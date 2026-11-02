"""Optional categorization, safely separated from immutable visit notes.

The client is replaceable with a real external provider. Only synthetic data
should be used with this classroom demonstration client.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import logging
import math
from uuid import UUID
from category import Category
from category_suggestion import CategorySuggestion, SuggestionStatus
from patient_service import parse_id

logger = logging.getLogger(__name__)

class KeywordAIClient:
    """Deterministic *demo substitute*, not a medical classifier."""
    def predict(self, reason: str):
        reason = reason.lower()
        rules = {
            Category.RESPIRATORY: ('cough', 'breath', 'wheez'),
            Category.DIGESTIVE: ('stomach', 'nausea', 'digest'),
            Category.MUSCULOSKELETAL: ('joint', 'muscle', 'sprain'),
        }
        # A basic heuristic for offline demonstrations; confidence varies by
        # evidence strength, so vague/unmatched text can be UNCERTAIN.
        matches = {category: sum(word in reason for word in keywords)
                   for category, keywords in rules.items()}
        category = max(matches, key=matches.get)
        strongest = matches[category]
        if strongest == 0:
            return Category.GENERAL_OTHER, 0.45
        # Ambiguity across organ systems deliberately lowers confidence.
        competing = any(count > 0 for group, count in matches.items() if group != category)
        return category, (0.55 if competing else min(0.95, 0.75 + 0.10 * (strongest - 1)))

class AICategoryService:
    def __init__(self, visit_service, suggestion_repository, auth_service,
                 client=None, timeout_seconds=0.5, confidence_threshold=0.70):
        if timeout_seconds <= 0 or not 0 <= confidence_threshold <= 1:
            raise ValueError('Invalid AI settings')
        self.visits = visit_service
        self.repository = suggestion_repository
        self.auth = auth_service
        self.client = client if client is not None else KeywordAIClient()
        self.timeout = timeout_seconds
        self.threshold = confidence_threshold

    def suggest_category(self, note_id, *, token):
        self.auth.authorize(token, 'read_visit_history')
        note = self.visits.get_visit_note(note_id, token=token)
        if note is None:
            raise LookupError('Visit note not found')
        if self.repository.find_by_note_id(note.note_id) is not None:
            raise ValueError('Suggestion already recorded for this visit')
        # The worker may finish after timeout; no worker is permitted to access DB.
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self.client.predict, note.note_content)
        try:
            category, confidence = future.result(timeout=self.timeout)
            if (not isinstance(category, Category) or isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not math.isfinite(confidence) or not 0 <= confidence <= 1):
                raise ValueError('Malformed AI response')
            if confidence < self.threshold:
                suggestion = CategorySuggestion.new(note.note_id, None, confidence, SuggestionStatus.UNCERTAIN)
            else:
                suggestion = CategorySuggestion.new(note.note_id, category, confidence, SuggestionStatus.PENDING)
        except FutureTimeout:
            logger.warning('AI suggestion timed out for note %s', note.note_id)
            suggestion = CategorySuggestion.new(note.note_id, None, None, SuggestionStatus.UNAVAILABLE)
        except (ConnectionError, TimeoutError, ValueError, TypeError, KeyError) as exc:
            logger.warning('AI suggestion unavailable for note %s: %s', note.note_id, type(exc).__name__)
            suggestion = CategorySuggestion.new(note.note_id, None, None, SuggestionStatus.UNAVAILABLE)
        except Exception:
            logger.exception('Unexpected AI classification failure for note %s', note.note_id)
            suggestion = CategorySuggestion.new(note.note_id, None, None, SuggestionStatus.UNAVAILABLE)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        self.repository.save(suggestion)
        return suggestion

    def review_suggestion(self, suggestion_id: UUID | str, patient_id: UUID | str, *,
                          accept: bool, token: str) -> CategorySuggestion:
        """Authorize doctor first; then validate patient ownership; then review.

        Authorization before the ownership query avoids exposing patient
        relationships to unauthorized users.
        """
        doctor = self.auth.authorize(token, 'review_ai_category')
        sid = parse_id(suggestion_id)
        pid = parse_id(patient_id)
        if self.repository.find_patient_id(sid) != pid:
            raise LookupError('Suggestion not found for this patient')
        if not isinstance(accept, bool):
            raise TypeError('accept must be a Boolean')
        return self.repository.review(sid, str(doctor.staff_id), accept)

    def get_suggestions_for_patient(self, patient_id: UUID | str, *,
                                    token: str) -> dict[UUID, CategorySuggestion]:
        """Authorize once and load all patient suggestions with one query."""
        self.auth.authorize(token, 'read_visit_history')
        return self.repository.find_by_patient_id(parse_id(patient_id))

    def get_suggestion(self, note_id, *, token):
        self.auth.authorize(token, 'read_visit_history')
        note = self.visits.get_visit_note(note_id, token=token)
        if note is None:
            raise LookupError('Visit note not found')
        return self.repository.find_by_note_id(note.note_id)

    def accepted_category(self, note_id, *, token):
        suggestion = self.get_suggestion(note_id, token=token)
        if suggestion and suggestion.status == SuggestionStatus.ACCEPTED:
            return suggestion.suggested_category
        return None

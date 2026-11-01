"""Optional categorization, safely separated from immutable visit notes.

The client is replaceable with a real external provider. Only synthetic data
should be used with this classroom demonstration client.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from category import Category
from category_suggestion import CategorySuggestion, SuggestionStatus
from patient_service import parse_id

class KeywordAIClient:
    """Deterministic *demo substitute*, not a medical classifier."""
    def predict(self, reason: str):
        reason = reason.lower()
        rules = {
            Category.RESPIRATORY: ('cough', 'breath', 'wheez'),
            Category.DIGESTIVE: ('stomach', 'nausea', 'digest'),
            Category.MUSCULOSKELETAL: ('joint', 'muscle', 'sprain'),
        }
        for category, keywords in rules.items():
            if any(word in reason for word in keywords):
                return category, 0.90
        return Category.GENERAL_OTHER, 0.75

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
            if not isinstance(category, Category) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ValueError('Malformed AI response')
            if confidence < self.threshold:
                suggestion = CategorySuggestion.new(note.note_id, None, confidence, SuggestionStatus.UNCERTAIN)
            else:
                suggestion = CategorySuggestion.new(note.note_id, category, confidence, SuggestionStatus.PENDING)
        except (Exception):
            suggestion = CategorySuggestion.new(note.note_id, None, None, SuggestionStatus.UNAVAILABLE)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        self.repository.save(suggestion)
        return suggestion

    def review_suggestion(self, suggestion_id, *, accept: bool, token: str):
        doctor = self.auth.authorize(token, 'review_ai_category')
        if not isinstance(accept, bool):
            raise TypeError('accept must be a Boolean')
        return self.repository.review(parse_id(suggestion_id), str(doctor.staff_id), accept)

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

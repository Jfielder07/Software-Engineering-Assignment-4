"""Immutable snapshots of AI suggestions and clinician decisions."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from category import Category

class SuggestionStatus(str, Enum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    UNAVAILABLE = 'unavailable'
    UNCERTAIN = 'uncertain'

@dataclass(frozen=True, slots=True)
class CategorySuggestion:
    suggestion_id: UUID
    note_id: UUID
    suggested_category: Category | None
    confidence_score: float | None
    status: SuggestionStatus
    reviewed_by: str | None = None
    created_at: datetime | None = None

    def __post_init__(self):
        if not isinstance(self.suggestion_id, UUID) or not isinstance(self.note_id, UUID):
            raise TypeError('IDs must be UUID values')
        if self.suggested_category is not None and not isinstance(self.suggested_category, Category):
            raise TypeError('Category must be an enum member')
        if self.confidence_score is not None and (not isinstance(self.confidence_score, (float, int)) or not 0 <= self.confidence_score <= 1):
            raise ValueError('Confidence must be within [0, 1]')
        if not isinstance(self.status, SuggestionStatus):
            raise TypeError('Invalid suggestion status')
        if self.status in (SuggestionStatus.PENDING, SuggestionStatus.ACCEPTED, SuggestionStatus.REJECTED) and self.suggested_category is None:
            raise ValueError('Reviewable suggestions require a category')
        if self.status in (SuggestionStatus.UNAVAILABLE, SuggestionStatus.UNCERTAIN) and self.suggested_category is not None:
            raise ValueError('Unavailable/uncertain results must not assign a category')
        if self.status in (SuggestionStatus.ACCEPTED, SuggestionStatus.REJECTED) and not self.reviewed_by:
            raise ValueError('Reviewed suggestion must identify the doctor')

    @classmethod
    def new(cls, note_id, category, confidence, status):
        return cls(uuid4(), note_id, category, confidence, status, created_at=datetime.now(timezone.utc))

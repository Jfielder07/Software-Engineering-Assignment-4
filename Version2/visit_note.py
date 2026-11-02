"""Immutable visit note entity; each note is associated with one patient."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4
from category import Category


@dataclass(frozen=True, slots=True)
class VisitNote:
    note_id: UUID
    patient_id: UUID
    visit_date: datetime
    note_content: str
    created_by: str
    category: Category | None = None

    @classmethod
    def create(cls, patient_id: UUID, note_content: str, created_by: str,
               category: Category | None = None) -> "VisitNote":
        return cls(uuid4(), patient_id, datetime.now(timezone.utc),
                   note_content, created_by, category)

    def __post_init__(self) -> None:
        if not isinstance(self.note_id, UUID) or not isinstance(self.patient_id, UUID):
            raise TypeError("note_id and patient_id must be UUID values")
        if not isinstance(self.visit_date, datetime) or self.visit_date.tzinfo is None or self.visit_date.utcoffset() is None:
            raise ValueError("visit_date must be a timezone-aware datetime")
        if not isinstance(self.note_content, str) or not self.note_content.strip():
            raise ValueError("note_content must be nonempty text")
        if not isinstance(self.created_by, str) or not self.created_by.strip():
            raise ValueError("created_by must identify the staff member")
        if self.category is not None and not isinstance(self.category, Category):
            raise TypeError("category must be a Category enum or None")

    def get_note_id(self) -> str:
        return str(self.note_id)

    def get_patient_id(self) -> str:
        return str(self.patient_id)

    def get_note_content(self) -> str:
        return self.note_content

    def get_visit_date(self) -> datetime:
        return self.visit_date

    def get_category(self) -> Category | None:
        return self.category

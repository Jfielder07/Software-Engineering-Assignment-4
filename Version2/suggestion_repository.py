"""Persistent AI recommendation and one-time clinical review."""
from datetime import datetime
from uuid import UUID
from category import Category
from category_suggestion import CategorySuggestion, SuggestionStatus
from database_connection import DatabaseConnection

class SuggestionRepository:
    def __init__(self, database: DatabaseConnection):
        self.database = database

    @staticmethod
    def _map(row):
        if row is None:
            return None
        return CategorySuggestion(UUID(row['suggestion_id']), UUID(row['note_id']),
            Category(row['category']) if row['category'] else None,
            row['confidence'], SuggestionStatus(row['status']), row['reviewed_by'],
            datetime.fromisoformat(row['created_at']))

    def save(self, suggestion: CategorySuggestion):
        with self.database.connect() as conn:
            conn.execute('''INSERT INTO category_suggestions
            (suggestion_id, note_id, category, confidence, status, reviewed_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (str(suggestion.suggestion_id), str(suggestion.note_id),
             suggestion.suggested_category.value if suggestion.suggested_category else None,
             suggestion.confidence_score, suggestion.status.value,
             suggestion.reviewed_by, suggestion.created_at.isoformat()))

    def find_by_note_id(self, note_id: UUID):
        row = self.database.connect().execute('SELECT * FROM category_suggestions WHERE note_id=?',
                                             (str(note_id),)).fetchone()
        return self._map(row)

    def find_patient_id(self, suggestion_id: UUID) -> UUID | None:
        """Return the owner patient of a suggestion using one join query."""
        row = self.database.connect().execute("""
            SELECT v.patient_id
            FROM category_suggestions AS s
            JOIN visit_notes AS v ON v.note_id = s.note_id
            WHERE s.suggestion_id = ?
        """, (str(suggestion_id),)).fetchone()
        return UUID(row['patient_id']) if row is not None else None

    def find_by_patient_id(self, patient_id: UUID) -> dict[UUID, CategorySuggestion]:
        """Retrieve all suggestions for one patient in one SQL JOIN.

        Keys are visit note UUIDs; values are saved suggestions.
        """
        rows = self.database.connect().execute("""
            SELECT s.*
            FROM category_suggestions AS s
            JOIN visit_notes AS v ON v.note_id = s.note_id
            WHERE v.patient_id = ?
        """, (str(patient_id),)).fetchall()
        suggestions = (self._map(row) for row in rows)
        return {item.note_id: item for item in suggestions}

    def review(self, suggestion_id: UUID, reviewer: str, accept: bool):
        state = SuggestionStatus.ACCEPTED if accept else SuggestionStatus.REJECTED
        with self.database.connect() as conn:
            cur = conn.execute('''UPDATE category_suggestions SET status=?, reviewed_by=?
              WHERE suggestion_id=? AND status='pending' ''', (state.value, reviewer, str(suggestion_id)))
            if cur.rowcount != 1:
                raise ValueError('Suggestion not found or no longer pending')
            row = conn.execute('SELECT * FROM category_suggestions WHERE suggestion_id=?',
                               (str(suggestion_id),)).fetchone()
        return self._map(row)

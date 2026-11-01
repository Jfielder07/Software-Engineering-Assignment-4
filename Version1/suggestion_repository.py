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

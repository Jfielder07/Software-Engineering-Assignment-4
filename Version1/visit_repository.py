"""Append-only persistence for patient visit history."""
from datetime import datetime
from uuid import UUID
from category import Category
from database_connection import DatabaseConnection
from visit_note import VisitNote


class VisitRepository:
    def __init__(self, database: DatabaseConnection) -> None:
        self.database = database

    def save_visit_note(self, note: VisitNote) -> None:
        if not isinstance(note, VisitNote):
            raise TypeError('note must be VisitNote')
        conn = self.database.connect()
        with conn:
            conn.execute('''
                INSERT INTO visit_notes
                    (note_id, patient_id, visit_date, note_content, created_by, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(note.note_id), str(note.patient_id), note.visit_date.isoformat(),
                  note.note_content, note.created_by,
                  note.category.value if note.category is not None else None))

    @staticmethod
    def _from_row(row) -> VisitNote | None:
        if row is None:
            return None
        return VisitNote(
            UUID(row['note_id']), UUID(row['patient_id']),
            datetime.fromisoformat(row['visit_date']), row['note_content'],
            row['created_by'], Category(row['category']) if row['category'] is not None else None)

    def find_note_by_id(self, note_id: UUID) -> VisitNote | None:
        if not isinstance(note_id, UUID):
            raise TypeError('note_id must be UUID')
        row = self.database.connect().execute(
            'SELECT * FROM visit_notes WHERE note_id=?', (str(note_id),)
        ).fetchone()
        return self._from_row(row)

    def find_notes_by_patient_id(self, patient_id: UUID) -> list[VisitNote]:
        if not isinstance(patient_id, UUID):
            raise TypeError('patient_id must be UUID')
        rows = self.database.connect().execute('''
            SELECT * FROM visit_notes WHERE patient_id=? ORDER BY visit_date, note_id
        ''', (str(patient_id),)).fetchall()
        return [self._from_row(row) for row in rows]

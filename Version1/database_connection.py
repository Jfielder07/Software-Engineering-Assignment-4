"""SQLite connection and schema for a classroom PRS prototype (not production PHI)."""
import sqlite3
from pathlib import Path


class DatabaseConnection:
    def __init__(self, database_path: str | Path = 'prs.db') -> None:
        self.database_path = str(database_path)
        self._connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.database_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute('PRAGMA foreign_keys = ON')
        return self._connection

    def initialize_schema(self) -> None:
        conn = self.connect()
        with conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS staff (
                    staff_id TEXT PRIMARY KEY NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('doctor', 'clinical_staff')),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS staff_sessions (
                    token_hash TEXT PRIMARY KEY NOT NULL,
                    staff_id TEXT NOT NULL REFERENCES staff(staff_id),
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON staff_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    date_of_birth TEXT NOT NULL,
                    contact_info TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS visit_notes (
                    note_id TEXT PRIMARY KEY NOT NULL,
                    patient_id TEXT NOT NULL,
                    visit_date TEXT NOT NULL,
                    note_content TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    category TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                        ON DELETE RESTRICT,
                    CHECK (category IS NULL OR category IN
                        ('Respiratory', 'Digestive', 'Musculoskeletal', 'General/Other'))
                );
                CREATE INDEX IF NOT EXISTS idx_visit_notes_patient_date
                    ON visit_notes(patient_id, visit_date);
                CREATE TABLE IF NOT EXISTS category_suggestions (
                    suggestion_id TEXT PRIMARY KEY,
                    note_id TEXT UNIQUE NOT NULL REFERENCES visit_notes(note_id) ON DELETE RESTRICT,
                    category TEXT,
                    confidence REAL CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1),
                    status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','unavailable','uncertain')),
                    reviewed_by TEXT,
                    created_at TEXT NOT NULL,
                    CHECK ((status IN ('unavailable','uncertain') AND category IS NULL)
                           OR (status IN ('pending','accepted','rejected') AND category IS NOT NULL)),
                    CHECK (status NOT IN ('accepted','rejected') OR reviewed_by IS NOT NULL)
                );
                CREATE TRIGGER IF NOT EXISTS prevent_suggestion_delete
                    BEFORE DELETE ON category_suggestions
                    BEGIN SELECT RAISE(ABORT, 'suggestions cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS restrict_suggestion_update
                    BEFORE UPDATE ON category_suggestions
                    WHEN OLD.status != 'pending' OR NEW.status NOT IN ('accepted','rejected')
                      OR NEW.note_id != OLD.note_id OR NEW.suggestion_id != OLD.suggestion_id
                      OR NEW.category IS NOT OLD.category OR NEW.confidence IS NOT OLD.confidence
                      OR NEW.created_at != OLD.created_at OR NEW.reviewed_by IS NULL
                    BEGIN SELECT RAISE(ABORT, 'only one clinical review is permitted'); END;
                CREATE TRIGGER IF NOT EXISTS prevent_patient_id_change
                    BEFORE UPDATE OF patient_id ON patients
                    BEGIN SELECT RAISE(ABORT, 'patient IDs are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS prevent_visit_note_update
                    BEFORE UPDATE ON visit_notes
                    BEGIN SELECT RAISE(ABORT, 'visit notes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS prevent_visit_note_delete
                    BEFORE DELETE ON visit_notes
                    BEGIN SELECT RAISE(ABORT, 'visit notes cannot be deleted'); END;
            ''')

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> 'DatabaseConnection':
        self.connect()
        self.initialize_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

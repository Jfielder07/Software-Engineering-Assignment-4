"""Persistent account and opaque login-token storage."""
from uuid import UUID
from staff import Staff, Role
from database_connection import DatabaseConnection

class StaffRepository:
    def __init__(self, database: DatabaseConnection):
        self.database = database

    def create(self, staff: Staff) -> None:
        with self.database.connect() as conn:
            conn.execute('INSERT INTO staff (staff_id, username, password_hash, role, active) VALUES (?, ?, ?, ?, ?)',
                         (str(staff.staff_id), staff.username, staff.password_hash, staff.role.value, int(staff.active)))

    def find_by_username(self, username: str) -> Staff | None:
        row = self.database.connect().execute('SELECT * FROM staff WHERE username=?', (username,)).fetchone()
        return self._staff(row)

    def find_by_id(self, staff_id: UUID) -> Staff | None:
        row = self.database.connect().execute('SELECT * FROM staff WHERE staff_id=?', (str(staff_id),)).fetchone()
        return self._staff(row)

    @staticmethod
    def _staff(row):
        return None if row is None else Staff(UUID(row['staff_id']), row['username'], row['password_hash'], Role(row['role']), bool(row['active']))

    def insert_session(self, token_hash: str, staff_id: UUID, expires_at: str) -> None:
        with self.database.connect() as conn:
            conn.execute('INSERT INTO staff_sessions (token_hash, staff_id, expires_at) VALUES (?, ?, ?)',
                         (token_hash, str(staff_id), expires_at))

    def get_session_staff(self, token_hash: str, now: str) -> Staff | None:
        row = self.database.connect().execute('''SELECT s.* FROM staff s
            JOIN staff_sessions t ON t.staff_id=s.staff_id
            WHERE t.token_hash=? AND t.expires_at>? AND s.active=1''', (token_hash, now)).fetchone()
        return self._staff(row)

    def delete_session(self, token_hash: str) -> None:
        with self.database.connect() as conn:
            conn.execute('DELETE FROM staff_sessions WHERE token_hash=?', (token_hash,))

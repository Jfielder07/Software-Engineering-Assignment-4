"""Password authentication and role checks for a classroom prototype."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from staff import Staff, Role
from staff_repository import StaffRepository

# Backend-enforced policy (default-deny).
PERMISSIONS = {
    'create_patient': {Role.DOCTOR, Role.CLINICAL_STAFF},
    'search_patient': {Role.DOCTOR, Role.CLINICAL_STAFF},
    'update_patient': {Role.DOCTOR, Role.CLINICAL_STAFF},
    'create_visit_note': {Role.DOCTOR, Role.CLINICAL_STAFF},
    'read_visit_history': {Role.DOCTOR, Role.CLINICAL_STAFF},
    'review_ai_category': {Role.DOCTOR},
}

class AuthenticationService:
    def __init__(self, repository: StaffRepository):
        self.repository = repository

    @staticmethod
    def _hash_password(password: str, *, salt: bytes | None = None) -> str:
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError('Password must have at least 12 characters')
        salt = secrets.token_bytes(16) if salt is None else salt
        digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)
        return f'scrypt$16384$8$1${salt.hex()}${digest.hex()}'

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt, expected = encoded.split('$')
            if algorithm != 'scrypt' or (int(n), int(r), int(p)) != (16384, 8, 1):
                return False
            computed = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
            return hmac.compare_digest(computed, bytes.fromhex(expected))
        except (ValueError, TypeError):
            return False

    def register_staff(self, username: str, password: str, role: Role, *, bootstrap: bool = False) -> Staff:
        """Bootstrap is CLI-only in this prototype; do not expose account creation via a public route."""
        if not bootstrap:
            raise PermissionError('Staff enrollment is restricted to offline bootstrap')
        if not isinstance(username, str) or not username.strip():
            raise ValueError('Username required')
        if not isinstance(role, Role):
            raise ValueError('Invalid role')
        staff = Staff(uuid4(), username.strip(), self._hash_password(password), role)
        self.repository.create(staff)
        return staff

    def login(self, username: str, password: str) -> str:
        staff = self.repository.find_by_username(username) if isinstance(username, str) else None
        if not staff or not staff.active or not isinstance(password, str) or not self._verify_password(password, staff.password_hash):
            raise PermissionError('Invalid username or password')
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        self.repository.insert_session(digest, staff.staff_id, expires)
        return token

    def current_user(self, token: str) -> Staff:
        if not isinstance(token, str) or not token:
            raise PermissionError('Login required')
        digest = hashlib.sha256(token.encode()).hexdigest()
        staff = self.repository.get_session_staff(digest, datetime.now(timezone.utc).isoformat())
        if staff is None:
            raise PermissionError('Session invalid, expired, or revoked')
        return staff

    def authorize(self, token: str, action: str) -> Staff:
        staff = self.current_user(token)
        if staff.role not in PERMISSIONS.get(action, set()):
            raise PermissionError('Not authorized for this action')
        return staff

    def logout(self, token: str) -> None:
        if isinstance(token, str) and token:
            self.repository.delete_session(hashlib.sha256(token.encode()).hexdigest())

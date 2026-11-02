"""Staff identity and role definitions. No plaintext passwords are stored."""
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

class Role(str, Enum):
    DOCTOR = 'doctor'
    CLINICAL_STAFF = 'clinical_staff'

@dataclass(frozen=True, slots=True)
class Staff:
    staff_id: UUID
    username: str
    password_hash: str
    role: Role
    active: bool = True

    def __post_init__(self):
        if not isinstance(self.staff_id, UUID):
            raise TypeError('staff_id must be UUID')
        if not isinstance(self.username, str) or not self.username.strip():
            raise ValueError('username required')
        if not isinstance(self.password_hash, str) or not self.password_hash:
            raise ValueError('password_hash required')
        if not isinstance(self.role, Role):
            raise TypeError('Invalid role')

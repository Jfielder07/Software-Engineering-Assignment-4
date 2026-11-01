"""Patient entity. Authorization and consent are enforced by PatientService later."""
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Patient:
    patient_id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    contact_info: str

    @classmethod
    def create(cls, first_name: str, last_name: str,
               date_of_birth: date, contact_info: str) -> "Patient":
        """Create a new patient with an automatically generated, unique ID."""
        return cls(uuid4(), first_name, last_name, date_of_birth, contact_info)

    def __post_init__(self) -> None:
        if not isinstance(self.patient_id, UUID):
            raise TypeError("patient_id must be a UUID")
        for field_name in ("first_name", "last_name", "contact_info"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be nonempty text")
        if not isinstance(self.date_of_birth, date) or isinstance(self.date_of_birth, datetime):
            raise TypeError("date_of_birth must be a date")
        if self.date_of_birth > date.today():
            raise ValueError("date_of_birth cannot be in the future")

    def get_patient_id(self) -> str:
        return str(self.patient_id)

    def get_patient_info(self) -> dict:
        return {
            "patient_id": str(self.patient_id),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "date_of_birth": self.date_of_birth.isoformat(),
            "contact_info": self.contact_info,
        }

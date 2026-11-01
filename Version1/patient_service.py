"""Stage 3 patient use cases. Authentication and role enforcement arrive in Stage 4.

Do not expose these services to untrusted clients until Stage 4 is implemented.
"""
from dataclasses import replace
from datetime import date
from uuid import UUID
from patient import Patient
from patient_repository import PatientRepository


def parse_id(value: UUID | str) -> UUID:
    """Normalize a patient/note ID; reject invalid input with ValueError."""
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError('ID must be a UUID or UUID string')
    try:
        return UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError('Invalid UUID') from exc


class PatientService:
    def __init__(self, patient_repository: PatientRepository, auth_service) -> None:
        self.patient_repository = patient_repository
        self.auth_service = auth_service

    def create_patient(self, first_name: str, last_name: str,
                       date_of_birth: date, contact_info: str, *, token: str) -> Patient:
        self.auth_service.authorize(token, 'create_patient')
        patient = Patient.create(first_name, last_name, date_of_birth, contact_info)
        self.patient_repository.save_patient(patient)
        return patient

    def search_patient(self, patient_id: UUID | str, *, token: str) -> Patient | None:
        self.auth_service.authorize(token, 'search_patient')
        return self.patient_repository.find_patient_by_id(parse_id(patient_id))

    def patient_exists(self, patient_id: UUID | str, *, token: str) -> bool:
        self.auth_service.authorize(token, 'search_patient')
        return self.patient_repository.patient_exists(parse_id(patient_id))

    def update_patient(self, patient_id: UUID | str, *, token: str, consent: bool,
                       first_name: str | None = None, last_name: str | None = None,
                       date_of_birth: date | None = None,
                       contact_info: str | None = None) -> Patient:
        self.auth_service.authorize(token, 'update_patient')
        if consent is not True:
            raise PermissionError('Explicit patient consent is required')
        patient = self.search_patient(patient_id, token=token)
        if patient is None:
            raise LookupError('Patient not found')
        changes = {key: value for key, value in {
            'first_name': first_name, 'last_name': last_name,
            'date_of_birth': date_of_birth, 'contact_info': contact_info,
        }.items() if value is not None}
        if not changes:
            raise ValueError('Provide at least one field to update')
        updated = replace(patient, **changes)
        self.patient_repository.update_patient(updated)
        return updated

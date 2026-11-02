"""Authorized visit-note use cases; notes remain immutable."""
from uuid import UUID
from category import Category
from patient_service import PatientService, parse_id
from visit_note import VisitNote
from visit_repository import VisitRepository

class VisitService:
    def __init__(self, visit_repository: VisitRepository,
                 patient_service: PatientService, auth_service) -> None:
        self.visit_repository = visit_repository
        self.patient_service = patient_service
        self.auth_service = auth_service

    def create_visit_note(self, patient_id: UUID | str, note_content: str,
                          category: Category | None = None, *, token: str) -> VisitNote:
        staff = self.auth_service.authorize(token, 'create_visit_note')
        pid = parse_id(patient_id)
        if not self.patient_service.patient_exists(pid, token=token):
            raise LookupError('Cannot create a visit note for a nonexistent patient')
        note = VisitNote.create(pid, note_content, str(staff.staff_id), category)
        self.visit_repository.save_visit_note(note)
        return note

    def get_visit_history(self, patient_id: UUID | str, *, token: str) -> list[VisitNote]:
        self.auth_service.authorize(token, 'read_visit_history')
        pid = parse_id(patient_id)
        if not self.patient_service.patient_exists(pid, token=token):
            raise LookupError('Patient not found')
        return self.visit_repository.find_notes_by_patient_id(pid)

    def get_visit_note(self, note_id: UUID | str, *, token: str) -> VisitNote | None:
        self.auth_service.authorize(token, 'read_visit_history')
        return self.visit_repository.find_note_by_id(parse_id(note_id))

"""Demonstrates optional AI assistance with synthetic patient data."""
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from visit_repository import VisitRepository
from staff_repository import StaffRepository
from authentication_service import AuthenticationService
from patient_service import PatientService
from visit_service import VisitService
from suggestion_repository import SuggestionRepository
from ai_category_service import AICategoryService
from staff import Role

with TemporaryDirectory() as directory:
    path = Path(directory) / 'demo.db'
    with DatabaseConnection(path) as db:
        auth = AuthenticationService(StaffRepository(db))
        auth.register_staff('demo-doctor', 'sample-password-only', Role.DOCTOR, bootstrap=True)
        token = auth.login('demo-doctor', 'sample-password-only')
        patients = PatientService(PatientRepository(db), auth)
        visits = VisitService(VisitRepository(db), patients, auth)
        ai = AICategoryService(visits, SuggestionRepository(db), auth)
        patient = patients.create_patient('Example', 'Patient', date(1992, 6, 10), 'fictional@example.test', token=token)
        note = visits.create_visit_note(patient.patient_id, 'Persistent cough', token=token)
        suggestion = ai.suggest_category(note.note_id, token=token)
        print('Saved note:', note.note_id)
        print('Suggested category:', suggestion.suggested_category)
        print('Suggestion status:', suggestion.status.value)
        if suggestion.suggested_category is not None:
            reviewed = ai.review_suggestion(suggestion.suggestion_id, accept=True, token=token)
            print('Doctor decision:', reviewed.status.value)
        auth.logout(token)
    with DatabaseConnection(path) as reopened:
        print('Persisted suggestion:', SuggestionRepository(reopened).find_by_note_id(note.note_id).status.value)

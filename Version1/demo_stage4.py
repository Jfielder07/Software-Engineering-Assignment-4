"""Demonstrate authenticated operations with fictional classroom data."""
from datetime import date
from pathlib import Path
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from visit_repository import VisitRepository
from patient_service import PatientService
from visit_service import VisitService
from staff import Role
from staff_repository import StaffRepository
from authentication_service import AuthenticationService

with DatabaseConnection(Path('prs_stage4_demo.db')) as db:
    auth = AuthenticationService(StaffRepository(db))
    if auth.repository.find_by_username('demo-doctor') is None:
        auth.register_staff('demo-doctor', 'fictional-demo-password-123', Role.DOCTOR, bootstrap=True)
    token = auth.login('demo-doctor', 'fictional-demo-password-123')
    patients = PatientService(PatientRepository(db), auth)
    visits = VisitService(VisitRepository(db), patients, auth)
    patient = patients.create_patient('Example', 'Patient', date(1992, 5, 10), 'fictional@example.test', token=token)
    patients.update_patient(patient.patient_id, consent=True, contact_info='updated@example.test', token=token)
    visit = visits.create_visit_note(patient.patient_id, 'Fictional checkup', token=token)
    print('Patient:', patients.search_patient(patient.patient_id, token=token).get_patient_info())
    print('History:', visits.get_visit_history(patient.patient_id, token=token))
    print('Note author matches logged-in doctor:', visit.created_by == str(auth.current_user(token).staff_id))
    auth.logout(token)
    try:
        patients.search_patient(patient.patient_id, token=token)
    except PermissionError:
        print('Logout successfully revoked access.')

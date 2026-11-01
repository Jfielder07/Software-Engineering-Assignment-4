"""Demo of Stage 3 services using synthetic patient information only."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from category import Category
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from patient_service import PatientService
from visit_repository import VisitRepository
from visit_service import VisitService


def main() -> None:
    with TemporaryDirectory() as tmp:
        db_file = Path(tmp) / 'demo.db'
        with DatabaseConnection(db_file) as db:
            patients = PatientService(PatientRepository(db))
            visits = VisitService(VisitRepository(db), patients)
            patient = patients.create_patient('Demo', 'Person', date(2000, 2, 3), 'example@example.test')
            print('Created patient:', patient.get_patient_info())
            updated = patients.update_patient(patient.patient_id, consent=True,
                                              contact_info='updated@example.test')
            print('Updated contact:', updated.contact_info)
            note = visits.create_visit_note(patient.patient_id, 'Demonstration-only visit note',
                                           'demo-staff', Category.GENERAL_OTHER)
            print('Saved note:', note.get_note_id())
        with DatabaseConnection(db_file) as db:
            patients = PatientService(PatientRepository(db))
            visits = VisitService(VisitRepository(db), patients)
            print('After database reopen:', patients.search_patient(patient.patient_id).get_patient_info())
            print('Saved visit history:', len(visits.get_visit_history(patient.patient_id)))


if __name__ == '__main__':
    main()

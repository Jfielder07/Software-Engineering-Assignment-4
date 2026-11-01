"""Run twice to see a patient and note persist after a full process restart."""
from datetime import date
from pathlib import Path
from category import Category
from patient import Patient
from visit_note import VisitNote
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from visit_repository import VisitRepository


def main():
    db_path = Path(__file__).with_name('prs_demo.db')
    with DatabaseConnection(db_path) as db:
        patients = PatientRepository(db)
        visits = VisitRepository(db)
        saved_id_path = Path(__file__).with_name('demo_patient_id.txt')
        if saved_id_path.exists():
            from uuid import UUID
            patient_id = UUID(saved_id_path.read_text().strip())
            patient = patients.find_patient_by_id(patient_id)
            if patient is None:
                raise RuntimeError('Saved demo ID not in database; remove demo_patient_id.txt to reset')
            print('Existing patient loaded after restart:', patient.get_patient_info())
        else:
            patient = Patient.create('Example', 'Patient', date(1990, 4, 12), 'fictional@example.test')
            patients.save_patient(patient)
            saved_id_path.write_text(str(patient.patient_id))
            print('New patient saved:', patient.get_patient_info())
            visits.save_visit_note(VisitNote.create(
                patient.patient_id, 'Fictional demonstration visit',
                'demo-doctor', Category.GENERAL_OTHER))
        print('Visit history:')
        for note in visits.find_notes_by_patient_id(patient.patient_id):
            print(note.visit_date.isoformat(), note.note_content, note.category)


if __name__ == '__main__':
    main()

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import uuid4
from category import Category
from patient import Patient
from visit_note import VisitNote
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from visit_repository import VisitRepository


class StageTwoTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'test.db'
        self.db = DatabaseConnection(self.path)
        self.db.initialize_schema()
        self.patients = PatientRepository(self.db)
        self.visits = VisitRepository(self.db)
        self.patient = Patient.create('Jane', 'Doe', date(1990, 4, 12), 'fictional@example.test')
        self.patients.save_patient(self.patient)

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def test_patient_round_trip(self):
        self.assertEqual(self.patients.find_patient_by_id(self.patient.patient_id), self.patient)

    def test_persistence_after_reopening(self):
        note = VisitNote.create(self.patient.patient_id, 'Checkup', 'doctor-1', Category.GENERAL_OTHER)
        self.visits.save_visit_note(note)
        self.db.close()
        new_db = DatabaseConnection(self.path)
        new_db.initialize_schema()
        try:
            self.assertEqual(PatientRepository(new_db).find_patient_by_id(self.patient.patient_id), self.patient)
            self.assertEqual(VisitRepository(new_db).find_note_by_id(note.note_id), note)
        finally:
            new_db.close()

    def test_history_order_and_category_none(self):
        note1 = VisitNote.create(self.patient.patient_id, 'Checkup', 'doctor-1')
        note2 = VisitNote.create(self.patient.patient_id, 'Cough', 'doctor-1', Category.RESPIRATORY)
        self.visits.save_visit_note(note1)
        self.visits.save_visit_note(note2)
        history = self.visits.find_notes_by_patient_id(self.patient.patient_id)
        self.assertEqual({n.note_id for n in history}, {note1.note_id, note2.note_id})
        self.assertIsNone(self.visits.find_note_by_id(note1.note_id).category)

    def test_reject_orphan_note(self):
        note = VisitNote.create(uuid4(), 'Orphan', 'doctor-1')
        with self.assertRaises(sqlite3.IntegrityError):
            self.visits.save_visit_note(note)

    def test_reject_duplicate_patient(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.patients.save_patient(self.patient)

    def test_note_update_and_delete_blocked_in_database(self):
        note = VisitNote.create(self.patient.patient_id, 'Original', 'doctor-1')
        self.visits.save_visit_note(note)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect():
                self.db.connect().execute('UPDATE visit_notes SET note_content=? WHERE note_id=?',
                                          ('Changed', str(note.note_id)))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect():
                self.db.connect().execute('DELETE FROM visit_notes WHERE note_id=?', (str(note.note_id),))
        self.assertEqual(self.visits.find_note_by_id(note.note_id).note_content, 'Original')

    def test_patient_id_update_blocked_in_database(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect():
                self.db.connect().execute('UPDATE patients SET patient_id=? WHERE patient_id=?',
                                          (str(uuid4()), str(self.patient.patient_id)))

    def test_patient_permitted_field_update(self):
        changed = replace(self.patient, contact_info='new@example.test')
        self.patients.update_patient(changed)
        self.assertEqual(self.patients.find_patient_by_id(self.patient.patient_id), changed)

    def test_missing_lookups(self):
        self.assertIsNone(self.patients.find_patient_by_id(uuid4()))
        self.assertIsNone(self.visits.find_note_by_id(uuid4()))
        self.assertEqual(self.visits.find_notes_by_patient_id(uuid4()), [])


if __name__ == '__main__':
    unittest.main()

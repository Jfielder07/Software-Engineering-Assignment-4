"""Service tests against a real temporary SQLite database."""
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4
from category import Category
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from patient_service import PatientService
from visit_repository import VisitRepository
from visit_service import VisitService
from staff_repository import StaffRepository
from staff import Role
from authentication_service import AuthenticationService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'prs.db'
        self.db = DatabaseConnection(self.path)
        self.db.__enter__()
        self.auth = AuthenticationService(StaffRepository(self.db))
        self.auth.register_staff('doc', 'a-very-long-test-password', Role.DOCTOR, bootstrap=True)
        self.token = self.auth.login('doc', 'a-very-long-test-password')
        self.patients = PatientService(PatientRepository(self.db), self.auth)
        self.visits = VisitService(VisitRepository(self.db), self.patients, self.auth)
        self.patient = self.patients.create_patient('Test', 'Patient', date(1995, 1, 1), 'test@example.test', token=self.token)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_create_and_search(self):
        self.assertEqual(self.patients.search_patient(str(self.patient.patient_id), token=self.token), self.patient)
        self.assertTrue(self.patients.patient_exists(self.patient.patient_id, token=self.token))

    def test_unique_ids(self):
        second = self.patients.create_patient('Second', 'Patient', date(2000, 1, 1), 'other@example.test', token=self.token)
        self.assertNotEqual(self.patient.patient_id, second.patient_id)

    def test_update_consent_required(self):
        for consent in [False, None, 1, 'yes']:
            with self.subTest(consent=consent), self.assertRaises(PermissionError):
                self.patients.update_patient(self.patient.patient_id, token=self.token, consent=consent, first_name='Changed')
        self.assertEqual(self.patients.search_patient(self.patient.patient_id, token=self.token).first_name, 'Test')

    def test_update_approved_retains_id_and_other_fields(self):
        edited = self.patients.update_patient(self.patient.patient_id, token=self.token, consent=True,
                                              contact_info='new@example.test')
        self.assertEqual(edited.patient_id, self.patient.patient_id)
        self.assertEqual(edited.first_name, 'Test')
        self.assertEqual(self.patients.search_patient(self.patient.patient_id, token=self.token), edited)

    def test_invalid_update_does_not_persist(self):
        with self.assertRaises(ValueError):
            self.patients.update_patient(self.patient.patient_id, token=self.token, consent=True, first_name='  ')
        self.assertEqual(self.patients.search_patient(self.patient.patient_id, token=self.token), self.patient)

    def test_update_missing_patient_and_no_changes(self):
        with self.assertRaises(LookupError):
            self.patients.update_patient(uuid4(), token=self.token, consent=True, first_name='Someone')
        with self.assertRaises(ValueError):
            self.patients.update_patient(self.patient.patient_id, token=self.token, consent=True)

    def test_invalid_id(self):
        with self.assertRaises(ValueError):
            self.patients.search_patient('not-a-uuid', token=self.token)

    def test_note_for_existing_patient(self):
        note = self.visits.create_visit_note(str(self.patient.patient_id), 'Checkup', Category.GENERAL_OTHER, token=self.token)
        self.assertEqual(self.visits.get_visit_note(str(note.note_id), token=self.token), note)
        self.assertEqual(self.visits.get_visit_history(self.patient.patient_id, token=self.token), [note])

    def test_note_nonexistent_patient_rejected(self):
        with self.assertRaises(LookupError):
            self.visits.create_visit_note(uuid4(), 'Checkup', token=self.token)
        self.assertEqual(self.visits.get_visit_history(self.patient.patient_id, token=self.token), [])

    def test_optional_category(self):
        note = self.visits.create_visit_note(self.patient.patient_id, 'Note without AI', token=self.token)
        self.assertIsNone(note.category)

    def test_multiple_notes_preserve_history(self):
        a = self.visits.create_visit_note(self.patient.patient_id, 'First', token=self.token)
        b = self.visits.create_visit_note(self.patient.patient_id, 'Second', token=self.token)
        self.assertEqual({n.note_id for n in self.visits.get_visit_history(self.patient.patient_id, token=self.token)}, {a.note_id, b.note_id})

    def test_history_missing_patient(self):
        with self.assertRaises(LookupError):
            self.visits.get_visit_history(uuid4(), token=self.token)

    def test_restart_reloads_updates_and_notes(self):
        self.patients.update_patient(self.patient.patient_id, token=self.token, consent=True, last_name='Changed')
        note = self.visits.create_visit_note(self.patient.patient_id, 'Retained after restart', token=self.token)
        self.db.close()
        with DatabaseConnection(self.path) as db2:
            p = PatientService(PatientRepository(db2), self.auth)
            v = VisitService(VisitRepository(db2), p, self.auth)
            self.assertEqual(p.search_patient(self.patient.patient_id, token=self.token).last_name, 'Changed')
            self.assertEqual(v.get_visit_history(self.patient.patient_id, token=self.token), [note])


if __name__ == '__main__':
    unittest.main()

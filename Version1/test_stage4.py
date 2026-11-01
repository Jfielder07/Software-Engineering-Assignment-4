"""Stage 4 real-SQLite tests for authentication and authorization."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import date
from uuid import uuid4
from database_connection import DatabaseConnection
from staff import Role
from staff_repository import StaffRepository
from authentication_service import AuthenticationService
from patient_repository import PatientRepository
from patient_service import PatientService
from visit_repository import VisitRepository
from visit_service import VisitService

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'records.db'
        self.db = DatabaseConnection(self.path)
        self.db.__enter__()
        self.auth = AuthenticationService(StaffRepository(self.db))
        self.doctor = self.auth.register_staff('doctor', 'very-long-doc-password', Role.DOCTOR, bootstrap=True)
        self.clinician = self.auth.register_staff('nurse', 'very-long-nurse-password', Role.CLINICAL_STAFF, bootstrap=True)
        self.token = self.auth.login('doctor', 'very-long-doc-password')
        self.p = PatientService(PatientRepository(self.db), self.auth)
        self.v = VisitService(VisitRepository(self.db), self.p, self.auth)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_password_hash_no_plaintext(self):
        self.assertTrue(self.doctor.password_hash.startswith('scrypt$'))
        self.assertNotIn('very-long-doc-password', self.doctor.password_hash)

    def test_wrong_password_denied(self):
        with self.assertRaises(PermissionError):
            self.auth.login('doctor', 'wrong-password')

    def test_unregistered_access_denied(self):
        with self.assertRaises(PermissionError):
            self.auth.register_staff('attacker', 'very-long-attacker-pass', Role.DOCTOR)

    def test_unauthenticated_patient_actions_denied(self):
        with self.assertRaises(PermissionError):
            self.p.create_patient('Ann', 'A', date(2000,1,1), 'email', token='invalid')
        with self.assertRaises(PermissionError):
            self.p.search_patient(uuid4(), token='invalid')

    def test_session_logout_revokes_access(self):
        self.auth.logout(self.token)
        with self.assertRaises(PermissionError):
            self.p.search_patient(uuid4(), token=self.token)

    def test_roles_and_default_deny(self):
        nurse_token = self.auth.login('nurse', 'very-long-nurse-password')
        self.assertEqual(self.auth.authorize(nurse_token, 'create_patient').staff_id, self.clinician.staff_id)
        with self.assertRaises(PermissionError):
            self.auth.authorize(nurse_token, 'review_ai_category')
        with self.assertRaises(PermissionError):
            self.auth.authorize(self.token, 'unknown_action')
        self.assertEqual(self.auth.authorize(self.token, 'review_ai_category').role, Role.DOCTOR)

    def test_create_update_and_history(self):
        patient = self.p.create_patient('Ann', 'A', date(2000,1,1), 'email', token=self.token)
        with self.assertRaises(PermissionError):
            self.p.update_patient(patient.patient_id, consent=False, contact_info='new', token=self.token)
        edited = self.p.update_patient(patient.patient_id, consent=True, contact_info='new', token=self.token)
        self.assertEqual(edited.patient_id, patient.patient_id)
        note = self.v.create_visit_note(patient.patient_id, 'Checkup', token=self.token)
        self.assertEqual(note.created_by, str(self.doctor.staff_id))
        self.assertEqual(self.v.get_visit_history(patient.patient_id, token=self.token), [note])
        with self.assertRaises(PermissionError):
            self.v.get_visit_history(patient.patient_id, token='invalid')
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.connect().execute('UPDATE visit_notes SET note_content=? WHERE note_id=?', ('bad', str(note.note_id)))

    def test_restart_preserves_accounts_but_not_plaintext_token(self):
        self.db.close()
        with DatabaseConnection(self.path) as reopened:
            auth = AuthenticationService(StaffRepository(reopened))
            self.assertEqual(auth.current_user(self.token).staff_id, self.doctor.staff_id)
            self.assertIsNone(reopened.connect().execute('SELECT token_hash FROM staff_sessions WHERE token_hash=?', (self.token,)).fetchone())

    def test_nonexistent_visit_refused(self):
        with self.assertRaises(LookupError):
            self.v.create_visit_note(uuid4(), 'Impossible', token=self.token)

    def test_account_deactivation_invalidates_existing_session(self):
        with self.db.connect():
            self.db.connect().execute('UPDATE staff SET active=0 WHERE staff_id=?', (str(self.doctor.staff_id),))
        with self.assertRaises(PermissionError):
            self.auth.current_user(self.token)

if __name__ == '__main__':
    unittest.main()

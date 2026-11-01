"""Stage 5 integration tests with synthetic data only."""
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from category import Category
from category_suggestion import SuggestionStatus
from database_connection import DatabaseConnection
from patient_repository import PatientRepository
from visit_repository import VisitRepository
from staff_repository import StaffRepository
from authentication_service import AuthenticationService
from patient_service import PatientService
from visit_service import VisitService
from staff import Role
from ai_category_service import AICategoryService
from suggestion_repository import SuggestionRepository

class Stage5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'prs.sqlite')
        self.open_database()
        self.auth.register_staff('doctor', 'doctor-secret-password', Role.DOCTOR, bootstrap=True)
        self.auth.register_staff('nurse', 'nurse-secret-password', Role.CLINICAL_STAFF, bootstrap=True)
        self.doc = self.auth.login('doctor', 'doctor-secret-password')
        self.nurse = self.auth.login('nurse', 'nurse-secret-password')
        self.patient = self.patients.create_patient('Test', 'Patient', date(1990, 1, 1), 'demo', token=self.doc)
        self.note = self.visits.create_visit_note(self.patient.patient_id, 'Persistent cough', token=self.doc)

    def open_database(self):
        self.db = DatabaseConnection(self.path)
        self.db.connect()
        self.db.initialize_schema()
        self.auth = AuthenticationService(StaffRepository(self.db))
        self.patients = PatientService(PatientRepository(self.db), self.auth)
        self.visits = VisitService(VisitRepository(self.db), self.patients, self.auth)
        self.suggestions = SuggestionRepository(self.db)
        self.ai = AICategoryService(self.visits, self.suggestions, self.auth)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_pending_and_doctor_acceptance(self):
        s = self.ai.suggest_category(self.note.note_id, token=self.doc)
        self.assertEqual(s.suggested_category, Category.RESPIRATORY)
        self.assertEqual(s.status, SuggestionStatus.PENDING)
        result = self.ai.review_suggestion(s.suggestion_id, accept=True, token=self.doc)
        self.assertEqual(result.status, SuggestionStatus.ACCEPTED)
        self.assertEqual(self.ai.accepted_category(self.note.note_id, token=self.doc), Category.RESPIRATORY)
        self.assertIsNone(self.visits.get_visit_note(self.note.note_id, token=self.doc).category)

    def test_rejection_and_double_review(self):
        s = self.ai.suggest_category(self.note.note_id, token=self.doc)
        self.assertEqual(self.ai.review_suggestion(s.suggestion_id, accept=False, token=self.doc).status, SuggestionStatus.REJECTED)
        self.assertIsNone(self.ai.accepted_category(self.note.note_id, token=self.doc))
        with self.assertRaises(ValueError):
            self.ai.review_suggestion(s.suggestion_id, accept=True, token=self.doc)

    def test_nurse_cannot_review(self):
        s = self.ai.suggest_category(self.note.note_id, token=self.nurse)
        with self.assertRaises(PermissionError):
            self.ai.review_suggestion(s.suggestion_id, accept=True, token=self.nurse)

    def test_uncertain(self):
        class LowConfidence:
            def predict(self, text): return Category.DIGESTIVE, 0.2
        ai = AICategoryService(self.visits, self.suggestions, self.auth, client=LowConfidence())
        s = ai.suggest_category(self.note.note_id, token=self.doc)
        self.assertEqual(s.status, SuggestionStatus.UNCERTAIN)
        with self.assertRaises(ValueError):
            ai.review_suggestion(s.suggestion_id, accept=True, token=self.doc)

    def test_failure_and_note_still_saved(self):
        class Down:
            def predict(self, text): raise ConnectionError('offline')
        ai = AICategoryService(self.visits, self.suggestions, self.auth, client=Down())
        s = ai.suggest_category(self.note.note_id, token=self.doc)
        self.assertEqual(s.status, SuggestionStatus.UNAVAILABLE)
        self.assertIsNotNone(self.visits.get_visit_note(self.note.note_id, token=self.doc))

    def test_timeout(self):
        class Slow:
            def predict(self, text):
                time.sleep(0.08)
                return Category.RESPIRATORY, 0.9
        ai = AICategoryService(self.visits, self.suggestions, self.auth, client=Slow(), timeout_seconds=0.01)
        self.assertEqual(ai.suggest_category(self.note.note_id, token=self.doc).status, SuggestionStatus.UNAVAILABLE)

    def test_malformed_response(self):
        class Bad:
            def predict(self, text): return 'cough', 0.99
        ai = AICategoryService(self.visits, self.suggestions, self.auth, client=Bad())
        self.assertEqual(ai.suggest_category(self.note.note_id, token=self.doc).status, SuggestionStatus.UNAVAILABLE)

    def test_restart_preserves_review(self):
        s = self.ai.suggest_category(self.note.note_id, token=self.doc)
        self.ai.review_suggestion(s.suggestion_id, accept=True, token=self.doc)
        self.db.close()
        self.open_database()
        self.assertEqual(self.ai.accepted_category(self.note.note_id, token=self.doc), Category.RESPIRATORY)

    def test_reject_duplicate_suggestion(self):
        self.ai.suggest_category(self.note.note_id, token=self.doc)
        with self.assertRaises(ValueError):
            self.ai.suggest_category(self.note.note_id, token=self.doc)

    def test_missing_note_and_invalid_session(self):
        from uuid import uuid4
        with self.assertRaises(LookupError):
            self.ai.suggest_category(uuid4(), token=self.doc)
        with self.assertRaises(PermissionError):
            self.ai.suggest_category(self.note.note_id, token='invalid')

if __name__ == '__main__':
    unittest.main()

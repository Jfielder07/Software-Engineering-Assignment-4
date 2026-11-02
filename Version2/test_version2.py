"""Stage 6 Version 2 regression tests, entirely synthetic and offline."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from ai_category_service import AICategoryService, KeywordAIClient
from category import Category
from category_suggestion import SuggestionStatus
from database_connection import DatabaseConnection
from llm_category_classifier import LLMCategoryClassifier
from patient_repository import PatientRepository
from patient_service import PatientService
from staff import Role
from staff_repository import StaffRepository
from authentication_service import AuthenticationService
from suggestion_repository import SuggestionRepository
from visit_repository import VisitRepository
from visit_service import VisitService


class PRSVersion2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DatabaseConnection(Path(self.temp.name) / 'test.db')
        self.db.initialize_schema()
        self.auth = AuthenticationService(StaffRepository(self.db))
        self.auth.register_staff('doctor', 'a-secure-demo-password', Role.DOCTOR, bootstrap=True)
        self.auth.register_staff('nurse', 'a-secure-demo-password', Role.CLINICAL_STAFF, bootstrap=True)
        self.doctor = self.auth.login('doctor', 'a-secure-demo-password')
        self.nurse = self.auth.login('nurse', 'a-secure-demo-password')
        self.patients = PatientService(PatientRepository(self.db), self.auth)
        self.visits = VisitService(VisitRepository(self.db), self.patients, self.auth)
        self.repo = SuggestionRepository(self.db)
        self.ai = AICategoryService(self.visits, self.repo, self.auth)
        self.alice = self.patients.create_patient('Alice', 'Example', date(1988, 1, 1), 'demo', token=self.doctor)
        self.bob = self.patients.create_patient('Bob', 'Example', date(1989, 1, 1), 'demo', token=self.doctor)
        self.n1 = self.visits.create_visit_note(self.alice.patient_id, 'cough', token=self.doctor)
        self.n2 = self.visits.create_visit_note(self.alice.patient_id, 'stomach pain', token=self.doctor)
        self.n3 = self.visits.create_visit_note(self.bob.patient_id, 'sprained ankle', token=self.doctor)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_find_patient_id_returns_uuid_or_none(self):
        suggestion = self.ai.suggest_category(self.n1.note_id, token=self.doctor)
        self.assertEqual(self.repo.find_patient_id(suggestion.suggestion_id), self.alice.patient_id)
        self.assertIsNone(self.repo.find_patient_id(uuid4()))

    def test_wrong_patient_cannot_review_suggestion(self):
        suggestion = self.ai.suggest_category(self.n1.note_id, token=self.doctor)
        with self.assertRaises(LookupError):
            self.ai.review_suggestion(suggestion.suggestion_id, self.bob.patient_id,
                                      accept=True, token=self.doctor)
        self.assertEqual(self.repo.find_by_note_id(self.n1.note_id).status, SuggestionStatus.PENDING)
        reviewed = self.ai.review_suggestion(suggestion.suggestion_id, self.alice.patient_id,
                                             accept=True, token=self.doctor)
        self.assertEqual(reviewed.status, SuggestionStatus.ACCEPTED)

    def test_authorization_before_ownership_query(self):
        suggestion = self.ai.suggest_category(self.n1.note_id, token=self.doctor)
        with patch.object(self.repo, 'find_patient_id', side_effect=AssertionError('Accessed ownership!')) as lookup:
            with self.assertRaises(PermissionError):
                self.ai.review_suggestion(suggestion.suggestion_id, self.alice.patient_id,
                                          accept=True, token=self.nurse)
            lookup.assert_not_called()
            with self.assertRaises(PermissionError):
                self.ai.review_suggestion(suggestion.suggestion_id, self.alice.patient_id,
                                          accept=True, token='invalid')
            lookup.assert_not_called()

    def test_wrong_or_nonexistent_patient_returns_no_suggestions(self):
        self.ai.suggest_category(self.n1.note_id, token=self.doctor)
        self.assertEqual(self.repo.find_by_patient_id(self.bob.patient_id), {})
        self.assertEqual(self.repo.find_by_patient_id(uuid4()), {})

    def test_batch_history_one_join_and_authorization_once(self):
        s1 = self.ai.suggest_category(self.n1.note_id, token=self.doctor)
        s2 = self.ai.suggest_category(self.n2.note_id, token=self.doctor)
        self.ai.suggest_category(self.n3.note_id, token=self.doctor)
        statements = []
        conn = self.db.connect()
        original_authorize = self.auth.authorize
        try:
            conn.set_trace_callback(statements.append)
            with patch.object(self.auth, 'authorize', wraps=original_authorize) as authorize:
                result = self.ai.get_suggestions_for_patient(self.alice.patient_id, token=self.doctor)
            self.assertEqual(authorize.call_count, 1)
        finally:
            conn.set_trace_callback(None)
        self.assertEqual(set(result), {self.n1.note_id, self.n2.note_id})
        self.assertEqual(result[self.n1.note_id].suggestion_id, s1.suggestion_id)
        self.assertEqual(result[self.n2.note_id].suggestion_id, s2.suggestion_id)
        selects = [sql.lower() for sql in statements if sql.lstrip().lower().startswith('select')]
        joins = [sql for sql in selects if 'join visit_notes' in sql]
        self.assertEqual(len(joins), 1, statements)
        self.assertEqual(len(selects), 2, statements)  # one session authorization + one JOIN

    def test_batch_history_requires_valid_session(self):
        with self.assertRaises(PermissionError):
            self.ai.get_suggestions_for_patient(self.alice.patient_id, token='bad')

    def test_fallback_vague_notes_uncertain(self):
        self.assertEqual(KeywordAIClient().predict('Not sure why I am here')[0], Category.GENERAL_OTHER)
        vague = self.visits.create_visit_note(self.alice.patient_id, 'Not sure why I am here', token=self.doctor)
        result = self.ai.suggest_category(vague.note_id, token=self.doctor)
        self.assertEqual(result.status, SuggestionStatus.UNCERTAIN)
        self.assertIsNone(result.suggested_category)

    def test_gemini_mock_returns_structured_category(self):
        sdk = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs:
            SimpleNamespace(text=json.dumps({'category': 'Respiratory', 'confidence': 0.93}))))
        classifier = LLMCategoryClassifier(sdk_client=sdk)
        self.assertEqual(classifier.predict('cough and wheezing'), (Category.RESPIRATORY, 0.93))

    def test_gemini_mock_low_confidence_is_uncertain(self):
        sdk = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs:
            SimpleNamespace(text=json.dumps({'category': 'Digestive', 'confidence': 0.38}))))
        classifier = LLMCategoryClassifier(sdk_client=sdk)
        ai = AICategoryService(self.visits, self.repo, self.auth, client=classifier)
        result = ai.suggest_category(self.n1.note_id, token=self.doctor)
        self.assertEqual(result.status, SuggestionStatus.UNCERTAIN)

    def test_gemini_malformed_json_is_unavailable_but_note_remains(self):
        sdk = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs:
            SimpleNamespace(text='not json')))
        classifier = LLMCategoryClassifier(sdk_client=sdk)
        ai = AICategoryService(self.visits, self.repo, self.auth, client=classifier)
        result = ai.suggest_category(self.n1.note_id, token=self.doctor)
        self.assertEqual(result.status, SuggestionStatus.UNAVAILABLE)
        self.assertIsNotNone(self.visits.get_visit_note(self.n1.note_id, token=self.doctor))

    def test_gemini_mock_uses_model_and_schema_without_leaking_key(self):
        calls = []
        def fake_generate(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text=json.dumps({'category':'General/Other', 'confidence':0.64}))
        classifier = LLMCategoryClassifier(model='gemini-3.8-flash', sdk_client=SimpleNamespace(
            models=SimpleNamespace(generate_content=fake_generate)))
        category, score = classifier.predict('fictional visit')
        self.assertEqual((category, score), (Category.GENERAL_OTHER, 0.64))
        self.assertEqual(calls[0]['model'], 'gemini-3.8-flash')
        self.assertEqual(calls[0]['config']['response_mime_type'], 'application/json')
        self.assertEqual(len(calls[0]['config']['response_schema']['properties']['category']['enum']), 4)
        self.assertNotIn('api_key', calls[0])


if __name__ == '__main__':
    unittest.main()

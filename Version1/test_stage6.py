"""Flask end-to-end tests. Skipped when Flask is not installed."""
import tempfile
import unittest
from pathlib import Path

try:
    from web_app import create_app
    from database_connection import DatabaseConnection
    from authentication_service import AuthenticationService
    from staff_repository import StaffRepository
    from staff import Role
except ModuleNotFoundError as exc:
    if exc.name not in ('flask', 'markupsafe', 'werkzeug', 'jinja2', 'click', 'itsdangerous', 'blinker'):
        raise
    create_app = None


@unittest.skipIf(create_app is None, 'Flask dependency not installed in this environment')
class Stage6WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbfile = str(Path(self.tmp.name) / 'test.db')
        self.app = create_app({'TESTING': True, 'DATABASE': self.dbfile, 'SECRET_KEY': 'test-only-secret'})
        self.client = self.app.test_client()
        with DatabaseConnection(self.dbfile) as db:
            auth = AuthenticationService(StaffRepository(db))
            auth.register_staff('doctor', 'doctor-password-123', Role.DOCTOR, bootstrap=True)
            auth.register_staff('nurse', 'nurse-password-1234', Role.CLINICAL_STAFF, bootstrap=True)

    def tearDown(self):
        self.tmp.cleanup()

    def csrf(self):
        with self.client.session_transaction() as s:
            return s.get('_csrf')

    def login(self, username='doctor', password='doctor-password-123'):
        self.client.get('/login')
        return self.client.post('/login', data={'username': username, 'password': password, '_csrf': self.csrf()}, follow_redirects=True)

    def create_patient(self):
        response = self.client.post('/patients/new', data={'_csrf': self.csrf(), 'first_name': 'Jane', 'last_name': 'Doe', 'date_of_birth': '1990-01-01', 'contact_info': 'demo@example.com'}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        return response.headers['Location'].split('/patients/')[1]

    def test_login_and_protected_page(self):
        self.assertEqual(self.client.get('/patients').status_code, 302)
        self.assertIn(b'Find patient', self.login().data)

    def test_no_csrf_rejected(self):
        self.client.get('/login')
        self.assertEqual(self.client.post('/login', data={'username': 'doctor'}).status_code, 400)

    def test_patient_note_ai_and_review(self):
        self.login()
        patient_id = self.create_patient()
        res = self.client.post(f'/patients/{patient_id}/notes', data={'_csrf': self.csrf(), 'note_content': 'Patient reports cough.'}, follow_redirects=True)
        self.assertIn(b'Patient reports cough.', res.data)
        with DatabaseConnection(self.dbfile) as db:
            note_id = db.connect().execute('SELECT note_id FROM visit_notes').fetchone()['note_id']
        res = self.client.post(f'/patients/{patient_id}/notes/{note_id}/suggest', data={'_csrf': self.csrf()}, follow_redirects=True)
        self.assertIn(b'Respiratory', res.data)
        with DatabaseConnection(self.dbfile) as db:
            suggestion_id = db.connect().execute('SELECT suggestion_id FROM category_suggestions').fetchone()['suggestion_id']
        res = self.client.post(f'/patients/{patient_id}/suggestions/{suggestion_id}/review', data={'_csrf': self.csrf(), 'decision': 'accept'}, follow_redirects=True)
        self.assertIn(b'accepted', res.data)
        self.assertEqual(self.client.get(f'/patients/{patient_id}').status_code, 200)

    def test_staff_cannot_review(self):
        self.login()
        patient_id = self.create_patient()
        self.client.post(f'/patients/{patient_id}/notes', data={'_csrf': self.csrf(), 'note_content': 'Persistent cough.'})
        with DatabaseConnection(self.dbfile) as db:
            note_id = db.connect().execute('SELECT note_id FROM visit_notes').fetchone()['note_id']
        self.client.post(f'/patients/{patient_id}/notes/{note_id}/suggest', data={'_csrf': self.csrf()})
        with DatabaseConnection(self.dbfile) as db:
            suggestion_id = db.connect().execute('SELECT suggestion_id FROM category_suggestions').fetchone()['suggestion_id']
        self.client.post('/logout', data={'_csrf': self.csrf()})
        self.login('nurse', 'nurse-password-1234')
        res = self.client.post(f'/patients/{patient_id}/suggestions/{suggestion_id}/review', data={'_csrf': self.csrf(), 'decision': 'accept'}, follow_redirects=True)
        self.assertIn(b'Not authorized', res.data)
        with DatabaseConnection(self.dbfile) as db:
            self.assertEqual(db.connect().execute('SELECT status FROM category_suggestions').fetchone()['status'], 'pending')

    def test_patient_update_requires_consent(self):
        self.login()
        pid = self.create_patient()
        fields = {'_csrf': self.csrf(), 'first_name': 'Jane', 'last_name': 'Doe', 'date_of_birth': '1990-01-01', 'contact_info': 'new@example.com'}
        res = self.client.post(f'/patients/{pid}/edit', data=fields, follow_redirects=True)
        self.assertIn(b'Explicit patient consent', res.data)
        fields['consent'] = 'yes'
        res = self.client.post(f'/patients/{pid}/edit', data=fields, follow_redirects=True)
        self.assertIn(b'new@example.com', res.data)

if __name__ == '__main__':
    unittest.main()

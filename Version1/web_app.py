"""Classroom PRS Flask UI. Fictional data only; NOT a production medical system."""
import os
import secrets
import sqlite3
from datetime import date
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from markupsafe import escape
from database_connection import DatabaseConnection
from staff_repository import StaffRepository
from authentication_service import AuthenticationService
from patient_repository import PatientRepository
from patient_service import PatientService
from visit_repository import VisitRepository
from visit_service import VisitService
from suggestion_repository import SuggestionRepository
from ai_category_service import AICategoryService
from category_suggestion import SuggestionStatus
from staff import Role


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get('PRS_SECRET_KEY') or secrets.token_hex(32),
        DATABASE=os.environ.get('PRS_DATABASE') or str(Path(__file__).with_name('prs_web.db')),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('PRS_SECURE_COOKIE') == '1',
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    # For multi-process deployment configure a persistent PRS_SECRET_KEY.

    def services():
        if 'db' not in g:
            g.db = DatabaseConnection(app.config['DATABASE'])
            g.db.connect()
            g.db.initialize_schema()
            g.auth = AuthenticationService(StaffRepository(g.db))
            g.patients = PatientService(PatientRepository(g.db), g.auth)
            g.visits = VisitService(VisitRepository(g.db), g.patients, g.auth)
            g.ai = AICategoryService(g.visits, SuggestionRepository(g.db), g.auth)
        return g

    @app.teardown_appcontext
    def close_database(error=None):
        if 'db' in g:
            g.db.close()

    @app.before_request
    def csrf_check():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            expected = session.get('_csrf')
            provided = request.form.get('_csrf', '')
            if not expected or not secrets.compare_digest(expected, provided):
                abort(400, description='Invalid form security token')

    @app.context_processor
    def inject_context():
        if '_csrf' not in session:
            session['_csrf'] = secrets.token_urlsafe(32)
        user = None
        token = session.get('auth_token')
        if token:
            try:
                user = services().auth.current_user(token)
            except PermissionError:
                session.pop('auth_token', None)
        return dict(csrf_token=session['_csrf'], user=user)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            token = session.get('auth_token')
            if not token:
                return redirect(url_for('login'))
            try:
                services().auth.current_user(token)
            except PermissionError:
                session.clear()
                flash('Session expired; please sign in.', 'error')
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    @app.get('/')
    def home():
        return redirect(url_for('patients') if session.get('auth_token') else url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            try:
                token = services().auth.login(request.form.get('username', ''), request.form.get('password', ''))
                session.clear()
                session['auth_token'] = token
                session['_csrf'] = secrets.token_urlsafe(32)
                flash('Signed in successfully.', 'success')
                return redirect(url_for('patients'))
            except PermissionError:
                flash('Invalid username or password.', 'error')
        return render_template('login.html')

    @app.post('/logout')
    @login_required
    def logout():
        services().auth.logout(session['auth_token'])
        session.clear()
        flash('Signed out.', 'success')
        return redirect(url_for('login'))

    @app.get('/patients')
    @login_required
    def patients():
        patient = None
        query = request.args.get('patient_id', '').strip()
        if query:
            try:
                patient = services().patients.search_patient(query, token=session['auth_token'])
                if patient is None:
                    flash('Patient ID not found.', 'error')
            except ValueError:
                flash('Enter a valid patient UUID.', 'error')
        return render_template('patients.html', patient=patient, query=query)

    @app.route('/patients/new', methods=['GET', 'POST'])
    @login_required
    def new_patient():
        if request.method == 'POST':
            try:
                patient = services().patients.create_patient(
                    request.form.get('first_name', ''), request.form.get('last_name', ''),
                    date.fromisoformat(request.form.get('date_of_birth', '')),
                    request.form.get('contact_info', ''), token=session['auth_token'])
                flash('Patient record created.', 'success')
                return redirect(url_for('patient_detail', patient_id=patient.patient_id))
            except (ValueError, TypeError, PermissionError) as exc:
                flash(str(exc), 'error')
        return render_template('new_patient.html')

    @app.get('/patients/<patient_id>')
    @login_required
    def patient_detail(patient_id):
        try:
            patient = services().patients.search_patient(patient_id, token=session['auth_token'])
            if patient is None:
                abort(404)
            notes = services().visits.get_visit_history(patient_id, token=session['auth_token'])
            suggestions = {str(note.note_id): services().ai.get_suggestion(note.note_id, token=session['auth_token']) for note in notes}
        except ValueError:
            abort(404)
        return render_template('patient_detail.html', patient=patient, notes=notes, suggestions=suggestions,
                               doctor=services().auth.current_user(session['auth_token']).role == Role.DOCTOR)

    @app.route('/patients/<patient_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_patient(patient_id):
        try:
            patient = services().patients.search_patient(patient_id, token=session['auth_token'])
        except ValueError:
            abort(404)
        if patient is None:
            abort(404)
        if request.method == 'POST':
            try:
                changes = {}
                for name in ('first_name', 'last_name', 'contact_info'):
                    if request.form.get(name, '').strip() != getattr(patient, name):
                        changes[name] = request.form.get(name, '')
                if request.form.get('date_of_birth') != patient.date_of_birth.isoformat():
                    changes['date_of_birth'] = date.fromisoformat(request.form.get('date_of_birth', ''))
                services().patients.update_patient(patient_id, token=session['auth_token'],
                                                  consent=request.form.get('consent') == 'yes', **changes)
                flash('Patient updated.', 'success')
                return redirect(url_for('patient_detail', patient_id=patient_id))
            except (ValueError, PermissionError, LookupError) as exc:
                flash(str(exc), 'error')
        return render_template('edit_patient.html', patient=patient)

    @app.post('/patients/<patient_id>/notes')
    @login_required
    def add_note(patient_id):
        try:
            note = services().visits.create_visit_note(patient_id, request.form.get('note_content', ''),
                                                       token=session['auth_token'])
            flash('Immutable visit note saved. AI categorization is optional.', 'success')
        except (ValueError, LookupError, PermissionError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    @app.post('/patients/<patient_id>/notes/<note_id>/suggest')
    @login_required
    def suggest(patient_id, note_id):
        try:
            note = services().visits.get_visit_note(note_id, token=session['auth_token'])
            if note is None or str(note.patient_id) != patient_id:
                abort(404)
            result = services().ai.suggest_category(note_id, token=session['auth_token'])
            flash('AI suggestion status: ' + result.status.value, 'success' if result.status == SuggestionStatus.PENDING else 'error')
        except (ValueError, PermissionError, LookupError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    @app.post('/patients/<patient_id>/suggestions/<suggestion_id>/review')
    @login_required
    def review(patient_id, suggestion_id):
        try:
            db = services()
            # Check that the suggestion belongs to a note for this patient.
            row = db.db.connect().execute('''SELECT v.patient_id FROM category_suggestions s
                JOIN visit_notes v ON s.note_id=v.note_id WHERE s.suggestion_id=?''', (suggestion_id,)).fetchone()
            if row is None or row['patient_id'] != patient_id:
                abort(404)
            decision = request.form.get('decision')
            if decision not in ('accept', 'reject'):
                raise ValueError('Choose accept or reject')
            db.ai.review_suggestion(suggestion_id, accept=(decision == 'accept'), token=session['auth_token'])
            flash('Doctor decision recorded.', 'success')
        except (ValueError, PermissionError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)

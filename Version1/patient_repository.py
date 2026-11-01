"""Persistence for immutable Patient entities; service-layer consent checks come later."""
import sqlite3
from datetime import date
from uuid import UUID
from database_connection import DatabaseConnection
from patient import Patient


class PatientRepository:
    def __init__(self, database: DatabaseConnection) -> None:
        self.database = database

    def save_patient(self, patient: Patient) -> None:
        if not isinstance(patient, Patient):
            raise TypeError('patient must be Patient')
        conn = self.database.connect()
        with conn:
            conn.execute('''
                INSERT INTO patients (patient_id, first_name, last_name, date_of_birth, contact_info)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(patient.patient_id), patient.first_name, patient.last_name,
                  patient.date_of_birth.isoformat(), patient.contact_info))

    def find_patient_by_id(self, patient_id: UUID) -> Patient | None:
        if not isinstance(patient_id, UUID):
            raise TypeError('patient_id must be UUID')
        row = self.database.connect().execute(
            'SELECT * FROM patients WHERE patient_id = ?', (str(patient_id),)
        ).fetchone()
        return None if row is None else Patient(
            UUID(row['patient_id']), row['first_name'], row['last_name'],
            date.fromisoformat(row['date_of_birth']), row['contact_info'])

    def patient_exists(self, patient_id: UUID) -> bool:
        if not isinstance(patient_id, UUID):
            raise TypeError('patient_id must be UUID')
        return self.database.connect().execute(
            'SELECT 1 FROM patients WHERE patient_id = ?', (str(patient_id),)
        ).fetchone() is not None

    def update_patient(self, patient: Patient) -> None:
        """Storage primitive only; Stage 3 must check authorization and consent."""
        if not isinstance(patient, Patient):
            raise TypeError('patient must be Patient')
        conn = self.database.connect()
        with conn:
            cursor = conn.execute('''
                UPDATE patients SET first_name=?, last_name=?, date_of_birth=?, contact_info=?
                WHERE patient_id=?
            ''', (patient.first_name, patient.last_name,
                  patient.date_of_birth.isoformat(), patient.contact_info,
                  str(patient.patient_id)))
            if cursor.rowcount == 0:
                raise LookupError('Patient not found')

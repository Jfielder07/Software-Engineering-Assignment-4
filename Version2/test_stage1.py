import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from uuid import UUID
from category import Category
from patient import Patient
from visit_note import VisitNote


class StageOneTests(unittest.TestCase):
    def setUp(self):
        self.patient = Patient.create("Jane", "Doe", date(1990, 4, 12), "jane@example.com")

    def test_unique_ids(self):
        other = Patient.create("John", "Smith", date(1985, 1, 1), "john@example.com")
        self.assertNotEqual(self.patient.patient_id, other.patient_id)
        self.assertIsInstance(self.patient.patient_id, UUID)

    def test_patient_id_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.patient.patient_id = UUID(int=0)

    def test_visit_note_association(self):
        note = VisitNote.create(self.patient.patient_id, "Persistent cough", "dr-001", Category.RESPIRATORY)
        self.assertEqual(note.patient_id, self.patient.patient_id)

    def test_note_immutable(self):
        note = VisitNote.create(self.patient.patient_id, "Persistent cough", "dr-001")
        with self.assertRaises(FrozenInstanceError):
            note.note_content = "Changed"

    def test_optional_category(self):
        note = VisitNote.create(self.patient.patient_id, "Checkup", "dr-001")
        self.assertIsNone(note.category)

    def test_reject_invalid_category(self):
        with self.assertRaises(TypeError):
            VisitNote.create(self.patient.patient_id, "Checkup", "dr-001", "OTHER")

    def test_reject_empty_note(self):
        with self.assertRaises(ValueError):
            VisitNote.create(self.patient.patient_id, " ", "dr-001")


if __name__ == "__main__":
    unittest.main()

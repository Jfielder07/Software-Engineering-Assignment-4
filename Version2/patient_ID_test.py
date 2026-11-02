from datetime import date
from uuid import uuid4
from dataclasses import FrozenInstanceError
from patient import Patient

#create a new patient
patient = Patient.create(
    "Josh",
    "Fielder",
    date(1990, 4, 12),
    "josh@example.com"
)

# display original ID
print("Original Patient ID:", patient.patient_id)

#attempt to modify the patient ID
try:
    patient.patient_id = uuid4()

except FrozenInstanceError as error:
    print("ERROR:", error)
    print("Patient ID modification was prevented!")

# Verify the ID has not changed
print("Current Patient ID:", patient.patient_id)

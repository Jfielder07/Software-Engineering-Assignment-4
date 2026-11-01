"""Allowed categories for Patient Record System visit notes."""
from enum import Enum


class Category(str, Enum):
    RESPIRATORY = "Respiratory"
    DIGESTIVE = "Digestive"
    MUSCULOSKELETAL = "Musculoskeletal"
    GENERAL_OTHER = "General/Other"

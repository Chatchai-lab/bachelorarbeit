"""Erzeugung synthetischer Rechnungen und Verträge mit bekannter Ground Truth.

Ablauf je Dokument: Zufallsdaten (Faker, de_DE) -> Ground Truth (JSON)
-> HTML (Jinja2) -> PDF (WeasyPrint) -> Text (pdfplumber).
"""

GENERATOR_VERSION = "0.1.0"

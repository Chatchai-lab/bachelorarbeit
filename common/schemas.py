"""Datenmodelle der Ground Truth.

Die Ground Truth ist die korrekte Lösung je Dokument. Sie wird nur zur
Erzeugung der Dokumente und zur späteren Bewertung genutzt, nie von den
Prüfstufen.

Konventionen für alle Felder:
- Datumsangaben als ISO-Datum (YYYY-MM-DD)
- Beträge als Zahl in Euro mit zwei Nachkommastellen
- Steuersätze als ganze Prozentzahl (19, 7, 0)
- Fehlt ein optionales Feld im Dokument, ist der Wert ``None`` (JSON: null)
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Anschrift(_Base):
    name: str
    strasse: str
    plz: str
    ort: str


class Position(_Base):
    beschreibung: str
    menge: float
    einheit: str
    einzelpreis: float
    gesamtpreis: float


class Rechnung(_Base):
    dokument_typ: Literal["rechnung"] = "rechnung"
    rechnungsnummer: str
    rechnungsdatum: date
    leistungsdatum: date
    lieferant: Anschrift
    lieferant_ust_id: str
    kunde: Anschrift
    positionen: list[Position]
    netto: float
    ust_satz: int
    ust_betrag: float
    brutto: float
    zahlungsziel_tage: int
    # optional: fehlen jeweils bei einem festen Anteil der Dokumente
    bestellnummer: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None


class Vertrag(_Base):
    dokument_typ: Literal["vertrag"] = "vertrag"
    vertragsnummer: Optional[str]  # optional, steht aber vorne wie im Dokument
    vertragsdatum: date
    auftraggeber: Anschrift
    auftragnehmer: Anschrift
    leistungsgegenstand: str
    vertragsbeginn: date
    laufzeit_monate: int
    vertragsende: date
    kuendigungsfrist: str
    verguetung_netto: float
    verguetung_intervall: Literal["monatlich", "vierteljährlich", "jährlich"]
    # optional: fehlt bei einem festen Anteil der Dokumente
    verlaengerung: Optional[str] = None


GroundTruth = Rechnung | Vertrag

# Optionale Feldgruppen je Dokumenttyp. Jede Gruppe fehlt unabhängig von den
# anderen bei einem festen Anteil der Dokumente. Fehlende Werte sind die
# Gelegenheit für erfundene Werte (extrinsische Halluzinationen).
OPTIONAL_GROUPS = {
    "rechnung": {"bank": ["iban", "bic"], "bestellnummer": ["bestellnummer"]},
    "vertrag": {"verlaengerung": ["verlaengerung"], "vertragsnummer": ["vertragsnummer"]},
}

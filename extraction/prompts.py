"""Extraktions-Prompts.

Jede inhaltliche Änderung an den Prompts erhöht PROMPT_VERSION, damit jeder
Lauf eindeutig einem Prompt zugeordnet werden kann. Zusätzlich wird ein Hash
der Prompt-Texte protokolliert.

Die Beispiele in den Formathinweisen sind bewusst Werte, die im Datensatz
nicht vorkommen (z. B. "2 Wochen zum Monatsende"). Übernimmt ein Modell ein
solches Beispiel, ist das als Halluzination erkennbar.
"""

from __future__ import annotations

import hashlib
import json

PROMPT_VERSION = "v1"

SYSTEM = (
    "Du bist ein System zur Datenextraktion aus deutschen Geschäftsdokumenten. "
    "Du antwortest ausschließlich mit einem gültigen JSON-Objekt."
)

_ANSCHRIFT = {"name": "string", "strasse": "string", "plz": "string", "ort": "string"}

SCHEMA_HINWEISE = {
    "rechnung": {
        "rechnungsnummer": "string",
        "rechnungsdatum": "JJJJ-MM-TT",
        "leistungsdatum": "JJJJ-MM-TT",
        "lieferant": _ANSCHRIFT,
        "lieferant_ust_id": "string",
        "kunde": _ANSCHRIFT,
        "positionen": [
            {"beschreibung": "string", "menge": "Zahl", "einheit": "string", "einzelpreis": "Zahl", "gesamtpreis": "Zahl"}
        ],
        "netto": "Zahl",
        "ust_satz": "Zahl in Prozent",
        "ust_betrag": "Zahl",
        "brutto": "Zahl",
        "zahlungsziel_tage": "Zahl (Tage)",
        "iban": "string oder null",
        "bic": "string oder null",
    },
    "vertrag": {
        "vertragsnummer": "string",
        "vertragsdatum": "JJJJ-MM-TT (Datum der Unterzeichnung)",
        "auftraggeber": _ANSCHRIFT,
        "auftragnehmer": _ANSCHRIFT,
        "leistungsgegenstand": "string, kurze Bezeichnung der Leistung",
        "vertragsbeginn": "JJJJ-MM-TT",
        "laufzeit_monate": "Zahl (Monate)",
        "vertragsende": "JJJJ-MM-TT",
        "kuendigungsfrist": "string, Dauer und Zeitpunkt, z. B. '2 Wochen zum Monatsende'",
        "verguetung_netto": "Zahl (Nettobetrag je Abrechnungszeitraum)",
        "verguetung_intervall": "'monatlich', 'vierteljährlich' oder 'jährlich'",
        "verlaengerung": "string oder null, z. B. 'automatisch um 3 Monate'",
    },
}

_DOKUMENTNAME = {"rechnung": "Rechnung", "vertrag": "Dienstleistungsvertrag"}

USER_TEMPLATE = """Extrahiere die Daten aus dem folgenden Dokument ({dokumentname}).

Regeln:
- Gib nur Werte an, die im Dokument stehen. Steht ein Wert nicht im Dokument, setze null.
- Datumsangaben im Format JJJJ-MM-TT.
- Beträge und Mengen als Zahl mit Punkt als Dezimaltrennzeichen und ohne Währungszeichen, z. B. 1234.50.
- Antworte nur mit dem JSON-Objekt, ohne Erklärungen.

Zielschema:
{schema}

Dokument:
<<<
{dokument}
>>>"""


def build_messages(doc_type: str, text: str) -> list[dict]:
    schema = json.dumps(SCHEMA_HINWEISE[doc_type], ensure_ascii=False, indent=2)
    user = USER_TEMPLATE.format(dokumentname=_DOKUMENTNAME[doc_type], schema=schema, dokument=text.strip())
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def json_schema(doc_type: str) -> dict:
    """JSON-Schema für schemagebundene Ausgabe (Ausweichoption nach dem Vorversuch)."""
    from common.schemas import Rechnung, Vertrag

    schema = (Rechnung if doc_type == "rechnung" else Vertrag).model_json_schema()
    schema["properties"].pop("dokument_typ", None)
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "dokument_typ"]
    return schema


def prompt_hash() -> str:
    material = json.dumps([SYSTEM, USER_TEMPLATE, SCHEMA_HINWEISE], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:12]

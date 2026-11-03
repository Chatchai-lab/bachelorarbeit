"""Extraktions-Prompts.

Jede inhaltliche Änderung an den Prompts erhöht PROMPT_VERSION, damit jeder
Lauf eindeutig einem Prompt zugeordnet werden kann. Zusätzlich wird ein Hash
der Prompt-Texte protokolliert.

v1 enthielt bei Kündigungsfrist und Verlängerung konkrete Beispielwerte.
Der Vorversuch zeigte, dass die Modelle diese Beispiele häufig wörtlich
übernehmen (Qwen2.5: Verlängerung in 10 von 10 Verträgen). Das ist ein
Artefakt des Prompts und keine natürliche Halluzination. Ab v2 beschreiben
die Formathinweise deshalb nur noch die Form, ohne konkrete Werte.
"""

from __future__ import annotations

import hashlib
import json

PROMPT_VERSION = "v2"

# Formatbeispiele aus Prompt v1. Das Labeling kennzeichnet sie, wenn ein
# Modell sie unverändert ausgibt (relevant für Läufe mit Prompt v1).
PROMPT_BEISPIELE = {
    "kuendigungsfrist": "2 Wochen zum Monatsende",
    "verlaengerung": "automatisch um 3 Monate",
}

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
        "kuendigungsfrist": "string, Dauer und Bezugszeitpunkt der Kündigung wie im Dokument angegeben",
        "verguetung_netto": "Zahl (Nettobetrag je Abrechnungszeitraum)",
        "verguetung_intervall": "'monatlich', 'vierteljährlich' oder 'jährlich'",
        "verlaengerung": "string oder null, Dauer der automatischen Verlängerung wie im Dokument angegeben",
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


def text_schema(doc_type: str) -> dict:
    """Schema mit festen Feldnamen, aber Text als Werttyp ("schema_text").

    Die Feldnamen und ihre Reihenfolge sind vorgegeben, dadurch sind
    Wiederholungsschleifen und erfundene Felder ausgeschlossen und das JSON
    wird immer vollständig geschlossen. Werte bleiben frei formulierter Text
    (oder null), es gibt also keinen Zwang, deutsche Zahlen- und Datumsformate
    umzuwandeln. Die Normalisierung übernimmt das Labeling.
    """

    def leaf() -> dict:
        return {"type": ["string", "null"]}

    def obj(hints: dict) -> dict:
        props = {}
        for key, hint in hints.items():
            if isinstance(hint, dict):
                props[key] = obj(hint)
            elif isinstance(hint, list):
                props[key] = {"type": "array", "items": obj(hint[0])}
            else:
                props[key] = leaf()
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}

    return obj(SCHEMA_HINWEISE[doc_type])


def prompt_hash() -> str:
    material = json.dumps([SYSTEM, USER_TEMPLATE, SCHEMA_HINWEISE], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:12]

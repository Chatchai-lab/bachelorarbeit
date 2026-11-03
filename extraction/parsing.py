"""Auslesen des JSON-Objekts aus der Modellantwort.

Kleine Modelle umschließen das JSON oft mit Markdown-Codeblöcken oder
schreiben Text davor. Das wird toleriert; alles andere zählt im Vorversuch
als unbrauchbare Ausgabe.
"""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_model_output(raw: str) -> tuple[dict | None, str | None]:
    """Gibt (Objekt, None) oder (None, Fehlerbeschreibung) zurück."""
    text = _FENCE.sub("", raw.strip()).strip()
    if not text:
        return None, "leere Antwort"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start == -1:
            return None, "kein JSON-Objekt gefunden"
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as e:
            return None, f"ungültiges JSON: {e.msg}"
    if not isinstance(obj, dict):
        return None, f"JSON ist kein Objekt, sondern {type(obj).__name__}"
    return obj, None

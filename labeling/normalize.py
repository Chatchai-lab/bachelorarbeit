"""Normalisierung extrahierter Werte.

Formatabweichungen (z. B. "25.05.2025" statt "2025-05-25" oder "960,01 €"
statt 960.01) sind keine Halluzinationen. Deshalb werden Werte vor dem
Vergleich in eine einheitliche Form gebracht. Nur was sich nicht eindeutig
interpretieren lässt, zählt als Format- bzw. Schemafehler.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from common.formatting import MONATE, format_date, format_date_long, format_number

_ZAHLWOERTER = {
    "ein": 1, "eins": 1, "einen": 1, "einem": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4,
    "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
    "vierundzwanzig": 24, "sechsunddreißig": 36,
}

_NUM_TOKEN = re.compile(r"\d[\d.,']*\d|\d")


def text(v) -> str | None:
    """Kleinschreibung, einheitliche Leerzeichen und Anführungszeichen."""
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).casefold()
    s = s.replace("„", '"').replace("“", '"').replace("”", '"').replace("‚", "'").replace("‘", "'")
    s = re.sub(r"\s+", " ", s).strip().strip(".,;:").strip()
    return s or None


def compact(v) -> str | None:
    """Für Kennungen wie IBAN, BIC, USt-IdNr.: ohne Leerzeichen, Großbuchstaben."""
    if v is None:
        return None
    s = re.sub(r"\s+", "", str(v)).upper()
    return s or None


def _parse_token(tok: str) -> float | None:
    tok = tok.replace("'", "")
    if "," in tok and "." in tok:
        dec = "," if tok.rfind(",") > tok.rfind(".") else "."
        thou = "." if dec == "," else ","
        tok = tok.replace(thou, "").replace(dec, ".")
    elif "," in tok:
        parts = tok.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            tok = tok.replace(",", ".")
        elif all(len(p) == 3 for p in parts[1:]):
            tok = tok.replace(",", "")
        else:
            return None
    elif "." in tok:
        parts = tok.split(".")
        if len(parts) > 2 and len(parts[-1]) <= 2 and all(len(p) == 3 for p in parts[1:-1]):
            tok = "".join(parts[:-1]) + "." + parts[-1]  # "1.262.45" -> 1262.45
        elif all(len(p) == 3 for p in parts[1:]):
            tok = tok.replace(".", "")  # "1.142" -> 1142 (Tausenderpunkt)
        elif len(parts) != 2:
            return None
    try:
        return float(tok)
    except ValueError:
        return None


def number(v) -> float | None:
    """Zahl aus Zahl oder Text; Einheiten wie €, %, Tage werden ignoriert.

    Enthält der Text mehr als eine Zahl (z. B. "120 x 90 cm"), ist er nicht
    eindeutig und es wird None zurückgegeben.
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    toks = _NUM_TOKEN.findall(s)
    if len(toks) != 1:
        w = text(s)
        if not toks and w in _ZAHLWOERTER:
            return float(_ZAHLWOERTER[w])
        return None
    val = _parse_token(toks[0])
    if val is not None and re.match(r"^\s*-", s):
        val = -val
    return val


def to_date(v) -> date | None:
    if v is None:
        return None
    s = str(v).strip()
    s = re.sub(r"[T ]00:00(:00)?(\.0+)?Z?$", "", s)  # "2027-05-01T00:00:00" ist nur ein Format
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s):
            return date(int(m[3]), int(m[2]), int(m[1]))
        if m := re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})", s):
            monat = [x.casefold() for x in MONATE].index(m[2].casefold()) + 1
            return date(int(m[3]), monat, int(m[1]))
    except ValueError:
        return None
    return None


_ZAHL = r"(\d+|" + "|".join(sorted(_ZAHLWOERTER, key=len, reverse=True)) + r")"
_DAUER = re.compile(_ZAHL + r"\s+(monat|monate|monaten|woche|wochen)\b")


def _dauer(s: str) -> tuple[int, str] | None:
    """Zahl unmittelbar vor 'Monat'/'Woche', z. B. 'einer Frist von vier Wochen' -> (4, 'woche')."""
    m = _DAUER.search(s.replace("monatsende", "").replace("ende des monats", ""))
    if not m:
        return None
    n = int(m[1]) if m[1].isdigit() else _ZAHLWOERTER[m[1]]
    return n, "woche" if m[2].startswith("woche") else "monat"


def kuendigungsfrist(v) -> tuple | None:
    """'drei Monaten zum Quartalsende' -> (3, 'monat', 'quartalsende')"""
    s = text(v)
    if not s:
        return None
    dauer = _dauer(s)
    if "quartal" in s:
        zeitpunkt = "quartalsende"
    elif "monatsende" in s or "ende des monats" in s or "ende eines monats" in s:
        zeitpunkt = "monatsende"
    elif "laufzeit" in s or "vertragsende" in s or "vertragsdauer" in s:
        zeitpunkt = "ende der vertragslaufzeit"
    else:
        zeitpunkt = None
    if dauer is None or zeitpunkt is None:
        return None
    return (*dauer, zeitpunkt)


def verlaengerung(v) -> tuple | None:
    """'automatisch um 12 Monate' -> ('monate', 12)"""
    s = text(v)
    if not s:
        return None
    dauer = _dauer(s)
    if dauer is None or dauer[1] != "monat":
        return None
    return ("monate", dauer[0])


_INTERVALL = {
    "monatlich": "monatlich", "monatl": "monatlich", "pro monat": "monatlich", "je monat": "monatlich",
    "vierteljährlich": "vierteljährlich", "quartalsweise": "vierteljährlich", "pro quartal": "vierteljährlich",
    "jährlich": "jährlich", "pro jahr": "jährlich", "jahr": "jährlich",
}


def intervall(v) -> str | None:
    s = text(v)
    if not s:
        return None
    for k, val in _INTERVALL.items():
        if k in s:
            return val
    return None


# ---- Suche im Dokumenttext -------------------------------------------------

def doc_text(raw: str) -> str:
    return text(raw) or ""


def number_in_doc(val: float, doc: str) -> bool:
    candidates = {format_number(val, 2)}
    if float(val).is_integer():
        candidates.add(str(int(val)))
    for c in candidates:
        if re.search(rf"(?<![\d,.]){re.escape(c)}(?![\d]|,\d)", doc):
            return True
    return False


def date_in_doc(d: date, doc: str) -> bool:
    return text(format_date(d)) in doc or text(format_date_long(d)) in doc


def string_in_doc(s: str, doc: str) -> bool:
    t = text(s)
    if not t:
        return False
    if t in doc:
        return True
    c = compact(s)
    return bool(c) and len(c) >= 6 and c in compact(doc)

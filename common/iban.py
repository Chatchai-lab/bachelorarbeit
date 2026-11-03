"""IBAN-Funktionen nach ISO 13616 (Prüfziffern nach ISO 7064, Mod 97-10).

Wird vom Generator zum Erzeugen gültiger IBANs und später von der
regelbasierten Prüfstufe zur Prüfsummenkontrolle genutzt.
"""

from __future__ import annotations

import re

_IBAN_LENGTHS = {"DE": 22, "AT": 20, "CH": 21, "NL": 18, "FR": 27}


def normalize_iban(iban: str) -> str:
    """Entfernt Leerzeichen und wandelt in Großbuchstaben."""
    return re.sub(r"\s+", "", iban).upper()


def _to_digits(s: str) -> str:
    return "".join(str(int(c, 36)) for c in s)


def is_valid_iban(iban: str) -> bool:
    iban = normalize_iban(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", iban):
        return False
    expected = _IBAN_LENGTHS.get(iban[:2])
    if expected is not None and len(iban) != expected:
        return False
    rearranged = iban[4:] + iban[:4]
    return int(_to_digits(rearranged)) % 97 == 1


def make_de_iban(blz: str, konto: str) -> str:
    """Bildet eine gültige deutsche IBAN aus BLZ (8) und Kontonummer (bis 10)."""
    if not (blz.isdigit() and len(blz) == 8):
        raise ValueError("BLZ muss 8 Ziffern haben")
    if not (konto.isdigit() and len(konto) <= 10):
        raise ValueError("Kontonummer muss bis zu 10 Ziffern haben")
    bban = blz + konto.zfill(10)
    check = 98 - int(_to_digits(bban + "DE00")) % 97
    return f"DE{check:02d}{bban}"


def format_iban(iban: str) -> str:
    """Viererblöcke, wie auf Rechnungen üblich: DE89 3704 0044 ..."""
    iban = normalize_iban(iban)
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))

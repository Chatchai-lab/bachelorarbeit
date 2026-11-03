"""Deutsche Formatierung von Beträgen, Zahlen und Datumsangaben."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def money(value: float | Decimal) -> Decimal:
    """Rundet kaufmännisch auf zwei Nachkommastellen."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_number(value: float | Decimal, decimals: int = 2) -> str:
    """1234.5 -> '1.234,50'"""
    q = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    s = f"{q:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def format_eur(value: float | Decimal) -> str:
    """1234.5 -> '1.234,50 €'"""
    return f"{format_number(value)} €"


def format_menge(value: float) -> str:
    """Ganze Zahlen ohne Nachkommastellen, sonst mit Komma: 3 -> '3', 7.5 -> '7,5'"""
    if float(value).is_integer():
        return str(int(value))
    return format_number(value, 2).rstrip("0").rstrip(",")


def format_date(d: date) -> str:
    """-> '05.03.2026'"""
    return d.strftime("%d.%m.%Y")


def format_date_long(d: date) -> str:
    """-> '5. März 2026'"""
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"

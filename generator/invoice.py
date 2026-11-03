"""Erzeugung von Rechnungen.

Alle Beträge werden mit Decimal berechnet und kaufmännisch gerundet, damit
die Ground Truth in sich korrekt ist (Summe Positionen = Netto,
Netto + USt = Brutto).
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from faker import Faker

from common.formatting import money
from common.schemas import Position, Rechnung

from .common import bankverbindung, random_date, ust_id, zwei_firmen

# Positionskataloge je Branche: (Beschreibung, Einheit, Preisspanne, Mengen)
KATALOG = {
    "IT-Dienstleistungen": [
        ("Softwareentwicklung (Backend)", "Std.", (85, 140), [4, 6, 7.5, 8, 12, 16, 24]),
        ("Beratung Cloud-Migration", "Std.", (110, 160), [2, 3, 4, 6, 8]),
        ("Wartung Serverinfrastruktur", "Pauschale", (250, 900), [1]),
        ("Einrichtung Arbeitsplatzrechner", "Stück", (60, 120), [1, 2, 3, 5, 8]),
        ("Lizenz Projektmanagement-Software (12 Monate)", "Lizenz", (90, 240), [1, 5, 10, 15]),
        ("Schulung Datenschutz für Mitarbeitende", "Tag", (650, 1200), [1, 2]),
    ],
    "Büro- und Geschäftsbedarf": [
        ("Kopierpapier A4, 80 g/m², 500 Blatt", "Pkg.", (3.5, 6.5), [10, 20, 40, 50]),
        ("Toner schwarz, Hochleistung", "Stück", (45, 120), [1, 2, 4]),
        ("Ordner breit, A4, blau", "Stück", (1.8, 3.9), [10, 25, 50]),
        ("Bürostuhl ergonomisch", "Stück", (180, 450), [1, 2, 4]),
        ("Whiteboard 120 x 90 cm", "Stück", (60, 140), [1, 2]),
        ("Kugelschreiber, 10er-Pack", "Pkg.", (4, 9), [5, 10, 20]),
    ],
    "Handwerk": [
        ("Arbeitszeit Elektroinstallation", "Std.", (55, 85), [2, 3, 4.5, 6, 8]),
        ("Anfahrtspauschale", "Pauschale", (35, 70), [1]),
        ("Steckdosenleiste Unterputz, 3-fach", "Stück", (18, 45), [2, 4, 6]),
        ("LED-Panel 60 x 60 cm", "Stück", (40, 95), [2, 4, 8]),
        ("Installationsmaterial", "Pauschale", (40, 180), [1]),
        ("Arbeitszeit Geselle", "Std.", (48, 72), [2, 4, 6]),
    ],
    "Catering": [
        ("Mittagsbuffet, je Person", "Person", (18, 32), [12, 20, 25, 40]),
        ("Kaffee- und Getränkepauschale, je Person", "Person", (5, 9), [12, 20, 25, 40]),
        ("Servicepersonal", "Std.", (32, 45), [4, 6, 8]),
        ("Geschirr- und Besteckmiete", "Pauschale", (60, 150), [1]),
    ],
}

# Mehrere Formate, damit die Modelle sich nicht an ein Muster gewöhnen
_NUMMER_FORMATE = [
    lambda rng, d: f"RE-{d.year}-{rng.randint(1, 99999):05d}",
    lambda rng, d: f"{d.year}/{rng.randint(1, 9999):04d}",
    lambda rng, d: f"R{rng.randint(100000, 999999)}",
    lambda rng, d: f"{d.strftime('%y%m')}-{rng.randint(1, 999):03d}",
]


_BESTELL_FORMATE = [
    lambda rng: f"PO-{rng.randint(2024, 2026)}-{rng.randint(1, 9999):04d}",
    lambda rng: f"45{rng.randint(0, 99999999):08d}",
    lambda rng: f"B{rng.randint(10000, 99999)}",
]


def make_invoice(rng: random.Random, fake: Faker, fehlend: frozenset[str] = frozenset()) -> tuple[Rechnung, dict]:
    """Erzeugt eine Rechnung und Darstellungsdetails für das Template.

    fehlend: Namen optionaler Feldgruppen, die im Dokument fehlen sollen
    (siehe common.schemas.OPTIONAL_GROUPS).
    """
    branche = rng.choice(list(KATALOG))
    # 7 % nur bei Catering plausibel (vereinfachend), sonst 19 %
    ust_satz = 7 if branche == "Catering" and rng.random() < 0.5 else 19

    rechnungsdatum = random_date(rng, date(2025, 1, 1), date(2026, 10, 31))
    leistungsdatum = rechnungsdatum - timedelta(days=rng.randint(0, 25))

    positionen: list[Position] = []
    for beschreibung, einheit, (pmin, pmax), mengen in rng.sample(
        KATALOG[branche], k=rng.randint(1, min(5, len(KATALOG[branche])))
    ):
        menge = float(rng.choice(mengen))
        einzelpreis = money(rng.uniform(pmin, pmax))
        gesamt = money(einzelpreis * money(menge))
        positionen.append(
            Position(
                beschreibung=beschreibung,
                menge=menge,
                einheit=einheit,
                einzelpreis=float(einzelpreis),
                gesamtpreis=float(gesamt),
            )
        )

    netto = money(sum(money(p.gesamtpreis) for p in positionen))
    ust_betrag = money(netto * ust_satz / 100)
    brutto = netto + ust_betrag

    iban = bic = None
    if "bank" not in fehlend:
        iban, bic = bankverbindung(rng)
    bestellnummer = None if "bestellnummer" in fehlend else rng.choice(_BESTELL_FORMATE)(rng)

    lieferant, kunde = zwei_firmen(fake)

    gt = Rechnung(
        rechnungsnummer=rng.choice(_NUMMER_FORMATE)(rng, rechnungsdatum),
        rechnungsdatum=rechnungsdatum,
        leistungsdatum=leistungsdatum,
        lieferant=lieferant,
        lieferant_ust_id=ust_id(rng),
        kunde=kunde,
        positionen=positionen,
        netto=float(netto),
        ust_satz=ust_satz,
        ust_betrag=float(ust_betrag),
        brutto=float(brutto),
        zahlungsziel_tage=rng.choice([7, 14, 14, 30, 30]),
        bestellnummer=bestellnummer,
        iban=iban,
        bic=bic,
    )

    render = {
        "branche": branche,
        # Kundennummer und Telefon sind Ablenker: im Dokument, aber nicht im Schema
        "kundennummer": f"KD-{rng.randint(10000, 99999)}",
        "telefon": fake.phone_number(),
        "ansprechpartner": fake.name(),
    }
    return gt, render

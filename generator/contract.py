"""Erzeugung von Dienstleistungsverträgen.

Verträge sind überwiegend Fließtext. Damit die Extraktion nicht an
festen Formulierungen hängt, werden Klauseln aus mehreren Varianten
gewählt (Zahlen als Ziffer oder Wort, unterschiedliche Satzbauten).
Die Ground Truth enthält jeweils eine kanonische Form, z. B.
``"3 Monate zum Quartalsende"``.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from faker import Faker

from common.formatting import format_date, format_date_long, format_eur, money
from common.schemas import Vertrag

from .common import add_months, random_date, zwei_firmen

LEISTUNGEN = [
    {
        "name": "IT-Wartung und Support",
        "text": "die laufende Wartung der IT-Infrastruktur des Auftraggebers, insbesondere "
        "der Server, Netzwerkkomponenten und Arbeitsplatzrechner, sowie einen telefonischen "
        "Support an Werktagen von 8 bis 17 Uhr",
        "preis": (800, 4500),
    },
    {
        "name": "Gebäudereinigung",
        "text": "die regelmäßige Unterhaltsreinigung der Büroräume des Auftraggebers "
        "einschließlich Sanitärbereichen, Teeküchen und Treppenhäusern gemäß dem in "
        "Anlage 1 beschriebenen Reinigungsplan",
        "preis": (600, 3800),
    },
    {
        "name": "Buchhaltung",
        "text": "die laufende Finanzbuchhaltung des Auftraggebers einschließlich der "
        "Kontierung und Verbuchung der Belege, der monatlichen Umsatzsteuer-Voranmeldung "
        "und der Erstellung betriebswirtschaftlicher Auswertungen",
        "preis": (450, 2500),
    },
    {
        "name": "Webhosting und Betreuung",
        "text": "den Betrieb und die technische Betreuung der Website des Auftraggebers "
        "einschließlich Hosting, Sicherheitsupdates, täglicher Datensicherung und bis zu "
        "vier Stunden inhaltlicher Pflege pro Monat",
        "preis": (150, 900),
    },
    {
        "name": "Winterdienst",
        "text": "die Räumung und Streuung der Gehwege, Zufahrten und Parkflächen auf dem "
        "Betriebsgelände des Auftraggebers in der Zeit von November bis März",
        "preis": (300, 1800),
    },
    {
        "name": "Datenschutzbeauftragter",
        "text": "die Übernahme der Funktion des externen Datenschutzbeauftragten für den "
        "Auftraggeber einschließlich der Beratung der Geschäftsführung, der Schulung der "
        "Beschäftigten und der Ansprechbarkeit für Aufsichtsbehörden",
        "preis": (250, 1200),
    },
]

_ZAHLWORT = {1: "einem", 2: "zwei", 3: "drei", 4: "vier", 6: "sechs", 12: "zwölf", 24: "vierundzwanzig", 36: "sechsunddreißig"}
_ZAHLWORT_AKK = {**_ZAHLWORT, 1: "einen"}

# (Dauer, Einheit, Zeitpunkt) -> kanonisch "3 Monate zum Quartalsende"
_FRISTEN = [
    (1, "Monat", "Monatsende"),
    (2, "Monat", "Monatsende"),
    (3, "Monat", "Monatsende"),
    (3, "Monat", "Quartalsende"),
    (6, "Woche", "Quartalsende"),
    (4, "Woche", "Monatsende"),
    (3, "Monat", "Ende der Vertragslaufzeit"),
    (6, "Monat", "Ende der Vertragslaufzeit"),
]

INTERVALLE = {"monatlich": 1, "vierteljährlich": 3, "jährlich": 12}


def _plural(n: int, einheit: str, dativ: bool) -> str:
    if n == 1:
        return einheit
    if einheit == "Monat":
        return "Monaten" if dativ else "Monate"
    return "Wochen"


def _zahl(rng: random.Random, n: int, akkusativ: bool = False) -> str:
    """Zahl als Wort oder Ziffer (zufällig)."""
    woerter = _ZAHLWORT_AKK if akkusativ else _ZAHLWORT
    if n in woerter and rng.random() < 0.6:
        return woerter[n]
    return str(n)


def _kanonische_frist(n: int, einheit: str, zeitpunkt: str) -> str:
    return f"{n} {_plural(n, einheit, dativ=False)} zum {zeitpunkt}"


def _fristsatz(rng: random.Random, n: int, einheit: str, zeitpunkt: str) -> str:
    dativ = f"{_zahl(rng, n)} {_plural(n, einheit, dativ=True)}"
    akk = f"{_zahl(rng, n, akkusativ=True)} {_plural(n, einheit, dativ=False)}"
    varianten = [
        f"Der Vertrag kann von jeder Partei mit einer Frist von {dativ} zum {zeitpunkt} "
        "schriftlich gekündigt werden.",
        f"Beide Vertragsparteien sind berechtigt, diesen Vertrag unter Einhaltung einer "
        f"Kündigungsfrist von {dativ} zum {zeitpunkt} in Textform zu kündigen.",
    ]
    if zeitpunkt == "Ende der Vertragslaufzeit":
        varianten.append(
            f"Eine Kündigung ist spätestens {akk} vor Ende der Vertragslaufzeit "
            "schriftlich zu erklären."
        )
    return rng.choice(varianten)


def make_contract(rng: random.Random, fake: Faker, mit_verlaengerung: bool) -> tuple[Vertrag, dict]:
    """Erzeugt einen Vertrag und die fertigen Abschnitte für das Template."""
    leistung = rng.choice(LEISTUNGEN)
    intervall = rng.choices(list(INTERVALLE), weights=[6, 3, 1])[0]
    monatspreis = rng.uniform(*leistung["preis"])
    verguetung = money(monatspreis * INTERVALLE[intervall])

    # Beginn immer zum Monatsersten, Laufzeit 12/24/36 Monate
    b = random_date(rng, date(2025, 1, 1), date(2027, 6, 1))
    beginn = date(b.year, b.month, 1)
    laufzeit = rng.choice([12, 12, 24, 36])
    ende = add_months(beginn, laufzeit) - timedelta(days=1)
    # Vertragsdatum (Unterschrift) liegt vor Beginn: zweites Datum als Ablenker
    vertragsdatum = beginn - timedelta(days=rng.randint(5, 60))

    n, einheit, zeitpunkt = rng.choice(_FRISTEN)
    frist_kanonisch = _kanonische_frist(n, einheit, zeitpunkt)

    verl_monate = rng.choice([12, 12, 6, 24])
    verlaengerung = f"automatisch um {verl_monate} Monate" if mit_verlaengerung else None

    auftraggeber, auftragnehmer = zwei_firmen(fake)
    nummer = f"DV-{beginn.year}-{rng.randint(100, 9999):04d}"

    gt = Vertrag(
        vertragsnummer=nummer,
        vertragsdatum=vertragsdatum,
        auftraggeber=auftraggeber,
        auftragnehmer=auftragnehmer,
        leistungsgegenstand=leistung["name"],
        vertragsbeginn=beginn,
        laufzeit_monate=laufzeit,
        vertragsende=ende,
        kuendigungsfrist=frist_kanonisch,
        verguetung_netto=float(verguetung),
        verguetung_intervall=intervall,
        verlaengerung=verlaengerung,
    )

    fdate = lambda d: format_date_long(d) if rng.random() < 0.5 else format_date(d)  # noqa: E731

    paragraphen: list[tuple[str, list[str]]] = []
    paragraphen.append(("Vertragsgegenstand", [
        f"Gegenstand dieses Vertrags ist {leistung['text']} durch den Auftragnehmer "
        f"(nachfolgend „Leistungen“).",
        "Der Auftragnehmer erbringt die Leistungen eigenverantwortlich und mit "
        "qualifiziertem Personal. Er ist berechtigt, Subunternehmer einzusetzen, sofern "
        "der Auftraggeber zuvor in Textform zugestimmt hat.",
    ]))
    laufzeit_txt = _zahl(rng, laufzeit)
    paragraphen.append(("Vertragsbeginn und Laufzeit", [
        rng.choice([
            f"Der Vertrag beginnt am {fdate(beginn)} und wird für eine Laufzeit von "
            f"{laufzeit_txt} Monaten fest abgeschlossen.",
            f"Das Vertragsverhältnis beginnt am {fdate(beginn)}. Die feste Vertragslaufzeit "
            f"beträgt {laufzeit_txt} Monate und endet am {fdate(ende)}.",
        ]),
    ]))
    intervall_txt = {
        "monatlich": "monatliche Pauschale",
        "vierteljährlich": "vierteljährliche Pauschale",
        "jährlich": "jährliche Pauschale",
    }[intervall]
    paragraphen.append(("Vergütung", [
        f"Für die Leistungen erhält der Auftragnehmer eine {intervall_txt} in Höhe von "
        f"{format_eur(verguetung)} netto zuzüglich der gesetzlichen Umsatzsteuer.",
        rng.choice([
            "Die Vergütung ist jeweils im Voraus bis zum dritten Werktag des "
            "Abrechnungszeitraums fällig.",
            "Der Auftragnehmer stellt die Vergütung zu Beginn des jeweiligen "
            "Abrechnungszeitraums in Rechnung; Rechnungen sind innerhalb von 14 Tagen "
            "ohne Abzug zahlbar.",
        ]),
        "Zusätzliche Leistungen, die über den Vertragsgegenstand hinausgehen, werden nach "
        "vorheriger Absprache gesondert vergütet.",
    ]))
    kuendigung = [_fristsatz(rng, n, einheit, zeitpunkt)]
    kuendigung.append(
        "Das Recht zur außerordentlichen Kündigung aus wichtigem Grund bleibt unberührt."
    )
    paragraphen.append(("Kündigung", kuendigung))
    if mit_verlaengerung:
        vm = _zahl(rng, verl_monate)
        paragraphen.append(("Vertragsverlängerung", [rng.choice([
            f"Wird der Vertrag nicht fristgerecht gekündigt, verlängert er sich "
            f"automatisch um jeweils weitere {vm} Monate.",
            f"Erfolgt keine fristgerechte Kündigung, verlängert sich die Vertragslaufzeit "
            f"stillschweigend um jeweils {vm} Monate.",
        ])]))
    paragraphen.append(("Vertraulichkeit", [
        "Die Parteien verpflichten sich, alle im Rahmen dieses Vertrags erlangten "
        "vertraulichen Informationen geheim zu halten. Diese Pflicht besteht auch nach "
        "Beendigung des Vertrags fort.",
    ]))
    paragraphen.append(("Schlussbestimmungen", [
        "Änderungen und Ergänzungen dieses Vertrags bedürfen der Textform. Dies gilt auch "
        "für die Aufhebung dieses Formerfordernisses.",
        "Sollte eine Bestimmung dieses Vertrags unwirksam sein, bleibt die Wirksamkeit der "
        "übrigen Bestimmungen unberührt.",
        f"Gerichtsstand ist {auftraggeber.ort}.",
    ]))

    render = {
        "paragraphen": paragraphen,
        "vertragsdatum_text": fdate(vertragsdatum),
        "unterzeichner_ag": fake.name(),
        "unterzeichner_an": fake.name(),
    }
    return gt, render

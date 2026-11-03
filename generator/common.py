"""Hilfsfunktionen für beide Dokumenttypen."""

from __future__ import annotations

import calendar
import hashlib
import random
from datetime import date, timedelta

from faker import Faker

from common.iban import make_de_iban
from common.schemas import Anschrift

# Einige reale BLZ-Formate (nur für plausible Darstellung; die IBAN ist
# rechnerisch gültig, gehört aber zu keinem echten Konto)
_BLZ = ["10010010", "20050550", "37040044", "50010517", "50070010", "60050101", "70020270", "76050101"]
_BIC = {
    "10010010": "PBNKDEFFXXX", "20050550": "HASPDEHHXXX", "37040044": "COBADEFFXXX",
    "50010517": "INGDDEFFXXX", "50070010": "DEUTDEFFXXX", "60050101": "SOLADEST600",
    "70020270": "HYVEDEMMXXX", "76050101": "SSKNDE77XXX",
}


def derive_seed(*parts: object) -> int:
    """Stabiler Seed je Dokument, unabhängig von Python-Hash-Randomisierung."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:12], 16)


def make_rng(seed: int) -> tuple[random.Random, Faker]:
    rng = random.Random(seed)
    fake = Faker("de_DE")
    fake.seed_instance(seed)
    return rng, fake


def firma(fake: Faker) -> Anschrift:
    return Anschrift(
        name=fake.company(),
        strasse=f"{fake.street_name()} {fake.building_number()}",
        plz=fake.postcode(),
        ort=fake.city(),
    )


def zwei_firmen(fake: Faker) -> tuple[Anschrift, Anschrift]:
    """Zwei Firmen mit unterschiedlichem Namen und Ort.

    Gleiche Namen würden eine vertauschte Zuordnung unsichtbar machen.
    """
    a = firma(fake)
    b = firma(fake)
    while b.name == a.name or b.ort == a.ort:
        b = firma(fake)
    return a, b


def ust_id(rng: random.Random) -> str:
    return "DE" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def bankverbindung(rng: random.Random) -> tuple[str, str]:
    blz = rng.choice(_BLZ)
    konto = str(rng.randint(10_000_000, 9_999_999_999))
    return make_de_iban(blz, konto), _BIC[blz]


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def add_months(d: date, months: int) -> date:
    """Addiert Monate; der Tag wird bei kürzeren Monaten gekappt."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

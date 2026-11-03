import pytest

pytest.importorskip("faker")

from generator.common import derive_seed, make_rng  # noqa: E402
from generator.invoice import make_invoice  # noqa: E402
from generator.validate import missing_values  # noqa: E402


def _rechnung():
    rng, fake = make_rng(derive_seed("validate", 1))
    gt, _ = make_invoice(rng, fake, True)
    return gt


def test_sauberer_text_besteht():
    gt = _rechnung()
    from common.formatting import format_date, format_eur, format_menge
    from common.iban import format_iban

    pos = " ".join(f"{p.beschreibung} {format_menge(p.menge)} {p.einheit} {format_eur(p.einzelpreis)} {format_eur(p.gesamtpreis)}" for p in gt.positionen)
    text = (f"{gt.lieferant.name}\n{gt.lieferant.strasse}\n{gt.lieferant.plz} {gt.lieferant.ort}\n"
            f"{gt.kunde.name}\n{gt.kunde.strasse}\n{gt.kunde.plz} {gt.kunde.ort}\n"
            f"Rechnungsnummer: {gt.rechnungsnummer} {format_date(gt.rechnungsdatum)} {format_date(gt.leistungsdatum)}\n"
            f"{pos}\n{format_eur(gt.netto)} {gt.ust_satz} % {format_eur(gt.ust_betrag)} {format_eur(gt.brutto)}\n"
            f"innerhalb von {gt.zahlungsziel_tage} Tagen USt-IdNr.: {gt.lieferant_ust_id} "
            f"IBAN: {format_iban(gt.iban)} BIC: {gt.bic}")
    assert missing_values(gt, text) == []


def test_vermischter_kopf_faellt_auf():
    gt = _rechnung()
    text = f"{gt.lieferant.name} {gt.kunde.name}\n{gt.lieferant.strasse} {gt.kunde.strasse}"
    fehlt = missing_values(gt, text)
    assert "lieferant (zusammenhängend)" in fehlt and "kunde (zusammenhängend)" in fehlt

from datetime import timedelta
from decimal import Decimal

import pytest

pytest.importorskip("faker")

from common.formatting import format_eur  # noqa: E402
from common.iban import is_valid_iban  # noqa: E402
from generator.__main__ import generate, missing_indices  # noqa: E402
from generator.common import add_months, derive_seed, make_rng  # noqa: E402
from generator.contract import make_contract  # noqa: E402
from generator.invoice import make_invoice  # noqa: E402
from generator.render import render_html  # noqa: E402

D = Decimal


def _invoices(n=200, fehlend=frozenset()):
    for i in range(n):
        rng, fake = make_rng(derive_seed("test", i))
        yield make_invoice(rng, fake, fehlend)


def _contracts(n=200, fehlend=frozenset()):
    for i in range(n):
        rng, fake = make_rng(derive_seed("test-v", i))
        yield make_contract(rng, fake, fehlend)


def test_rechnung_rechnerisch_korrekt():
    for gt, _ in _invoices():
        for p in gt.positionen:
            assert D(str(p.gesamtpreis)) == (D(str(p.einzelpreis)) * D(str(p.menge))).quantize(D("0.01"), "ROUND_HALF_UP")
        assert D(str(gt.netto)) == sum(D(str(p.gesamtpreis)) for p in gt.positionen)
        assert D(str(gt.netto)) + D(str(gt.ust_betrag)) == D(str(gt.brutto))
        assert gt.ust_satz in (7, 19)
        assert gt.leistungsdatum <= gt.rechnungsdatum
        assert gt.lieferant.name != gt.kunde.name


def test_rechnung_iban_gueltig_oder_fehlend():
    for gt, _ in _invoices(50):
        assert is_valid_iban(gt.iban) and gt.bic and gt.bestellnummer
    for gt, _ in _invoices(20, fehlend=frozenset({"bank"})):
        assert gt.iban is None and gt.bic is None and gt.bestellnummer
    for gt, r in _invoices(20, fehlend=frozenset({"bestellnummer"})):
        assert gt.bestellnummer is None and gt.iban
        assert "Bestellnummer" not in render_html("rechnung_a.html.j2", gt, r)


def test_vertrag_logik():
    for gt, _ in _contracts():
        assert gt.vertragsbeginn.day == 1
        assert gt.vertragsende == add_months(gt.vertragsbeginn, gt.laufzeit_monate) - timedelta(days=1)
        assert gt.vertragsdatum < gt.vertragsbeginn
        assert gt.auftraggeber.name != gt.auftragnehmer.name
    for gt, r in _contracts(20, fehlend=frozenset({"verlaengerung"})):
        assert gt.verlaengerung is None and gt.vertragsnummer
        assert all(t != "Vertragsverlängerung" for t, _ in r["paragraphen"])
    for gt, r in _contracts(20, fehlend=frozenset({"vertragsnummer"})):
        assert gt.vertragsnummer is None and gt.verlaengerung
        assert "Vertragsnummer" not in render_html("vertrag_a.html.j2", gt, r)


def test_werte_stehen_im_dokument():
    """Jeder Ground-Truth-Wert muss im Dokument vorkommen, sonst wäre er nicht extrahierbar."""
    for gt, r in _invoices(30):
        html = render_html("rechnung_a.html.j2", gt, r)
        for wert in [gt.rechnungsnummer, gt.lieferant_ust_id, format_eur(gt.brutto), format_eur(gt.netto), gt.bic, gt.bestellnummer]:
            assert wert.replace("&", "&amp;") in html
    for gt, r in _contracts(30):
        html = render_html("vertrag_a.html.j2", gt, r)
        assert format_eur(gt.verguetung_netto) in html
        assert gt.vertragsnummer in html


def test_reproduzierbar():
    a = [gt.model_dump() for gt, _ in _invoices(5)]
    b = [gt.model_dump() for gt, _ in _invoices(5)]
    assert a == b


def test_fester_anteil_fehlender_felder():
    assert len(missing_indices(42, "rechnung", 50, 0.3, "bank")) == 15
    assert len(missing_indices(42, "rechnung", 10, 0.25, "bank")) == 3  # 2,5 kaufmännisch auf 3
    assert missing_indices(42, "rechnung", 40, 0.3, "bank") == missing_indices(42, "rechnung", 40, 0.3, "bank")
    # Gruppen werden unabhängig ausgelost
    assert missing_indices(42, "rechnung", 50, 0.3, "bank") != missing_indices(42, "rechnung", 50, 0.3, "bestellnummer")


def test_generate_ohne_pdf(tmp_path):
    out = generate("t", {"rechnung": 4, "vertrag": 4}, 1, 0.25, tmp_path, pdf=False)
    assert (out / "manifest.json").exists()
    assert (out / "rechnung_0001" / "ground_truth.json").exists()
    assert (out / "vertrag_0004" / "document.html").exists()

from datetime import date

from common.formatting import format_date, format_date_long, format_eur, format_menge
from common.iban import format_iban, is_valid_iban, make_de_iban


def test_bekannte_iban_gueltig():
    assert is_valid_iban("DE89 3704 0044 0532 0130 00")


def test_iban_mit_falscher_pruefziffer_ungueltig():
    assert not is_valid_iban("DE88370400440532013000")


def test_iban_falsche_laenge_ungueltig():
    assert not is_valid_iban("DE8937040044053201300")


def test_make_de_iban_erzeugt_gueltige_iban():
    for konto in ["532013000", "1", "9999999999"]:
        iban = make_de_iban("37040044", konto)
        assert len(iban) == 22 and is_valid_iban(iban)
    assert make_de_iban("37040044", "532013000") == "DE89370400440532013000"


def test_format_iban():
    assert format_iban("DE89370400440532013000") == "DE89 3704 0044 0532 0130 00"


def test_formatierung():
    assert format_eur(1234.5) == "1.234,50 €"
    assert format_eur(0.005) == "0,01 €"  # kaufmännisch gerundet
    assert format_menge(3.0) == "3"
    assert format_menge(7.5) == "7,5"
    assert format_date(date(2026, 3, 5)) == "05.03.2026"
    assert format_date_long(date(2026, 3, 5)) == "5. März 2026"

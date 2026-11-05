from datetime import date

from labeling.label import label_document
from labeling.normalize import kuendigungsfrist, number, to_date, verlaengerung

GT = {
    "rechnungsnummer": "RE-2026-00042", "rechnungsdatum": "2026-03-05", "leistungsdatum": "2026-03-01",
    "lieferant": {"name": "Alpha GmbH", "strasse": "Hauptstr. 1", "plz": "64283", "ort": "Darmstadt"},
    "lieferant_ust_id": "DE123456789",
    "kunde": {"name": "Beta AG", "strasse": "Ring 2", "plz": "60311", "ort": "Frankfurt am Main"},
    "positionen": [{"beschreibung": "Beratung", "menge": 2.0, "einheit": "Std.", "einzelpreis": 100.0, "gesamtpreis": 200.0}],
    "netto": 200.0, "ust_satz": 19, "ust_betrag": 38.0, "brutto": 238.0, "zahlungsziel_tage": 14,
    "iban": None, "bic": None,
}
DOC = ("Alpha GmbH Hauptstr. 1 64283 Darmstadt Beta AG Ring 2 60311 Frankfurt am Main Rechnung "
       "Rechnungsnummer: RE-2026-00042 Rechnungsdatum: 05.03.2026 Leistungsdatum: 01.03.2026 "
       "Kundennummer: KD-12345 Beratung 2 Std. 100,00 € 200,00 € Nettobetrag 200,00 € "
       "zzgl. 19 % USt. 38,00 € Rechnungsbetrag 238,00 € zahlbar innerhalb von 14 Tagen USt-IdNr.: DE123456789")


def _labels(**changes):
    ext = {**GT, "rechnungsdatum": "05.03.2026", "netto": "200,00 €", "ust_satz": "19 %"}
    ext.update(changes)
    return {x.field: x for x in label_document("r", "d", "rechnung", GT, ext, DOC)}


def test_normalisierung():
    assert number("1.142,41 €") == 1142.41 and number("1.262.45 €") == 1262.45
    assert number("120 x 90 cm") is None and number("30 Tage") == 30
    assert to_date("2027-05-01T00:00:00") == date(2027, 5, 1) and to_date("5. März 2026") == date(2026, 3, 5)
    assert kuendigungsfrist("unter Einhaltung einer Frist von vier Wochen zum Monatsende") == (4, "woche", "monatsende")
    assert verlaengerung("stillschweigend um jeweils zwölf Monate") == ("monate", 12)


def test_formatunterschiede_sind_korrekt():
    labs = _labels()
    assert all(x.status == "korrekt" for x in labs.values()), [x for x in labs.values() if x.status != "korrekt"]


def test_fehlertypen():
    labs = _labels(
        iban="DE12345678901234567890",               # Dokument hat keine IBAN
        rechnungsdatum="2026-03-01",                  # gehört zum Leistungsdatum
        rechnungsnummer="KD-12345",                   # steht im Dokument, anderes Feld
        brutto=240.0,                                 # falsch berechnet
        kunde={**GT["kunde"], "name": "Beta"},        # unvollständig
        bic=None,
        zahlungsziel_tage=None,                       # fehlt
    )
    assert labs["iban"].fehlertyp == "erfunden"
    assert labs["rechnungsdatum"].fehlertyp == "vertauscht"
    assert labs["rechnungsnummer"].fehlertyp == "vertauscht"
    assert labs["brutto"].fehlertyp == "rechen_logik"
    assert labs["kunde.name"].fehlertyp == "verfaelscht"
    assert labs["bic"].status == "korrekt"
    assert labs["zahlungsziel_tage"].fehlertyp == "format_schema"


def test_zusaetzliche_position_ist_erfunden():
    extra = {"beschreibung": "Anfahrt", "menge": 1, "einheit": "Pauschale", "einzelpreis": 50, "gesamtpreis": 50}
    labs = _labels(positionen=GT["positionen"] + [extra])
    assert labs["positionen[2]"].fehlertyp == "erfunden"


def test_null_als_text_ist_leer():
    labs = _labels(iban="null", bic="")
    assert labs["iban"].status == "korrekt" and labs["bic"].status == "korrekt"


def test_frist_ohne_zeitpunkt_ist_unvollstaendig():
    gt = {"vertragsnummer": "DV-1", "kuendigungsfrist": "4 Wochen zum Monatsende"}
    labs = {x.field: x for x in label_document("r", "d", "vertrag", gt, {**gt, "kuendigungsfrist": "4 Wochen"}, "")}
    assert labs["kuendigungsfrist"].fehlertyp == "verfaelscht"


def _merged(**changes):
    from labeling.label import merge_addresses

    ext = {**GT, **changes}
    return {x.field: x for x in merge_addresses(label_document("r", "d", "rechnung", GT, ext, DOC), GT, ext)}


def test_anschrift_als_einheit_korrekt():
    labs = _merged()
    assert labs["lieferant"].status == "korrekt" and labs["kunde"].status == "korrekt"
    assert not any(k.startswith(("lieferant.", "kunde.")) for k in labs)


def test_vertauschte_anschriften_zaehlen_zweimal_statt_achtmal():
    labs = _merged(lieferant=GT["kunde"], kunde=GT["lieferant"])
    falsch = [x for x in labs.values() if x.status == "halluziniert"]
    assert [x.field for x in falsch] == ["lieferant", "kunde"]
    assert all(x.fehlertyp == "vertauscht" for x in falsch)


def test_ein_falsches_teilfeld_macht_anschrift_falsch():
    labs = _merged(kunde={**GT["kunde"], "plz": "60312"})
    assert labs["kunde"].status == "halluziniert"
    assert "plz" in labs["kunde"].detail

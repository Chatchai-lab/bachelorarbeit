"""Prüft, ob jeder Ground-Truth-Wert im extrahierten Dokumenttext auffindbar ist.

Steht ein Wert nicht oder nur zerstückelt im Text, den die Modelle erhalten,
kann ihn kein Modell korrekt extrahieren. Jede Abweichung würde dann als
Halluzination gezählt, obwohl der Fehler im Datensatz liegt. Deshalb bricht
der Generator ab, wenn diese Prüfung fehlschlägt.

Anschriften werden zusammenhängend geprüft ("Name Straße PLZ Ort"), weil
nebeneinanderstehende Blöcke bei der Textextraktion zeilenweise vermischt
werden können, obwohl jedes Einzelteil noch vorkommt.
"""

from __future__ import annotations

import re

from common.formatting import format_eur, format_menge
from labeling import normalize as N


def _flat(s: str) -> str:
    """Text ohne Kommas und mit einfachen Leerzeichen, klein geschrieben."""
    return re.sub(r"\s+", " ", (N.text(s) or "").replace(",", " ")).strip()


def missing_values(gt, raw_text: str) -> list[str]:
    doc = N.doc_text(raw_text)
    flat = _flat(raw_text)
    fehlt: list[str] = []

    def need(name: str, ok: bool) -> None:
        if not ok:
            fehlt.append(name)

    def anschrift(name: str, a) -> None:
        block = _flat(f"{a.name} {a.strasse} {a.plz} {a.ort}")
        need(f"{name} (zusammenhängend)", block in flat)

    if gt.dokument_typ == "rechnung":
        need("rechnungsnummer", N.string_in_doc(gt.rechnungsnummer, doc))
        need("rechnungsdatum", N.date_in_doc(gt.rechnungsdatum, doc))
        need("leistungsdatum", N.date_in_doc(gt.leistungsdatum, doc))
        anschrift("lieferant", gt.lieferant)
        anschrift("kunde", gt.kunde)
        need("lieferant_ust_id", N.string_in_doc(gt.lieferant_ust_id, doc))
        for i, p in enumerate(gt.positionen, 1):
            zeile = _flat(f"{p.beschreibung} {format_menge(p.menge)} {p.einheit} "
                          f"{format_eur(p.einzelpreis)} {format_eur(p.gesamtpreis)}")
            need(f"positionen[{i}] (zusammenhängend)", zeile in flat)
        for f in ("netto", "ust_betrag", "brutto"):
            need(f, N.text(format_eur(getattr(gt, f))) in doc)
        need("ust_satz", f"{gt.ust_satz} %" in doc)
        need("zahlungsziel_tage", f"{gt.zahlungsziel_tage} tagen" in doc)
        if gt.iban:
            need("iban", N.string_in_doc(gt.iban, doc))
            need("bic", N.string_in_doc(gt.bic, doc))
        else:
            need("keine iban im dokument", "iban" not in doc)
    else:
        need("vertragsnummer", N.string_in_doc(gt.vertragsnummer, doc))
        need("vertragsdatum", N.date_in_doc(gt.vertragsdatum, doc))
        anschrift("auftraggeber", gt.auftraggeber)
        anschrift("auftragnehmer", gt.auftragnehmer)
        need("leistungsgegenstand", N.string_in_doc(gt.leistungsgegenstand, doc))
        need("vertragsbeginn", N.date_in_doc(gt.vertragsbeginn, doc))
        need("vertragsende", N.date_in_doc(gt.vertragsende, doc))
        need("verguetung_netto", N.text(format_eur(gt.verguetung_netto)) in doc)
        # Laufzeit, Frist und Verlängerung stehen als Wort oder Ziffer im Satz;
        # geprüft wird, dass der zugehörige Satz den Wert in normierter Form enthält
        ohne_nummern = re.sub(r"§ ?\d+|\(\d+\)", " ", doc)  # Paragraphen- und Absatznummern
        saetze = re.split(r"(?<=[.;])\s", ohne_nummern)
        need("kuendigungsfrist", any(N.kuendigungsfrist(s) == N.kuendigungsfrist(gt.kuendigungsfrist) for s in saetze))
        if gt.verlaengerung:
            need("verlaengerung", any(
                "verlänger" in s and N.verlaengerung(s) == N.verlaengerung(gt.verlaengerung) for s in saetze))
        else:
            need("keine verlängerungsklausel", "verlänger" not in doc)
    return fehlt

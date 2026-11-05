"""Feldweiser Abgleich von Extraktion und Ground Truth.

Jedes Feld der Ground Truth erhält einen Status:

- ``korrekt``          stimmt nach Normalisierung überein
- ``halluziniert``     weicht ab (jede Abweichung gilt als Halluzination)
- ``manuell_pruefen``  automatisch nicht entscheidbar (Freitext); manuell nachprüfen

und bei ``halluziniert`` einen automatisch vorgeschlagenen Fehlertyp:

- ``erfunden``         Wert steht nicht im Dokument (extrinsisch), z. B. IBAN ohne Bankverbindung
- ``verfaelscht``      Wert steht nicht im Dokument, ähnelt aber dem korrekten (intrinsisch)
- ``vertauscht``       Wert steht im Dokument, gehört aber zu einem anderen Feld (intrinsisch)
- ``rechen_logik``     berechneter Wert (Netto, Brutto, Vertragsende ...) falsch und nicht im Dokument
- ``format_schema``    Feld fehlt oder Wert ist nicht als Feldtyp interpretierbar

Die Fehlertypen sind eine Heuristik; die Taxonomie wird anhand der
beobachteten Fehler verfeinert und Grenzfälle werden manuell geprüft.

Bewertungseinheit Anschrift (Entscheidung nach dem Vorversuch): Eine
Anschrift (Name, Straße, PLZ, Ort) zählt als EIN Feld und ist nur korrekt,
wenn alle vier Teile stimmen. Sonst würde z. B. eine einzige vertauschte
Zuordnung von Lieferant und Kunde als acht Fehler gezählt. Die Teilfelder
bleiben im Feld ``detail`` nachvollziehbar. Mit ``--adressen-einzeln``
lässt sich die feldweise Zählung zum Vergleich weiterhin erzeugen.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from extraction.prompts import PROMPT_BEISPIELE

from . import normalize as N

# Feldarten je Dokumenttyp; Anschriften und Positionen werden aufgefaltet
ANSCHRIFT = {"name": "text", "strasse": "text", "plz": "id", "ort": "text"}
POSITION = {"beschreibung": "text", "menge": "number", "einheit": "text", "einzelpreis": "number", "gesamtpreis": "number"}

FIELDS = {
    "rechnung": {
        "rechnungsnummer": "id", "rechnungsdatum": "date", "leistungsdatum": "date",
        "lieferant": ANSCHRIFT, "lieferant_ust_id": "id", "kunde": ANSCHRIFT,
        "positionen": [POSITION],
        "netto": "number", "ust_satz": "number", "ust_betrag": "number", "brutto": "number",
        "zahlungsziel_tage": "number", "bestellnummer": "id", "iban": "id", "bic": "id",
    },
    "vertrag": {
        "vertragsnummer": "id", "vertragsdatum": "date",
        "auftraggeber": ANSCHRIFT, "auftragnehmer": ANSCHRIFT,
        "leistungsgegenstand": "free", "vertragsbeginn": "date", "laufzeit_monate": "number",
        "vertragsende": "date", "kuendigungsfrist": "frist", "verguetung_netto": "number",
        "verguetung_intervall": "intervall", "verlaengerung": "verl",
    },
}

ANSCHRIFT_FELDER = {"lieferant", "kunde", "auftraggeber", "auftragnehmer"}

# Reihenfolge, nach der bei mehreren fehlerhaften Teilfeldern einer Anschrift
# der Fehlertyp der ganzen Anschrift gewählt wird (schwerster zuerst)
_TYP_PRIORITAET = ["erfunden", "vertauscht", "verfaelscht", "rechen_logik", "format_schema"]

# Werte, die das Modell rechnen oder ableiten müsste
DERIVED = {"netto", "ust_betrag", "brutto", "vertragsende"}
DERIVED_SUFFIX = {"gesamtpreis"}

_MISSING = object()


@dataclass
class FieldLabel:
    run_id: str
    doc_id: str
    doc_type: str
    field: str
    gt: object
    extracted: object
    status: str
    fehlertyp: str | None = None
    detail: str | None = None


def _flatten(spec, gt, ext, prefix=""):
    """Liefert (Feldname, Art, GT-Wert, extrahierter Wert) für alle Blätter."""
    for key, kind in spec.items():
        g = gt.get(key) if isinstance(gt, dict) else None
        e = ext.get(key, _MISSING) if isinstance(ext, dict) else _MISSING
        name = f"{prefix}{key}"
        if isinstance(kind, dict):
            yield from _flatten(kind, g or {}, e if isinstance(e, dict) else {}, name + ".")
        elif isinstance(kind, list):
            g_list = g or []
            e_list = e if isinstance(e, list) else []
            for i in range(max(len(g_list), len(e_list))):
                gi = g_list[i] if i < len(g_list) else None
                ei = e_list[i] if i < len(e_list) else _MISSING
                if gi is None:  # zusätzliche, erfundene Position
                    yield (f"{name}[{i + 1}]", "extra_position", None, ei)
                    continue
                yield from _flatten(kind[0], gi, ei if isinstance(ei, dict) else {}, f"{name}[{i + 1}].")
        else:
            yield name, kind, g, e


_LEER = {"null", "none", "n/a", "na", "-", "keine", "nicht angegeben", "nicht vorhanden"}


def _normalize(kind, v):
    """-> (normierter Wert, interpretierbar?)"""
    if v is None or v is _MISSING or (isinstance(v, str) and (N.text(v) or "") in _LEER | {""}):
        return None, True
    if kind == "number":
        n = N.number(v)
        return n, n is not None
    if kind == "date":
        d = N.to_date(v)
        return d, d is not None
    if kind == "id":
        return N.compact(v), True
    if kind == "frist":
        f = N.kuendigungsfrist(v)
        return f, f is not None
    if kind == "verl":
        f = N.verlaengerung(v)
        return f, f is not None
    if kind == "intervall":
        f = N.intervall(v)
        return f, f is not None
    return N.text(v), True


def _equal(kind, g, e) -> bool:
    if g is None or e is None:
        return g is None and e is None
    if kind == "number":
        return abs(g - e) < 0.005
    return g == e


def _in_doc(kind, val, doc: str) -> bool:
    if val is None:
        return False
    if kind == "number":
        return N.number_in_doc(val, doc)
    if kind == "date":
        return N.date_in_doc(val, doc)
    if kind in ("text", "id", "free"):
        return N.string_in_doc(str(val), doc)
    return False


def _similar(g, e) -> bool:
    if isinstance(g, date) and isinstance(e, date):
        return sum(a == b for a, b in [(g.year, e.year), (g.month, e.month), (g.day, e.day)]) >= 2
    if isinstance(g, float) and isinstance(e, float):
        dreher = sorted(f"{g:.2f}") == sorted(f"{e:.2f}")  # z. B. 36 -> 63
        return dreher or (g != 0 and abs(g - e) / abs(g) < 0.1)
    return difflib.SequenceMatcher(None, str(g), str(e)).ratio() >= 0.6


def label_document(run_id, doc_id, doc_type, gt: dict, parsed: dict | None, doc_raw: str) -> list[FieldLabel]:
    doc = N.doc_text(doc_raw)
    leaves = list(_flatten(FIELDS[doc_type], gt, parsed or {}))

    # normierte GT-Werte aller Felder, um vertauschte Zuordnungen zu erkennen
    gt_by_kind: dict[str, list[tuple[str, object]]] = {}
    for name, kind, g, _ in leaves:
        if kind != "extra_position":
            gn, _ = _normalize(kind, g)
            if gn is not None:
                gt_by_kind.setdefault(kind, []).append((name, gn))

    labels = []
    for name, kind, g, e in leaves:
        lab = FieldLabel(run_id, doc_id, doc_type, name, g, None if e is _MISSING else e, "korrekt")
        if kind == "extra_position":
            lab.status, lab.fehlertyp, lab.detail = "halluziniert", "erfunden", "zusätzliche Position"
            labels.append(lab)
            continue

        gn, _ = _normalize(kind, g)
        en, ok = _normalize(kind, e)

        if not ok:
            if kind == "frist" and gn and N._dauer(N.text(e) or "") == gn[:2]:
                lab.status, lab.fehlertyp, lab.detail = "halluziniert", "verfaelscht", "unvollständig (Zeitpunkt fehlt)"
            elif kind in ("frist", "verl", "intervall"):
                lab.status, lab.detail = "manuell_pruefen", "nicht automatisch interpretierbar"
            else:
                lab.status, lab.fehlertyp, lab.detail = "halluziniert", "format_schema", "nicht interpretierbar"
        elif _equal(kind, gn, en):
            pass
        elif kind == "free":
            lab.status, lab.detail = "manuell_pruefen", "Freitext"
        elif en is None:
            lab.status, lab.fehlertyp, lab.detail = "halluziniert", "format_schema", (
                "Feld fehlt in der Ausgabe" if e is _MISSING else "ausgelassen (null, obwohl im Dokument)"
            )
        elif gn is None:
            lab.status = "halluziniert"
            if _in_doc(kind, en, doc):  # z. B. Kundennummer als Bestellnummer ausgegeben
                lab.fehlertyp, lab.detail = "vertauscht", "Feld fehlt im Dokument, Wert stammt aus anderer Angabe"
            else:
                lab.fehlertyp, lab.detail = "erfunden", "Wert ohne Grundlage im Dokument"
        elif name in PROMPT_BEISPIELE and _normalize(kind, PROMPT_BEISPIELE[name])[0] == en:
            lab.status, lab.fehlertyp, lab.detail = "halluziniert", "erfunden", "Prompt-Beispiel übernommen"
        elif kind == "text" and (en in gn or gn in en):
            lab.status, lab.fehlertyp = "halluziniert", "verfaelscht"
            lab.detail = "unvollständig" if en in gn else "um weiteren Text ergänzt"
        else:
            lab.status = "halluziniert"
            andere = [n for n, v in gt_by_kind.get(kind, []) if n != name and _equal(kind, v, en)]
            leaf = name.rsplit(".", 1)[-1].split("[")[0]
            if andere:
                lab.fehlertyp, lab.detail = "vertauscht", f"Wert gehört zu {andere[0]}"
            elif _in_doc(kind, en, doc):
                lab.fehlertyp, lab.detail = "vertauscht", "Wert steht an anderer Stelle im Dokument"
            elif kind in ("frist", "verl", "intervall"):
                lab.fehlertyp, lab.detail = "verfaelscht", "anderer Wert als im Dokument"
            elif name in DERIVED or leaf in DERIVED_SUFFIX:
                lab.fehlertyp, lab.detail = "rechen_logik", "berechneter Wert falsch"
            elif _similar(gn, en):
                lab.fehlertyp, lab.detail = "verfaelscht", "ähnlich, aber nicht im Dokument"
            else:
                lab.fehlertyp, lab.detail = "erfunden", "nicht im Dokument"
        labels.append(lab)
    return labels


def merge_addresses(labels: list[FieldLabel], gt: dict, parsed: dict | None) -> list[FieldLabel]:
    """Fasst die vier Teilfelder jeder Anschrift zu einem Label zusammen."""
    parsed = parsed or {}
    out: list[FieldLabel | str] = []
    groups: dict[str, list[FieldLabel]] = {}
    for lab in labels:
        prefix = lab.field.split(".")[0]
        if prefix in ANSCHRIFT_FELDER and "." in lab.field:
            if prefix not in groups:
                groups[prefix] = []
                out.append(prefix)  # Platzhalter, damit die Reihenfolge erhalten bleibt
            groups[prefix].append(lab)
        else:
            out.append(lab)

    def norm_addr(a) -> tuple | None:
        if not isinstance(a, dict):
            return None
        return tuple(N.compact(a.get(k)) if k == "plz" else N.text(a.get(k)) for k in ANSCHRIFT)

    result: list[FieldLabel] = []
    for item in out:
        if isinstance(item, FieldLabel):
            result.append(item)
            continue
        prefix, teile = item, groups[item]
        first = teile[0]
        lab = FieldLabel(first.run_id, first.doc_id, first.doc_type, prefix, gt.get(prefix), parsed.get(prefix), "korrekt")
        falsch = [t for t in teile if t.status == "halluziniert"]
        unklar = [t for t in teile if t.status == "manuell_pruefen"]
        if falsch:
            lab.status = "halluziniert"
            ext = norm_addr(parsed.get(prefix))
            andere = [p for p in ANSCHRIFT_FELDER if p != prefix and ext is not None and ext == norm_addr(gt.get(p))]
            if andere:
                lab.fehlertyp, lab.detail = "vertauscht", f"ganze Anschrift gehört zu {andere[0]}"
            else:
                typen = [t.fehlertyp for t in falsch]
                lab.fehlertyp = min(typen, key=lambda t: (-typen.count(t), _TYP_PRIORITAET.index(t)))
                lab.detail = "; ".join(f"{t.field.split('.', 1)[1]}: {t.fehlertyp} ({t.detail})" for t in falsch)
        elif unklar:
            lab.status, lab.detail = "manuell_pruefen", "; ".join(t.field for t in unklar)
        result.append(lab)
    return result


def _json_default(o):
    if isinstance(o, date):
        return o.isoformat()
    return str(o)


def label_run(run_dir: Path, dataset_dir: Path, adressen_einzeln: bool = False) -> dict:
    """Labelt alle Dokumente eines Laufs und schreibt labels.jsonl und labels_summary.json.

    Mit adressen_einzeln=True werden Anschriften feldweise gezählt und die
    Ergebnisse in labels_adressen_einzeln*.json(l) geschrieben (nur zum Vergleich).
    """
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in (run_dir / "extractions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    all_labels: list[FieldLabel] = []
    unbrauchbar = []
    for r in records:
        d = dataset_dir / r["doc_id"]
        gt = json.loads((d / "ground_truth.json").read_text(encoding="utf-8"))
        if r["parsed"] is None:
            unbrauchbar.append(r["doc_id"])
            continue
        doc_raw = (d / "document.txt").read_text(encoding="utf-8")
        labs = label_document(run["run_id"], r["doc_id"], r["doc_type"], gt, r["parsed"], doc_raw)
        if not adressen_einzeln:
            labs = merge_addresses(labs, gt, r["parsed"])
        all_labels += labs

    stem = "labels_adressen_einzeln" if adressen_einzeln else "labels"
    with open(run_dir / f"{stem}.jsonl", "w", encoding="utf-8") as f:
        for lab in all_labels:
            f.write(json.dumps(asdict(lab), ensure_ascii=False, default=_json_default) + "\n")

    summary = summarize(all_labels)
    summary.update(
        run_id=run["run_id"], model=run["model"]["name"], output_format=run["output_format"],
        gpu=run["environment"].get("gpu"), n_docs=len(records),
        n_unbrauchbar=len(unbrauchbar), unbrauchbar=unbrauchbar,
        anschrift_als_einheit=not adressen_einzeln,
    )
    (run_dir / f"{stem}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def summarize(labels: list[FieldLabel]) -> dict:
    def count(items):
        n = len(items)
        h = sum(x.status == "halluziniert" for x in items)
        m = sum(x.status == "manuell_pruefen" for x in items)
        return {"felder": n, "halluziniert": h, "manuell_pruefen": m, "rate": round(h / n, 3) if n else None}

    by_type: dict[str, int] = {}
    by_field: dict[str, list] = {}
    for x in labels:
        if x.status == "halluziniert":
            by_type[x.fehlertyp] = by_type.get(x.fehlertyp, 0) + 1
        key = f"{x.doc_type}:{x.field.split('[')[0]}" + (".*" if "[" in x.field else "")
        by_field.setdefault(key, []).append(x)
    return {
        "gesamt": count(labels),
        "je_dokumenttyp": {t: count([x for x in labels if x.doc_type == t]) for t in sorted({x.doc_type for x in labels})},
        "je_fehlertyp": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "je_feld": {k: count(v) for k, v in sorted(by_field.items())},
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Labelt Extraktionsläufe gegen die Ground Truth.")
    ap.add_argument("runs", nargs="+", type=Path, help="Lauf-Ordner unter data/runs/")
    ap.add_argument("--dataset", type=Path, help="Datensatz-Ordner (Standard: aus run.json)")
    ap.add_argument("--adressen-einzeln", action="store_true",
                    help="Anschriften feldweise zählen (nur zum Vergleich, eigene Ausgabedateien)")
    args = ap.parse_args()

    for run_dir in args.runs:
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        ds = args.dataset or Path(run["dataset"]["path"])
        s = label_run(run_dir, ds, adressen_einzeln=args.adressen_einzeln)
        g = s["gesamt"]
        print(f"{s['run_id']}  [{s['model']}, {s['output_format']}, {s['gpu']}]")
        print(f"  unbrauchbar: {s['n_unbrauchbar']}/{s['n_docs']}  |  Felder: {g['felder']}  "
              f"halluziniert: {g['halluziniert']} ({g['rate']:.1%})  manuell prüfen: {g['manuell_pruefen']}")
        for t, c in s["je_dokumenttyp"].items():
            print(f"    {t:9s} {c['halluziniert']:3d}/{c['felder']:3d} ({c['rate']:.1%})")
        print(f"  Fehlertypen: {s['je_fehlertyp']}")


if __name__ == "__main__":
    main()

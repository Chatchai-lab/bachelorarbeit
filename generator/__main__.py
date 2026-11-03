"""Kommandozeile für den Generator.

Beispiel (Vorversuch, je 10 Dokumente):

    python -m generator --name vorversuch --n-rechnung 10 --n-vertrag 10 --seed 42

Ergebnis:

    data/datasets/vorversuch/
        manifest.json                  Parameter, Versionen, Dokumentliste
        rechnung_0001/
            ground_truth.json          korrekte Lösung (nur für die Bewertung)
            render.json                Darstellungsdetails (Layout, Ablenker)
            document.html
            document.pdf
            document.txt               Text, den die Modelle erhalten
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from common.schemas import OPTIONAL_FIELDS

from . import GENERATOR_VERSION
from .common import derive_seed, make_rng
from .contract import make_contract
from .invoice import make_invoice
from .render import LAYOUTS, html_to_pdf, pdf_to_text, render_html

MAKERS = {"rechnung": make_invoice, "vertrag": make_contract}


def _pkg_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git_commit() -> str | None:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.call(["git", "diff", "--quiet"], stderr=subprocess.DEVNULL) != 0
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def missing_indices(seed: int, doc_type: str, n: int, rate: float) -> set[int]:
    """Fester Anteil: genau round(n * rate) Dokumente ohne optionale Felder."""
    import random

    k = round(n * rate)
    return set(random.Random(derive_seed(seed, doc_type, "missing")).sample(range(1, n + 1), k))


def generate(name: str, counts: dict[str, int], seed: int, missing_rate: float, out_root: Path, pdf: bool = True) -> Path:
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    docs = []
    for doc_type, n in counts.items():
        ohne = missing_indices(seed, doc_type, n, missing_rate)
        for i in range(1, n + 1):
            doc_id = f"{doc_type}_{i:04d}"
            doc_seed = derive_seed(seed, doc_type, i)
            rng, fake = make_rng(doc_seed)
            gt, render = MAKERS[doc_type](rng, fake, i not in ohne)
            layout = LAYOUTS[doc_type][rng.randrange(len(LAYOUTS[doc_type]))]
            render["layout"] = layout

            d = out / doc_id
            d.mkdir(exist_ok=True)
            (d / "ground_truth.json").write_text(gt.model_dump_json(indent=2), encoding="utf-8")
            (d / "render.json").write_text(json.dumps(render, ensure_ascii=False, indent=2), encoding="utf-8")
            html = render_html(layout, gt, render)
            (d / "document.html").write_text(html, encoding="utf-8")
            if pdf:
                html_to_pdf(html, d / "document.pdf")
                (d / "document.txt").write_text(pdf_to_text(d / "document.pdf"), encoding="utf-8")

            docs.append({
                "doc_id": doc_id,
                "doc_type": doc_type,
                "seed": doc_seed,
                "layout": layout,
                "optionale_felder_fehlen": i in ohne,
                "fehlende_felder": OPTIONAL_FIELDS[doc_type] if i in ohne else [],
            })
            print(f"  {doc_id}  {'(ohne optionale Felder)' if i in ohne else ''}")

    manifest = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "counts": counts,
        "missing_rate": missing_rate,
        "generator_version": GENERATOR_VERSION,
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "packages": {p: _pkg_version(p) for p in ["faker", "jinja2", "weasyprint", "pdfplumber", "pydantic"]},
        "documents": docs,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Erzeugt synthetische Rechnungen und Verträge mit Ground Truth.")
    ap.add_argument("--name", required=True, help="Name des Datensatzes, z. B. vorversuch")
    ap.add_argument("--n-rechnung", type=int, default=10)
    ap.add_argument("--n-vertrag", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--missing-rate", type=float, default=0.25, help="Anteil ohne optionale Felder (0.2 bis 0.3)")
    ap.add_argument("--out", type=Path, default=Path("data/datasets"))
    ap.add_argument("--no-pdf", action="store_true", help="nur JSON und HTML (zum schnellen Testen)")
    args = ap.parse_args()

    counts = {"rechnung": args.n_rechnung, "vertrag": args.n_vertrag}
    out = generate(args.name, counts, args.seed, args.missing_rate, args.out, pdf=not args.no_pdf)
    print(f"Fertig: {out}")


if __name__ == "__main__":
    main()

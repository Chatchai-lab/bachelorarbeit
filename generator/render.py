"""HTML-Rendering (Jinja2), PDF-Erzeugung (WeasyPrint) und Textextraktion (pdfplumber)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from common.formatting import format_date, format_eur, format_menge
from common.iban import format_iban

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Layouts je Dokumenttyp; weitere Layouts werden hier ergänzt
LAYOUTS = {
    "rechnung": ["rechnung_a.html.j2"],
    "vertrag": ["vertrag_a.html.j2"],
}

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    undefined=StrictUndefined,
    autoescape=True,
)
_env.globals.update(
    fmt_date=format_date,
    fmt_eur=format_eur,
    fmt_menge=format_menge,
    fmt_iban=format_iban,
)


def render_html(template: str, gt, render: dict) -> str:
    css = (TEMPLATE_DIR / "base.css").read_text(encoding="utf-8")
    return _env.get_template(template).render(gt=gt, r=render, css=css)


def html_to_pdf(html: str, out: Path) -> None:
    from weasyprint import HTML  # erst hier importieren: braucht Systembibliotheken

    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(out)


def pdf_to_text(pdf: Path) -> str:
    """Text so, wie ihn die Extraktionsmodelle erhalten (alle Seiten)."""
    import pdfplumber

    with pdfplumber.open(pdf) as doc:
        pages = [page.extract_text() or "" for page in doc.pages]
    return "\n\n".join(p.strip() for p in pages).strip() + "\n"

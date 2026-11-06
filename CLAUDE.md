# CLAUDE.md

Bachelorarbeit von Chatchai Sirichot (Hochschule Darmstadt): **Quality-Gates für LLM-Pipelines**,
empirische Evaluation von Verfahren zur Halluzinationserkennung bei der Extraktion
deutschsprachiger Rechnungen und Verträge. Ausführliche Doku: [docs/](docs/README.md).

## Sprache und Stil

- Sprache der Arbeit, Kommentare, Docstrings, Commit-Messages und Doku: **Deutsch**.
- Bezeichner im Code folgen dem Fachvokabular (`rechnung`, `positionen`, `kuendigungsfrist`), ohne Umlaute.
- Commit-Messages: kurze Betreffzeile im Indikativ, Begründung im Rumpf (siehe `git log`).
- Änderungen mit Außenwirkung (Verhalten, Läufe, Datenformat) in [CHANGELOG.md](CHANGELOG.md) unter `[Unreleased]` eintragen.

## Befehle

```bash
source .venv/bin/activate
pytest                                   # alle Tests, laufen lokal ohne Modal
python -m generator --name vorversuch3 --n-rechnung 10 --n-vertrag 10 --seed 42
modal run -m extraction.modal_extract --dataset data/datasets/vorversuch3 --model llama3.2:1b --limit 2
python -m labeling.label data/runs/<run-id>      # lokal, schreibt labels.jsonl + labels_summary.json
```

Die vollständigen Optionen stehen in [README.md](README.md) und [docs/extraktion.md](docs/extraktion.md).

## Architektur in Kürze

`generator/` (lokal) erzeugt Dokumente samt Ground Truth, `extraction/` (Modal, GPU) lässt kleine
Modelle über Ollama extrahieren, `labeling/` (lokal) gleicht die Extraktionen mit der Ground Truth ab und vergibt
Status und Fehlertyp je Feld, `common/` enthält Datenmodelle und gemeinsame Regeln. `checks/`, `experiments/` und
`analysis/` sind geplant, aber noch nicht vorhanden (siehe [docs/roadmap.md](docs/roadmap.md)). Diagramme: [docs/architektur.md](docs/architektur.md).

## Unverrückbare Regeln

1. **GPU ist festgelegt: exakt `NVIDIA A10`** (`common/hardware.py`). Nicht `A10G`, nicht `L4`.
   Modal vergibt bei `gpu="A10"` je nach Cloud beide Varianten; `check_gpu` bricht dann ab und der
   Lauf muss neu gestartet werden. Konstanten dort nicht ändern, ohne alle Läufe zu wiederholen.
   Nur Läufe auf `NVIDIA A10` sind für Latenzvergleiche gültig.
2. **Ground Truth nie an Prüfstufen oder Extraktionsmodelle weitergeben.** Sie dient nur der
   Erzeugung der Dokumente und der späteren Bewertung (`common/schemas.py`).
3. **Reproduzierbarkeit:** jeder Lauf trägt Seed, Prompt-Version/-Hash, Modell-Digest, GPU und
   Git-Commit. Wer den Prompt inhaltlich ändert, erhöht `PROMPT_VERSION` in `extraction/prompts.py` (aktuell `v3`).
   Ändert sich die Labeling-Heuristik, **alle** Läufe neu labeln, sonst sind Raten nicht vergleichbar.
4. **Bestehende Läufe und Datensätze unter `data/` nicht überschreiben oder umbenennen.** Neue Läufe
   bekommen eine neue `--run-id`; dieselbe ID bedeutet Wiederaufnahme.
5. Alles, was in Latenzmessungen eingeht, läuft auf Modal; lokal nur Schritte ohne Latenzmessung.
6. **Jeder Ground-Truth-Wert muss im Dokumenttext stehen.** `generator/validate.py` bricht sonst ab; was kein Modell
   finden kann, darf nicht als Halluzination zählen. Eine Anschrift zählt im Labeling als **ein** Feld.
7. Schemakonventionen: Datum ISO (`YYYY-MM-DD`), Beträge als Zahl mit zwei Nachkommastellen,
   Steuersatz als ganze Prozentzahl, fehlendes optionales Feld = `null`.

## Fallstricke

- `bash` gibt beim Start ein fastfetch-Banner aus; bei Shell-Ausgaben darin nach der eigentlichen Ausgabe suchen.
- WeasyPrint braucht Systembibliotheken (Pango). Der Import steckt deshalb in `html_to_pdf`; Tests mit `--no-pdf`-Pfad laufen auch ohne.
- Lauf `20261103-1517_…llama3.2-1b…` lief auf `NVIDIA A10G` (vor der strengen Prüfung) und ist für Latenzvergleiche **nicht** gültig, siehe [docs/vorversuch.md](docs/vorversuch.md).
- Mehrere Datensätze: `vorversuch` (Prompt v1), `vorversuch2` (v2), `vorversuch3` (v3, mit zusätzlichen optionalen Feldern); Läufe nicht über Prompts hinweg vergleichen, siehe [docs/vorversuch.md](docs/vorversuch.md).
- Ausgabeformate: `none`, `json`, `schema` (mit Datentypen), `schema_text` (feste Felder, Text); bisher am günstigsten: `schema_text` (Entscheidung für den Hauptlauf offen).
- `bachelorarbeit.egg-info/` und `.venv/` sind nicht versioniert.

## Wo liegt was

| Pfad | Inhalt |
|------|--------|
| `common/` | Pydantic-Schemas, IBAN, Formatierung, GPU-Festlegung |
| `generator/` | Faker → Ground Truth → Jinja2 → WeasyPrint → pdfplumber (`document.txt`), `validate.py` prüft Auffindbarkeit |
| `extraction/` | Prompts, Ollama-Client, Parser, Modal-Skript |
| `labeling/` | Abgleich Extraktion ↔ Ground Truth (`label.py`), Normalisierung (`normalize.py`) |
| `data/datasets/<name>/` | erzeugte Dokumente + `manifest.json` |
| `data/runs/<run-id>/` | `run.json`, `extractions.jsonl`, `docs/<doc_id>.json`, `labels.jsonl`, `labels_summary.json` |
| `tests/` | pytest, kein Modal nötig |
| `docs/` | Projektdokumentation mit Mermaid-Diagrammen |

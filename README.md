# Bachelorarbeit: Quality-Gates für LLM-Pipelines

Empirische Evaluation von Verfahren zur Halluzinationserkennung bei der
Extraktion deutschsprachiger Rechnungen und Verträge.

Chatchai Sirichot, Hochschule Darmstadt (h_da), Fachbereich Informatik

## Aufbau

| Ordner         | Inhalt                                               | Läuft auf | Stand    |
|----------------|------------------------------------------------------|-----------|----------|
| `common/`      | Datenmodelle (Ground Truth), IBAN, Formatierung      | –         | fertig   |
| `generator/`   | Faker (de_DE) → JSON → Jinja2 → PDF → Text           | lokal     | fertig   |
| `extraction/`  | Extraktion mit Llama 3.2 1B / Qwen2.5 1.5B (Ollama)  | Modal     | fertig   |
| `labeling/`    | Abgleich Extraktion ↔ Ground Truth, Fehlertypen      | lokal     | fertig   |
| `checks/`      | Prüfstufen: Regeln, NLI, LLM-as-a-Judge              | Modal     | offen    |
| `experiments/` | Modal-Skripte für Einzel- und Kombinationsläufe      | Modal     | offen    |
| `analysis/`    | Precision/Recall/F1, Bootstrap, Plots                | lokal     | offen    |
| `data/`        | erzeugte Datensätze (`datasets/`) und Läufe (`runs/`) | –         |          |
| `tests/`       | Unit-Tests                                           | lokal     |          |

Alles, was in Latenzmessungen eingeht (Extraktion und alle Prüfstufen),
läuft auf Modal auf demselben GPU-Typ: NVIDIA A10 (24 GB), festgelegt in `common/hardware.py`. Lokal laufen nur Schritte ohne
Latenzmessung.

## Einrichtung (einmalig)

```bash
# WeasyPrint braucht Pango (Ubuntu)
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[modal,dev]"

modal setup        # öffnet den Browser, speichert den Modal-Token lokal
pytest             # alle Tests sollten durchlaufen
```

## Vorversuch

1. **Datensatz erzeugen** (lokal; jede optionale Feldgruppe fehlt bei 30 % der Dokumente, unabhängig voneinander):

   ```bash
   python -m generator --name vorversuch --n-rechnung 10 --n-vertrag 10 --seed 42
   ```

   Danach ein paar PDFs unter `data/datasets/vorversuch/*/document.pdf` ansehen.
   `document.txt` ist genau der Text, den die Modelle bekommen.

2. **Kurztest auf Modal** (2 Dokumente):

   ```bash
   modal run -m extraction.modal_extract --dataset data/datasets/vorversuch --model llama3.2:1b --limit 2
   ```

   Beim ersten Mal baut Modal das Image und lädt das Modell (einige Minuten).

3. **Volle Läufe**, je Extraktionsmodell:

   ```bash
   modal run -m extraction.modal_extract --dataset data/datasets/vorversuch --model llama3.2:1b
   modal run -m extraction.modal_extract --dataset data/datasets/vorversuch --model qwen2.5:1.5b
   ```

   Ergebnisse liegen unter `data/runs/<run-id>/` (`run.json` = Protokoll,
   `extractions.jsonl` = alle Antworten).

4. **Labeln** (lokal, vergleicht feldweise mit der Ground Truth):

   ```bash
   python -m labeling.label data/runs/<run-id> [weitere Läufe ...]
   ```

   Schreibt `labels.jsonl` (ein Eintrag je Feld) und `labels_summary.json` in den Lauf-Ordner.

5. **Ergebnisse committen**: `git add data && git commit && git push`.

### Optionen der Extraktion

| Option          | Standard      | Bedeutung                                                     |
|-----------------|---------------|---------------------------------------------------------------|
| `--model`       | `llama3.2:1b` | Ollama-Modell, z. B. `qwen2.5:1.5b`, Ausweich `qwen3:1.7b`    |
| `--limit`       | `0` (alle)    | nur die ersten n Dokumente                                    |
| `--doc-type`    | `all`         | `rechnung` oder `vertrag`                                     |
| `--temperature` | `0`           | Hauptlauf 0, Stabilitätstest 0.7                              |
| `--seed`        | `42`          |                                                               |
| `--fmt`         | `none`        | `json` (JSON-Modus), `schema` (Structured Output mit Datentypen) oder `schema_text` (feste Felder, Werte als Text) |
| `--num-predict` | `1024`        | maximale Antwortlänge in Tokens (vollständige Antwort ca. 500) |
| `--run-id`      | automatisch   | gleiche ID erneut starten = Wiederaufnahme nach Abbruch      |

Lange Läufe ohne offenes Terminal:

```bash
modal run --detach -m extraction.modal_extract --dataset ... --model ... --run-id meinlauf
modal volume get ba-results meinlauf data/runs/
```

## Reproduzierbarkeit

- Jedes Dokument hat einen eigenen Seed; derselbe `--seed` erzeugt dieselbe Ground Truth.
- `manifest.json` je Datensatz enthält Parameter, Paketversionen und Git-Commit.
- `run.json` je Lauf enthält Modell, Ollama-Digest, Quantisierung, Temperature,
  Seed, Prompt-Version und -Hash, GPU, Ollama-Version, Git-Commit und Zeitstempel.

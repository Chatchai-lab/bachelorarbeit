# Bachelorarbeit: Quality-Gates für LLM-Pipelines

Empirische Evaluation von Verfahren zur Halluzinationserkennung bei der
Extraktion deutschsprachiger Rechnungen und Verträge.

Chatchai Sirichot, Hochschule Darmstadt (h_da), Fachbereich Informatik

## Aufbau (geplant)

| Ordner        | Inhalt                                              | Läuft auf |
|---------------|-----------------------------------------------------|-----------|
| `generator/`  | Ground Truth (Faker) → Jinja2 → PDF (WeasyPrint)    | lokal     |
| `extraction/` | Extraktion mit Llama 3.2 1B / Qwen2.5 1.5B (Ollama) | Modal     |
| `labeling/`   | Abgleich Extraktion ↔ Ground Truth, Fehlertypen     | lokal     |
| `checks/`     | Prüfstufen: Regeln, NLI, LLM-as-a-Judge             | Modal     |
| `experiments/`| Modal-Skripte für Einzel- und Kombinationsläufe     | Modal     |
| `analysis/`   | Precision/Recall/F1, Bootstrap, Plots               | lokal     |
| `data/`       | erzeugte Dokumente und Laufergebnisse               | –         |
| `docs/`       | Notizen, Entscheidungen                             | –         |

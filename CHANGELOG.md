# Changelog

Alle nennenswerten Änderungen an diesem Projekt. Format nach
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung nach
[Semantic Versioning](https://semver.org/lang/de/) (Paketversion in `pyproject.toml`).

## [Unreleased]

### Hinzugefügt
- `CLAUDE.md` mit Projektregeln und Befehlen für die Arbeit mit Claude Code.
- `docs/` mit Projektdokumentation und Mermaid-Diagrammen, dieses Changelog.
- Paket `labeling/`: feldweiser Abgleich von Extraktion und Ground Truth mit Normalisierung (Zahlen, Datumsangaben,
  Fristen) und heuristischen Fehlertypen (`erfunden`, `verfaelscht`, `vertauscht`, `rechen_logik`, `format_schema`);
  Labels der Vorversuchsläufe (`735bcf8`).
- `generator/validate.py`: der Generator bricht ab, wenn ein Ground-Truth-Wert im Dokumenttext nicht auffindbar ist (`735bcf8`).
- Ausgabeformat `schema_text` (feste Feldnamen, Werte als Text) nach Runde 2 des Vorversuchs (`843acc9`).
- Datensätze `vorversuch2` und `vorversuch3` sowie weitere Läufe (Vorversuch Runde 2 und 3, Kontrolllauf Llama am 05.11.) (`eb0abcc`, `44b6214`, `c0d9a3c`).
- Optionale Feldgruppen: `bestellnummer` (Rechnung) und `vertragsnummer` (Vertrag), jede Gruppe fehlt unabhängig bei 30 % der Dokumente (`ca15c15`).
- `labeling --adressen-einzeln` für die feldweise Zählung von Anschriften zum Vergleich (`359f39b`).

### Geändert
- Prompt v2: keine konkreten Beispielwerte mehr, da die Modelle sie in v1 wörtlich übernahmen (`735bcf8`).
- Prompt v3: neues Feld `bestellnummer`, `vertragsnummer` optional (`ca15c15`).
- Briefkopf der Rechnung steht über statt neben der Anschrift, sonst vermischte die Textextraktion Lieferant und Kunde (`735bcf8`).
- Aufwärmen vor der Messung mit je einer vollständigen, echten Anfrage je Dokumenttyp statt mit einem Token; das erste gemessene Dokument war sonst 3- bis 4-mal langsamer (`372b699`).
- Labeling: `"null"` als Text gilt als leer; Frist ohne Zeitpunkt ist unvollständig (`843acc9`); Kommas als Tausendertrenner sind Formatfehler (`d117024`);
  eine Anschrift zählt als ein Feld (`359f39b`); jeder Wert in einer Lücke gilt als `erfunden`, auch wenn er aus einer anderen Angabe stammt (`e0982dd`).
  Alle Läufe wurden jeweils neu gelabelt.
- `--missing-rate` Standard von 0.25 auf 0.3, bezogen auf jede Feldgruppe einzeln statt auf eine gemeinsame Lücke (`ca15c15`).

## [0.1.0] – 2026-11-03

Vorversuch: Datengenerator, Extraktion auf Modal und erste Läufe.

### Hinzugefügt
- Initiales Grundgerüst mit README und `.gitignore` (`e1fcca3`).
- Generator für synthetische Rechnungen und Verträge mit Ground Truth
  (Faker de_DE → Jinja2 → WeasyPrint → pdfplumber), Pydantic-Schemas, gültige IBANs,
  deutsche Formatierung, fester Anteil von Dokumenten ohne optionale Felder (`9dee697`).
- Extraktion mit Ollama auf Modal: Prompts (Version `v1`), Ollama-Client, Parser für
  Modellantworten, Protokoll je Lauf (`run.json`) und je Dokument, Wiederaufnahme per `--run-id` (`9dee697`).
- Unit-Tests für Common, Generator und Extraktion (`9dee697`).
- Zentrale GPU-Festlegung in `common/hardware.py` samt Test; Extraktion bricht bei falscher
  oder gewechselter GPU ab, GPU-Name wird je Dokument protokolliert (`a47be0c`).
- Datensatz `vorversuch` (10 Rechnungen, 10 Verträge, Seed 42) und fünf Extraktionsläufe (`17a2cf2`).

### Geändert
- Ausgabelimit der Extraktion von 2048 auf 1024 Tokens (vollständige Antworten brauchen ca. 500);
  Wiederholungsschleifen kosten so nur halb so viel Zeit (`d0b7657`).
- GPU-Prüfung verschärft: exakt `NVIDIA A10` statt jeder A10-Variante; zusätzlich
  `check_runs_consistent` für die Auswertung (`b1fabbd`).
- `.gitignore` ignoriert `*.egg-info/` (`d0b7657`).

### Bekannte Einschränkungen
- Lauf `20261103-1517_vorversuch_llama3.2-1b_t0_s42` lief auf `NVIDIA A10G` und ist für
  Latenzvergleiche ungültig; der Probelauf `20261103-1416_…` lief auf `NVIDIA L4` (mit 2048 Tokens Limit).
  Beide bleiben als Dokumentation im Repo, siehe `docs/vorversuch.md`.
- Ollama-Version wird noch nicht fixiert (`OLLAMA_VERSION = None`); erst nach dem Vorversuch festlegen.

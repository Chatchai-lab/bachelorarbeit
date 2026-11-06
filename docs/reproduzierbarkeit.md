# Reproduzierbarkeit

Jedes Ergebnis lässt sich auf Datensatz, Code, Prompt, Modell und Hardware zurückführen.

```mermaid
flowchart TD
    subgraph Daten
        S[Gesamtseed] --> DS[Dokument-Seed<br/>SHA-256 aus Seed, Typ, Index]
        DS --> GT[Ground Truth + Dokumente]
        MF[manifest.json<br/>Versionen, Git-Commit, Parameter]
    end
    subgraph Lauf
        PH[Prompt-Version + Hash]
        MD[Modell-Digest + Quantisierung]
        OP[temperature, seed, num_ctx, num_predict, fmt]
        HW[GPU-Name, Treiber, Ollama-Version, Cloud, Region]
        GC[Git-Commit<br/>-dirty bei ungespeicherten Änderungen]
        RJ[run.json]
        PH & MD & OP & HW & GC --> RJ
    end
    GT --> MF
    MF -. dataset.name/seed .-> RJ
```

## Was wo festgehalten wird

| Ebene | Datei | Inhalt |
|-------|-------|--------|
| Datensatz | `manifest.json` | Seed, Anzahl, `missing_rate`, Generatorversion, Git-Commit, Python- und Paketversionen, Dokumentliste mit Dokument-Seeds und Layout |
| Dokument | `render.json` | Layout, Branche, Ablenker, Absätze |
| Lauf | `run.json` | Modell (Digest, Größe, Quantisierung), Optionen, Ausgabeformat, Prompt-Version und -Hash, GPU, Treiber, Ollama-Version, Cloud, Region, Git-Commit, Start- und Endzeit, Zusammenfassung |
| Labels | `labels.jsonl`, `labels_summary.json` | Status und Fehlertyp je Feld; hängen von der Labeling-Version ab (Git-Commit) und werden bei Änderungen der Heuristik neu berechnet |
| Dokument im Lauf | `docs/<doc_id>.json` | Rohantwort, geparstes JSON, Parsefehler, alle Latenzen, Tokenzahlen, GPU |

## Regeln

1. **Seeds:** Derselbe `--seed` erzeugt dieselbe Ground Truth. Die Auswahl der Dokumente ohne optionale Felder ist ebenfalls seedbasiert.
2. **Prompt:** Jede inhaltliche Änderung erhöht `PROMPT_VERSION`; der Hash fängt vergessene Erhöhungen ab (`prompt_hash()`).
3. **Hardware:** exakt `NVIDIA A10`, erzwungen zur Laufzeit ([hardware.md](hardware.md)).
4. **Git-Commit:** Steht `-dirty` am Commit, gab es beim Start uncommittete Änderungen; solche Läufe nur für Tests verwenden.
5. **Läufe sind unveränderlich.** Neue Läufe bekommen eine neue `--run-id`. Dieselbe ID startet eine Wiederaufnahme.
6. **Temperature 0** im Hauptlauf; Ollama-Seed bleibt trotzdem gesetzt (42).

## Bekannte Grenzen

- Die Ollama-Version ist nicht fixiert (`OLLAMA_VERSION = None`); sie wird protokolliert (aktuell 0.40.14), aber nicht erzwungen.
- GPU-Inferenz ist auch bei Temperature 0 nicht garantiert bitgenau über verschiedene Treiber- oder Ollama-Versionen hinweg.
- Cloud und Region der A10 können wechseln und sind nicht festgelegt, nur protokolliert.
- Die Labels sind abgeleitete Daten: Ändert sich die Labeling-Heuristik, müssen alle Läufe neu gelabelt werden, sonst sind Raten nicht vergleichbar (so geschehen am 05.11., Commits `359f39b`, `d117024`, `e0982dd`).

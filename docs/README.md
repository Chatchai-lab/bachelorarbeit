# Dokumentation

Projektdokumentation zur Bachelorarbeit *Quality-Gates für LLM-Pipelines*
(Halluzinationserkennung bei der Extraktion deutschsprachiger Rechnungen und Verträge).

| Dokument | Inhalt |
|----------|--------|
| [architektur.md](architektur.md) | Gesamtbild: Komponenten, Datenfluss, Ausführungsorte |
| [datenmodell.md](datenmodell.md) | Ground-Truth-Schemas, Konventionen, Dateiformate |
| [generator.md](generator.md) | Erzeugung der synthetischen Dokumente |
| [extraktion.md](extraktion.md) | Prompt, Ollama, Modal-Lauf, Ausgabeformate, Protokoll, Parser |
| [labeling.md](labeling.md) | Abgleich mit der Ground Truth, Status, Fehlertypen |
| [hardware.md](hardware.md) | Warum exakt NVIDIA A10 und wie das erzwungen wird |
| [vorversuch.md](vorversuch.md) | Drei Runden, Läufe, Fehlertypen, Erkenntnisse |
| [reproduzierbarkeit.md](reproduzierbarkeit.md) | Seeds, Protokolle, Versionen |
| [entwicklung.md](entwicklung.md) | Einrichtung, Tests, Konventionen |
| [roadmap.md](roadmap.md) | Offene Bausteine und nächste Schritte |

Siehe auch: [../README.md](../README.md) (Schnellstart), [../CHANGELOG.md](../CHANGELOG.md), [../CLAUDE.md](../CLAUDE.md).

## Überblick

```mermaid
flowchart LR
    G[generator<br/>lokal] -->|Dokumente + Ground Truth| D[(data/datasets)]
    D --> E[extraction<br/>Modal, A10]
    E -->|Extraktionen| R[(data/runs)]
    R --> L[labeling<br/>lokal]
    D -->|Ground Truth| L
    L -->|Labels| C[checks<br/>geplant]
    C --> A[analysis<br/>geplant]

    classDef done fill:#d4edda,stroke:#28a745,color:#000
    classDef todo fill:#fff3cd,stroke:#e0a800,color:#000
    class G,E,L done
    class C,A todo
```

Grün: umgesetzt. Gelb: geplant.

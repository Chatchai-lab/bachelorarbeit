# Architektur

## Komponenten

```mermaid
flowchart TB
    subgraph common["common/ (geteilt)"]
        schemas[schemas.py<br/>Rechnung, Vertrag]
        iban[iban.py]
        fmt[formatting.py]
        hw[hardware.py<br/>GPU-Festlegung]
    end

    subgraph generator["generator/ (lokal)"]
        gmain[__main__.py<br/>CLI + Manifest]
        inv[invoice.py]
        con[contract.py]
        gcom[common.py<br/>Seeds, Firmen, Daten]
        ren[render.py<br/>Jinja2, WeasyPrint, pdfplumber]
        val[validate.py<br/>Werte im Text?]
    end

    subgraph labeling["labeling/ (lokal)"]
        lab[label.py<br/>Status + Fehlertyp]
        nor[normalize.py]
    end

    subgraph extraction["extraction/ (Modal, GPU)"]
        mod[modal_extract.py<br/>Lauf + Protokoll]
        oc[ollama_client.py]
        pr[prompts.py]
        pa[parsing.py]
    end

    gmain --> inv & con
    inv & con --> gcom
    inv & con --> schemas
    gcom --> iban
    ren --> fmt
    gmain --> ren
    gmain --> val
    val --> nor
    lab --> nor
    lab --> pr
    lab --> schemas

    mod --> oc & pr & pa
    mod --> hw
    pr --> schemas
```

## Datenfluss

```mermaid
sequenceDiagram
    autonumber
    actor U as Nutzer
    participant G as generator (lokal)
    participant FS as data/
    participant M as modal_extract (lokal)
    participant X as Modal-Container (A10)
    participant O as Ollama

    U->>G: python -m generator --name vorversuch
    G->>FS: ground_truth.json, document.pdf/.txt, manifest.json
    U->>M: modal run -m extraction.modal_extract
    M->>FS: manifest + document.txt lesen
    M->>X: extract.remote(docs, options, protocol)
    X->>X: nvidia-smi, check_gpu (exakt A10?)
    X->>O: Modell laden, aufwärmen
    loop je Dokument
        X->>O: /api/chat (Prompt + Dokumenttext)
        O-->>X: Antwort + Zeiten + Tokenzahlen
        X->>X: parse_model_output
        X->>X: docs/<doc_id>.json ins Volume
    end
    X-->>M: protocol + records
    M->>FS: data/runs/<run-id>/ (run.json, extractions.jsonl, docs/)
    U->>FS: python -m labeling.label data/runs/<run-id>
    FS-->>U: labels.jsonl, labels_summary.json
```

## Wo läuft was

| Schritt | Ort | Grund |
|---------|-----|-------|
| Generator | lokal | keine Latenzmessung, braucht nur CPU |
| Extraktion | Modal, NVIDIA A10 | Latenz geht in FF3 ein, Hardware muss einheitlich sein |
| Labeling | lokal | keine Latenzmessung |
| Analyse | lokal (geplant) | keine Latenzmessung |
| Prüfstufen | Modal, NVIDIA A10 (geplant) | Latenz geht ein |

## Modal-Ressourcen

| Ressource | Name | Zweck |
|-----------|------|-------|
| App | `ba-extraktion` | Funktion `extract` (GPU `A10`, Timeout 2 h) |
| Volume | `ba-ollama-models` | Modell-Cache (`/models`), Download nur einmal |
| Volume | `ba-results` | Zwischenergebnisse und Wiederaufnahme (`/results`) |

Das Image basiert auf `debian_slim` (Python 3.12) mit installiertem Ollama; `extraction` und `common`
werden als lokale Python-Quellen eingebunden.

## Zielbild der Gesamtpipeline

```mermaid
flowchart LR
    DOC[Dokument<br/>PDF/Text] --> LLM[Extraktionsmodell<br/>1B bis 1.5B]
    LLM --> OUT[Extrahiertes JSON]
    OUT --> Q1[Stufe 1<br/>Regeln]
    Q1 --> Q2[Stufe 2<br/>NLI]
    Q2 --> Q3[Stufe 3<br/>LLM-as-a-Judge]
    Q3 --> ENT{Gate-Entscheidung}
    ENT -->|ok| WEI[weiterverarbeiten]
    ENT -->|auffällig| REV[prüfen / ablehnen]
    GT[(Ground Truth)] -.nur Bewertung.-> EVAL[Precision/Recall/F1<br/>Latenz]
    ENT -.-> EVAL
```

Die Prüfstufen sind geplant (Stand: nicht implementiert) und dürfen die Ground Truth nie sehen.

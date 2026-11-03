"""Extraktion auf Modal (GPU) mit Ollama.

Aufruf aus dem Repo-Wurzelverzeichnis (nach `pip install -e ".[modal]"`):

    # kurzer Test mit 2 Dokumenten
    modal run -m extraction.modal_extract --dataset data/datasets/vorversuch --model llama3.2:1b --limit 2

    # voller Lauf
    modal run -m extraction.modal_extract --dataset data/datasets/vorversuch --model llama3.2:1b
    modal run -m extraction.modal_extract --dataset data/datasets/vorversuch --model qwen2.5:1.5b

    # Laptop zuklappen: Lauf läuft in der Cloud weiter, Ergebnisse liegen im Volume
    modal run --detach -m extraction.modal_extract --dataset ... --model ... --run-id <name>
    modal volume get ba-results <run-id> data/runs/

Wird ein Lauf mit derselben --run-id erneut gestartet, werden bereits
extrahierte Dokumente übersprungen (Wiederaufnahme nach Abbruch).

Ergebnis je Lauf unter data/runs/<run-id>/:
    run.json            Protokoll: Modell, Digest, Quantisierung, Temperature,
                        Seed, Prompt-Version, GPU, Ollama-Version, Git-Commit, Zeiten
    docs/<doc_id>.json  Rohantwort, geparstes JSON, Latenzen, Token je Dokument
    extractions.jsonl   alle Dokumente in einer Datei
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import modal

from common.hardware import MODAL_GPU as GPU  # A10, für die ganze Arbeit festgelegt
# Nach dem Vorversuch auf eine feste Version setzen, z. B. "0.13.0"
OLLAMA_VERSION: str | None = None

_install = "curl -fsSL https://ollama.com/install.sh | " + (f"OLLAMA_VERSION={OLLAMA_VERSION} sh" if OLLAMA_VERSION else "sh")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "ca-certificates", "zstd")
    .run_commands(_install)
    .env({"OLLAMA_MODELS": "/models", "OLLAMA_HOST": "127.0.0.1:11434"})
    .pip_install("pydantic>=2.6")
    .add_local_python_source("extraction", "common")
)

models_volume = modal.Volume.from_name("ba-ollama-models", create_if_missing=True)
results_volume = modal.Volume.from_name("ba-results", create_if_missing=True)

app = modal.App("ba-extraktion", image=image)


@app.function(gpu=GPU, volumes={"/models": models_volume, "/results": results_volume}, timeout=2 * 60 * 60)
def extract(run_id: str, model: str, docs: list[dict], options: dict, fmt: str, protocol: dict) -> dict:
    from extraction import ollama_client as oc
    from extraction.parsing import parse_model_output
    from extraction.prompts import build_messages, json_schema

    oc.start_server()
    if oc.ensure_model(model):
        models_volume.commit()

    from common.hardware import check_gpu

    env = oc.environment_info()
    run_dir = Path("/results") / run_id
    previous_gpu = None
    if (run_dir / "run.json").exists():  # Wiederaufnahme: gleiche GPU erzwingen
        previous_gpu = json.loads((run_dir / "run.json").read_text())["environment"].get("gpu")
    check_gpu(env.get("gpu"), previous_gpu)

    protocol = {
        **protocol,
        "model": oc.model_info(model),
        "environment": env,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print(json.dumps(protocol["model"], indent=2), flush=True)
    print(json.dumps(protocol["environment"], indent=2), flush=True)

    think = False if model.startswith("qwen3") else None  # Qwen3: Denkmodus aus

    # Aufwärmen: Modell in den GPU-Speicher laden, nicht protokolliert
    oc.chat(model, [{"role": "user", "content": "Hallo"}], {**options, "num_predict": 1}, think=think)

    (run_dir / "docs").mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2))
    results_volume.commit()

    records = []
    for i, doc in enumerate(docs, 1):
        out = run_dir / "docs" / f"{doc['doc_id']}.json"
        if out.exists():
            records.append(json.loads(out.read_text()))
            print(f"[{i}/{len(docs)}] {doc['doc_id']}: vorhanden, übersprungen", flush=True)
            continue

        if fmt == "json":
            ollama_format = "json"
        elif fmt == "schema":
            ollama_format = json_schema(doc["doc_type"])
        else:
            ollama_format = None
        messages = build_messages(doc["doc_type"], doc["text"])
        resp = oc.chat(model, messages, options, fmt=ollama_format, think=think)
        parsed, error = parse_model_output(resp["content"])

        record = {
            "doc_id": doc["doc_id"],
            "doc_type": doc["doc_type"],
            "run_id": run_id,
            "model": model,
            "gpu": env.get("gpu"),
            "raw_output": resp.pop("content"),
            "parsed": parsed,
            "parse_error": error,
            **resp,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        results_volume.commit()
        records.append(record)
        status = "ok" if error is None else f"FEHLER: {error}"
        print(f"[{i}/{len(docs)}] {doc['doc_id']}: {resp['wall_ms']:.0f} ms, {status}", flush=True)

    protocol["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    protocol["summary"] = _summary(records)
    (run_dir / "run.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2))
    with open(run_dir / "extractions.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    results_volume.commit()
    return {"protocol": protocol, "records": records}


def _summary(records: list[dict]) -> dict:
    n = len(records)
    errors = sum(r["parse_error"] is not None for r in records)
    lat = sorted(r["wall_ms"] for r in records)
    return {
        "n_docs": n,
        "n_unbrauchbar": errors,
        "anteil_unbrauchbar": round(errors / n, 3) if n else None,
        "latenz_median_ms": lat[n // 2] if n else None,
        "latenz_max_ms": lat[-1] if n else None,
    }


def _git_commit() -> str | None:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.call(["git", "diff", "--quiet"]) != 0
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


@app.local_entrypoint()
def main(
    dataset: str,
    model: str = "llama3.2:1b",
    limit: int = 0,
    doc_type: str = "all",
    temperature: float = 0.0,
    seed: int = 42,
    fmt: str = "none",
    num_ctx: int = 8192,
    run_id: str = "",
):
    """fmt: none (freie Antwort), json (Ollama-JSON-Modus) oder schema (schemagebunden)."""
    from extraction.prompts import PROMPT_VERSION, prompt_hash

    if fmt not in ("none", "json", "schema"):
        raise SystemExit("--fmt muss none, json oder schema sein")

    ds = Path(dataset)
    manifest = json.loads((ds / "manifest.json").read_text(encoding="utf-8"))
    docs = []
    for d in manifest["documents"]:
        if doc_type != "all" and d["doc_type"] != doc_type:
            continue
        text = (ds / d["doc_id"] / "document.txt").read_text(encoding="utf-8")
        docs.append({"doc_id": d["doc_id"], "doc_type": d["doc_type"], "text": text})
    if limit:
        docs = docs[:limit]
    if not docs:
        raise SystemExit("Keine Dokumente gefunden")

    slug = model.replace(":", "-").replace("/", "-")
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M}_{manifest['name']}_{slug}_t{temperature:g}_s{seed}"
    options = {"temperature": temperature, "seed": seed, "num_ctx": num_ctx, "num_predict": 2048}
    protocol = {
        "run_id": run_id,
        "dataset": {"name": manifest["name"], "seed": manifest["seed"], "path": str(ds)},
        "n_docs_requested": len(docs),
        "options": options,
        "output_format": fmt,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "gpu_requested": GPU,
        "git_commit": _git_commit(),
    }
    print(f"Lauf {run_id}: {len(docs)} Dokumente mit {model} auf {GPU}")

    result = extract.remote(run_id, model, docs, options, fmt, protocol)

    out = Path("data/runs") / run_id
    (out / "docs").mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps(result["protocol"], ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "extractions.jsonl", "w", encoding="utf-8") as f:
        for r in result["records"]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            (out / "docs" / f"{r['doc_id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    s = result["protocol"]["summary"]
    print(f"\nFertig: {out}")
    print(f"  unbrauchbare Ausgaben: {s['n_unbrauchbar']}/{s['n_docs']}")
    print(f"  Latenz Median: {s['latenz_median_ms']:.0f} ms, Max: {s['latenz_max_ms']:.0f} ms")

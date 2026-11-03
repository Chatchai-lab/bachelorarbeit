"""Schlanker Ollama-Client (nur Standardbibliothek) und Erfassung der Laufumgebung."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:11434"
NS_TO_MS = 1e-6


def _request(path: str, payload: dict | None = None, timeout: float = 600) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def start_server(log_path: str = "/tmp/ollama.log", wait_s: float = 60) -> subprocess.Popen:
    proc = subprocess.Popen(["ollama", "serve"], stdout=open(log_path, "w"), stderr=subprocess.STDOUT)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            _request("/api/version", timeout=2)
            return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    raise RuntimeError(f"Ollama-Server nicht erreichbar, siehe {log_path}")


def ensure_model(model: str) -> bool:
    """Lädt das Modell, falls es noch nicht vorhanden ist. True, wenn neu geladen."""
    names = {m["name"] for m in _request("/api/tags").get("models", [])}
    if model in names or f"{model}:latest" in names:
        return False
    print(f"Lade Modell {model} ...", flush=True)
    _request("/api/pull", {"model": model, "stream": False}, timeout=3600)
    return True


def model_info(model: str) -> dict:
    tags = _request("/api/tags").get("models", [])
    entry = next((m for m in tags if m["name"] in (model, f"{model}:latest")), {})
    show = _request("/api/show", {"model": model})
    details = show.get("details", {})
    return {
        "name": model,
        "digest": entry.get("digest"),
        "size_bytes": entry.get("size"),
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "format": details.get("format"),
    }


def environment_info() -> dict:
    info: dict = {"ollama_version": _request("/api/version").get("version")}
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            text=True,
        ).strip()
        name, driver, mem = [x.strip() for x in out.splitlines()[0].split(",")]
        info.update(gpu=name, gpu_driver=driver, gpu_memory=mem)
    except (OSError, subprocess.CalledProcessError, ValueError):
        info["gpu"] = None
    info["cpu_count"] = os.cpu_count()
    info["modal_region"] = os.environ.get("MODAL_REGION")
    info["modal_cloud"] = os.environ.get("MODAL_CLOUD_PROVIDER")
    return info


def chat(model: str, messages: list[dict], options: dict, fmt: str | dict | None = None, think: bool | None = None) -> dict:
    payload: dict = {"model": model, "messages": messages, "stream": False, "options": options, "keep_alive": "30m"}
    if fmt is not None:
        payload["format"] = fmt
    if think is not None:
        payload["think"] = think
    t0 = time.perf_counter()
    resp = _request("/api/chat", payload)
    wall_ms = (time.perf_counter() - t0) * 1000
    return {
        "content": resp.get("message", {}).get("content", ""),
        "done_reason": resp.get("done_reason"),
        "wall_ms": round(wall_ms, 1),
        "total_ms": round(resp.get("total_duration", 0) * NS_TO_MS, 1),
        "load_ms": round(resp.get("load_duration", 0) * NS_TO_MS, 1),
        "prompt_eval_ms": round(resp.get("prompt_eval_duration", 0) * NS_TO_MS, 1),
        "eval_ms": round(resp.get("eval_duration", 0) * NS_TO_MS, 1),
        "prompt_tokens": resp.get("prompt_eval_count"),
        "completion_tokens": resp.get("eval_count"),
    }

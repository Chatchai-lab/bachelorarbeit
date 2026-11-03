"""Festgelegte Hardware für alle Modal-Läufe der Bachelorarbeit.

Entscheidung: Alle Läufe (Extraktion und Prüfstufen) laufen auf einer
NVIDIA A10 Tensor Core GPU (24 GB GDDR6, Ampere). Nur so sind die
Latenzen in FF3 vergleichbar.

Achtung: Modal bedient gpu="A10" mit zwei verschiedenen Karten, je nach
Cloud-Anbieter: "NVIDIA A10" (z. B. Oracle Cloud) und "NVIDIA A10G"
(AWS-Variante mit anderen Taktraten). Deshalb wird der exakte Name laut
nvidia-smi geprüft; bei der falschen Variante bricht ein Lauf sofort ab
und muss neu gestartet werden.

Nicht ändern, ohne alle betroffenen Läufe zu wiederholen.
"""

from __future__ import annotations

from collections.abc import Iterable

MODAL_GPU = "A10"
EXPECTED_GPU_NAME = "NVIDIA A10"


class HardwareMismatch(RuntimeError):
    pass


def check_gpu(detected: str | None, previous: str | None = None) -> None:
    """Bricht ab, wenn nicht exakt die festgelegte GPU erkannt wurde oder
    sie sich gegenüber einem früheren Teil desselben Laufs geändert hat."""
    if detected != EXPECTED_GPU_NAME:
        raise HardwareMismatch(
            f"Erwartet {EXPECTED_GPU_NAME!r}, erkannt {detected!r}. "
            "Modal hat eine andere Variante zugewiesen; Lauf bitte neu starten."
        )
    if previous is not None and previous != detected:
        raise HardwareMismatch(
            f"Lauf wurde auf {previous!r} begonnen, jetzt aber {detected!r}. "
            "Wiederaufnahme auf anderer Hardware ist nicht erlaubt; neuen Lauf mit neuer --run-id starten."
        )


def check_runs_consistent(gpus: Iterable[str | None]) -> str:
    """Für die Auswertung: Alle Läufe bzw. Dokumente müssen exakt dieselbe GPU haben.

    Gibt den gemeinsamen GPU-Namen zurück.
    """
    names = set(gpus)
    if names != {EXPECTED_GPU_NAME}:
        raise HardwareMismatch(f"Uneinheitliche oder falsche Hardware in den Läufen: {sorted(map(str, names))}")
    return EXPECTED_GPU_NAME

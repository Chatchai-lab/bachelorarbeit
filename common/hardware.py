"""Festgelegte Hardware für alle Modal-Läufe der Bachelorarbeit.

Entscheidung: Alle Läufe (Vorversuch und Hauptversuch, Extraktion und
Prüfstufen) laufen auf einer NVIDIA A10 Tensor Core GPU (24 GB GDDR6,
Ampere). Nur so sind die Latenzen in FF3 vergleichbar.

Nicht ändern, ohne alle betroffenen Läufe zu wiederholen.
"""

from __future__ import annotations

MODAL_GPU = "A10"
# Teilstring, der im Namen laut nvidia-smi vorkommen muss
EXPECTED_GPU_SUBSTRING = "A10"


class HardwareMismatch(RuntimeError):
    pass


def check_gpu(detected: str | None, previous: str | None = None) -> None:
    """Bricht ab, wenn nicht die festgelegte GPU erkannt wurde oder sie
    sich gegenüber einem früheren Teil desselben Laufs geändert hat."""
    if not detected or EXPECTED_GPU_SUBSTRING not in detected:
        raise HardwareMismatch(f"Erwartet GPU mit '{EXPECTED_GPU_SUBSTRING}', erkannt: {detected!r}")
    if previous is not None and previous != detected:
        raise HardwareMismatch(
            f"Lauf wurde auf {previous!r} begonnen, jetzt aber {detected!r}. "
            "Wiederaufnahme auf anderer Hardware ist nicht erlaubt; neuen Lauf mit neuer --run-id starten."
        )

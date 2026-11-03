import pytest

from common.hardware import HardwareMismatch, check_gpu


def test_a10_akzeptiert():
    check_gpu("NVIDIA A10")
    check_gpu("NVIDIA A10", previous="NVIDIA A10")


def test_andere_gpu_abgelehnt():
    for name in ["Tesla T4", "NVIDIA L4", None]:
        with pytest.raises(HardwareMismatch):
            check_gpu(name)


def test_wechsel_bei_wiederaufnahme_abgelehnt():
    with pytest.raises(HardwareMismatch):
        check_gpu("NVIDIA A10", previous="NVIDIA A10G")

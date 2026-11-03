import pytest

from common.hardware import HardwareMismatch, check_gpu, check_runs_consistent


def test_a10_akzeptiert():
    check_gpu("NVIDIA A10")
    check_gpu("NVIDIA A10", previous="NVIDIA A10")


def test_andere_gpu_abgelehnt():
    for name in ["NVIDIA A10G", "Tesla T4", "NVIDIA L4", None]:
        with pytest.raises(HardwareMismatch):
            check_gpu(name)


def test_wechsel_bei_wiederaufnahme_abgelehnt():
    with pytest.raises(HardwareMismatch):
        check_gpu("NVIDIA A10", previous="NVIDIA A10G")


def test_auswertung_einheitliche_hardware():
    assert check_runs_consistent(["NVIDIA A10", "NVIDIA A10"]) == "NVIDIA A10"
    with pytest.raises(HardwareMismatch):
        check_runs_consistent(["NVIDIA A10", "NVIDIA A10G"])

"""Byte-exact regression guards for original pre-result 3053/3054 states.

Do not normalize immutable historical evidence at runtime or replace its
declared digest. This test checks the original bytes in the Git checkout.
"""
from hashlib import sha256
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
ORIGINALS = (
    "SMART_STATE_ARCHIVE/7410564d72f484eadafdd045d3f4911144b99643fde6b1efe58a1cbf5c535320.json",
    "SMART_STATE_ARCHIVE/3050323b613b6bf5c07e9ce20e59370ab5c5e0b3f030a370a819aacef3734df4.json",
    "SMART_STATE_ARCHIVE/2f7a0b0420f287807938a7bb84c388c0df131380b45eb29edaa289b3396bb02b.json",
)


@pytest.mark.parametrize("relative", ORIGINALS)
def test_original_immutable_state_bytes_and_git_pin(relative: str) -> None:
    path = ROOT / relative
    data = path.read_bytes()
    assert sha256(data).hexdigest() == path.stem
    assert data.count(b"\r\n") > 0
    assert data.count(b"\n") == data.count(b"\r\n")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert f"/{relative} -text" in attributes.splitlines()


def test_original_3054_lf_conversion_is_detected() -> None:
    archive = ROOT / ORIGINALS[1]
    raw = archive.read_bytes()
    converted = raw.replace(b"\r\n", b"\n")
    assert converted != raw
    assert sha256(converted).hexdigest() != archive.stem

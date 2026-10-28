"""Keep historical F12 fail-closed and test narrow, pinned scientific succession."""
from __future__ import annotations
from pathlib import Path

from smart_f12_scientific_successor_v2 import (
    PINNED_FINE_TUNING_LF_SHA256,
    _canonical_hash,
    evaluate,
)

ROOT = Path(__file__).resolve().parent


def test_scoped_successor_only_passes_when_f12_fails_for_exact_scientific_source():
    report = evaluate(ROOT)
    assert report["status"] == "PASS_SCOPE_ONLY", report["checks"]
    assert all(report["checks"].values())
    assert report["prior_gate_live_status"] == "FAIL"
    assert report["effective_model_promotion_authorized"] is False
    assert report["predictive_superiority_proven"] is False


def test_scoped_successor_pins_source_bytes_and_rejects_mutation():
    original = (ROOT / "smart_ai_fine_tuning.py").read_bytes()
    assert _canonical_hash(original) == PINNED_FINE_TUNING_LF_SHA256
    assert _canonical_hash(original + b"\n# unreviewed source change") != PINNED_FINE_TUNING_LF_SHA256


def test_scoped_successor_persisted_report_matches_recomputed():
    import json
    stored = json.loads((ROOT / "SMART_F12_SCIENTIFIC_SUCCESSOR_V2.json").read_text())
    assert stored == evaluate(ROOT)


def test_scoped_successor_pins_unchanged_main_f12_archive():
    from smart_f12_scientific_successor_v2 import PINNED_F12_ARCHIVE_SHA256
    assert PINNED_F12_ARCHIVE_SHA256 == "149b8ac92c6f25855cc6035c8d107608663c4f8e557f292fae7682cf1315b50b"

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import pytest

from smart_f12_scientific_successor import (
    PREDICTIVE_FILE, evaluate, reconstruct_predecessor, _matches_expected_code,
)
from smart_f11_predictive_nonregression import BASELINE_SOURCE_SHA256
from smart_f12_scientific_successor import GUARD_SOURCE_REVERSALS, reconstruct_guard_only_source

ROOT = Path(__file__).resolve().parent


def test_f12_successor_preserves_f11_and_rejects_unproved_superiority():
    actual = evaluate(ROOT)
    assert actual["status"] == "PASS", actual["checks"]
    assert all(actual["checks"].values())
    assert actual["historical_comparison"]["p10"]["total_delta"] == 0
    assert actual["historical_comparison"]["p06"]["approved_for_predictive_promotion"] is False
    assert actual["engineering_consumer_trace_fix_approved"] is True
    assert actual["prospective_advantage_proven"] is False
    assert actual["six_of_six_proven"] is False


def test_f12_persisted_gate_recomputes_without_rewriting_f11():
    stored = json.loads((ROOT / "SMART_F12_SCIENTIFIC_SUCCESSOR.json").read_text(encoding="utf-8"))
    assert stored == evaluate(ROOT)


def test_f12_reconstructed_approved_pipeline_is_bitwise_f11_identity():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    pre = reconstruct_predecessor(source)
    assert pre is not None
    assert _matches_expected_code(pre, BASELINE_SOURCE_SHA256[PREDICTIVE_FILE])


def test_f12_altered_agent_parameters_rejected_even_if_authority_declared():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    tampered = source.replace(b"expected_value != effective_value", b"expected_value == effective_value", 1)
    assert tampered != source
    assert reconstruct_predecessor(tampered) is None or not _matches_expected_code(
        reconstruct_predecessor(tampered), BASELINE_SOURCE_SHA256[PREDICTIVE_FILE]
    )


def test_f12_rejects_unrelated_predictive_code_change():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    tampered = source.replace(b"MAXIMIZE_SIX_HIT_SINGLE_CARD", b"MAXIMIZE_SIX_HIT_SINGLE_BIAS", 1)
    assert tampered != source
    pre = reconstruct_predecessor(tampered)
    assert pre is None or not _matches_expected_code(pre, BASELINE_SOURCE_SHA256[PREDICTIVE_FILE])


def test_f12_cannot_authorize_a_different_runtime_guard():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    tampered = source.replace(b"if _test_identity._authorized_pytest_sandbox(root):", b"if True:", 1)
    assert tampered != source
    assert reconstruct_predecessor(tampered) is None


@pytest.mark.parametrize("path", GUARD_SOURCE_REVERSALS)
def test_f12_other_guard_sources_reconstruct_the_original_f11_bytes(path):
    source = (ROOT / path).read_bytes()
    restored = reconstruct_guard_only_source(path, source)
    assert restored is not None
    assert _matches_expected_code(restored, BASELINE_SOURCE_SHA256[path])
    assert reconstruct_guard_only_source(path, source + b"\nUNAPPROVED_CHANGE = True\n") is None


def test_f12_scientific_successor_accepts_pinned_source_across_git_eol_styles():
    # Only the exact approved predecessor is accepted; checkout EOL is irrelevant.
    raw = (ROOT / PREDICTIVE_FILE).read_bytes()
    expected = BASELINE_SOURCE_SHA256[PREDICTIVE_FILE]
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    for variant in (raw, lf, crlf):
        predecessor = reconstruct_predecessor(variant)
        assert predecessor is not None
        assert _matches_expected_code(predecessor, expected)
    tampered = raw.replace(b"expected_value != effective_value", b"expected_value == effective_value", 1)
    assert tampered != raw
    assert reconstruct_predecessor(tampered) is None

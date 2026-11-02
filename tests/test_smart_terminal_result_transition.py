"""Characterize resumable ingest -> adjudication ordering without rollback."""
from __future__ import annotations

import json
from pathlib import Path
import pytest


def _case(tmp_path):
    from smart_terminal_result_transition import apply_official_result_transition
    payload = {"numbers": [1, 2, 3, 4, 5, 6], "draw_date": "2026-11-02"}
    normalized = {"numbers": payload["numbers"]}
    binding = {"ledger": tmp_path / "ledger.json", "freeze_sha256": "f" * 64}
    calls = []
    state = {"fail_ingest": False, "fail_adjudication": False, "ingest_writes": 0, "adjudication_writes": 0}
    ingest_path, adjudication_path = tmp_path / "ingest.json", tmp_path / "adjudication.json"

    def ensure_ingest(root, actual_payload, binding=None):
        calls.append(("ingest", root, actual_payload, binding))
        if state["fail_ingest"]:
            raise OSError("ingest store unavailable")
        if ingest_path.exists():
            return json.loads(ingest_path.read_text())
        state["ingest_writes"] += 1
        result = {"status": "INGESTED", "actual_numbers": actual_payload["numbers"]}
        ingest_path.write_text(json.dumps(result))
        return result

    def ensure_adjudication(root, actual_numbers, binding=None):
        calls.append(("adjudication", root, actual_numbers, binding))
        if state["fail_adjudication"]:
            raise RuntimeError("adjudication interrupted")
        if adjudication_path.exists():
            result = json.loads(adjudication_path.read_text())
            return {**result, "status": "ALREADY_ADJUDICATED_EVENT_PRESERVED"}
        state["adjudication_writes"] += 1
        result = {"status": "ADJUDICATED", "actual_numbers": actual_numbers}
        adjudication_path.write_text(json.dumps(result))
        return result

    def execute():
        return apply_official_result_transition(
            tmp_path, payload, normalized, binding,
            ensure_ingest=ensure_ingest, ensure_adjudication=ensure_adjudication,
        )

    return payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute


def test_first_execution_preserves_exact_argument_identity_and_order(tmp_path):
    payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute = _case(tmp_path)
    ingest, adjudication = execute()
    assert [name for name, *_ in calls] == ["ingest", "adjudication"]
    assert calls[0][1:] == (tmp_path, payload, binding)
    assert calls[1][1:] == (tmp_path, normalized["numbers"], binding)
    assert ingest["status"] == "INGESTED" and adjudication["status"] == "ADJUDICATED"
    assert state["ingest_writes"] == state["adjudication_writes"] == 1


def test_ingest_failure_blocks_adjudication_without_recovery_fabrication(tmp_path):
    payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute = _case(tmp_path)
    state["fail_ingest"] = True
    with pytest.raises(OSError, match="ingest store unavailable"):
        execute()
    assert [name for name, *_ in calls] == ["ingest"]
    assert not ingest_path.exists() and not adjudication_path.exists()


def test_interrupted_after_ingest_reuses_same_evidence_on_restart(tmp_path):
    payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute = _case(tmp_path)
    state["fail_adjudication"] = True
    with pytest.raises(RuntimeError, match="adjudication interrupted"):
        execute()
    frozen_ingest = ingest_path.read_bytes()
    assert state["ingest_writes"] == 1 and state["adjudication_writes"] == 0
    assert not adjudication_path.exists()
    state["fail_adjudication"] = False
    ingest, adjudication = execute()
    assert ingest_path.read_bytes() == frozen_ingest
    assert ingest["status"] == "INGESTED" and adjudication["status"] == "ADJUDICATED"
    assert state["ingest_writes"] == 1 and state["adjudication_writes"] == 1
    assert [name for name, *_ in calls] == ["ingest", "adjudication"] * 2


def test_completed_execution_replay_preserves_both_artifacts(tmp_path):
    payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute = _case(tmp_path)
    execute()
    frozen_ingest, frozen_adjudication = ingest_path.read_bytes(), adjudication_path.read_bytes()
    ingest, adjudication = execute()
    assert state["ingest_writes"] == state["adjudication_writes"] == 1
    assert ingest_path.read_bytes() == frozen_ingest
    assert adjudication_path.read_bytes() == frozen_adjudication
    assert adjudication["status"] == "ALREADY_ADJUDICATED_EVENT_PRESERVED"


def test_already_ingested_not_reverted_if_adjudication_fails_repeatedly(tmp_path):
    payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute = _case(tmp_path)
    state["fail_adjudication"] = True
    for _ in range(3):
        with pytest.raises(RuntimeError, match="adjudication interrupted"):
            execute()
    assert state["ingest_writes"] == 1
    assert state["adjudication_writes"] == 0
    assert ingest_path.is_file() and not adjudication_path.exists()


@pytest.mark.parametrize("mutation", ["missing_numbers", "wrong_type"])
def test_invalid_normalized_evidence_propagates_without_adjudication(tmp_path, mutation):
    from smart_terminal_result_transition import apply_official_result_transition
    payload, normalized, binding, calls, state, ingest_path, adjudication_path, execute = _case(tmp_path)
    bad = {} if mutation == "missing_numbers" else {"numbers": object()}
    def reject(root, numbers, binding=None):
        raise TypeError("invalid official numbers")
    with pytest.raises((KeyError, TypeError)):
        apply_official_result_transition(tmp_path, payload, bad, binding,
            ensure_ingest=lambda root, data, binding=None: {"status":"INGESTED"},
            ensure_adjudication=reject)


def test_callback_failure_is_not_recast_as_waiting_or_scientific_proof(tmp_path):
    from smart_terminal_result_transition import apply_official_result_transition
    def fail(*args, **kwargs):
        raise ValueError("invalid frozen authority")
    with pytest.raises(ValueError, match="invalid frozen authority"):
        apply_official_result_transition(tmp_path, {"numbers": [1]*6},
            {"numbers": [1]*6}, {"ledger": "locked"},
            ensure_ingest=lambda *args, **kwargs: {"status":"INGESTED"},
            ensure_adjudication=fail)

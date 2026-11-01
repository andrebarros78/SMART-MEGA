"""Frozen post-adjudication learning and sequence proof must remain ordered."""
from __future__ import annotations
import pytest

from smart_terminal_sequential_learning import ensure_learning_and_sequence


def _case(tmp_path, *, initial_events=()):
    ledger_path = tmp_path / "ledger.json"
    learned_path = tmp_path / "learned.json"
    data = tmp_path / "result.xlsx"
    binding = {"ledger": ledger_path, "learned": learned_path}
    recorded = {"events": [dict(item) for item in initial_events]}
    calls = []
    def load_ledger(path):
        calls.append(("load", path))
        return recorded
    def events(ledger, event_type):
        return [event for event in ledger["events"] if event.get("event_type") == event_type]
    def append_learning(path, target, state, result):
        calls.append(("learning", path, target, state, result))
        recorded["events"].append({"event_type": "LEARNING_UPDATE"})
    def append_proof(path, target):
        calls.append(("proof", path, target))
        recorded["events"].append({"event_type": "SEQUENTIAL_PROOF"})
    def verify(ledger, target, **kwargs):
        calls.append(("verify", target, kwargs, len(ledger["events"])))
        return {"valid": True, "status": "PASS"}
    config=dict(
        target=3080, result_data="result.xlsx",
        learning_event="LEARNING_UPDATE", proof_event="SEQUENTIAL_PROOF",
        load_ledger=load_ledger, target_events=events,
        append_learning_update=append_learning,
        append_sequence_proof=append_proof,
        validate_target_sequence=verify,
    )
    def run():
        return ensure_learning_and_sequence(tmp_path, binding, **config)
    return config, calls, recorded, run


def test_sequence_appends_learning_before_proof_and_validates(tmp_path):
    cfg, calls, ledger, run = _case(tmp_path)
    out=run()
    assert out == {"valid": True, "status": "PASS"}
    learning=[c for c in calls if c[0]=="learning"]
    proof=[c for c in calls if c[0]=="proof"]
    assert learning == [("learning", tmp_path/"ledger.json", 3080,
                         tmp_path/"learned.json", tmp_path/"result.xlsx")]
    assert proof == [("proof", tmp_path/"ledger.json", 3080)]
    assert calls.index(learning[0]) < calls.index(proof[0])
    verified=next(c for c in calls if c[0]=="verify")
    assert verified == ("verify", 3080, {
        "require_learning": True, "require_proof": True,
        "verify_files": True, "root": tmp_path,
    }, 2)


def test_existing_verified_sequence_is_idempotent(tmp_path):
    existing=({"event_type":"LEARNING_UPDATE"}, {"event_type":"SEQUENTIAL_PROOF"})
    cfg, calls, ledger, run = _case(tmp_path, initial_events=existing)
    assert run()["valid"] is True
    assert not [c for c in calls if c[0] in {"learning","proof"}]


def test_missing_proof_is_appended_without_repeating_learning(tmp_path):
    cfg, calls, ledger, run = _case(tmp_path,initial_events=({"event_type":"LEARNING_UPDATE"},))
    assert run()["valid"] is True
    assert [c[0] for c in calls if c[0] in {"learning","proof"}] == ["proof"]


@pytest.mark.parametrize("kind", ["LEARNING_UPDATE", "SEQUENTIAL_PROOF"])
def test_duplicate_events_fail_before_mutation(tmp_path, kind):
    cfg, calls, ledger, run = _case(tmp_path,initial_events=(
        {"event_type":kind}, {"event_type":kind}))
    with pytest.raises(ValueError, match="duplicate target learning/proof events"):
        run()
    assert not [c for c in calls if c[0] in {"learning", "proof","verify"}]


def test_invalid_final_sequence_blocks_success(tmp_path):
    cfg, calls, ledger, run = _case(tmp_path)
    cfg["validate_target_sequence"]=lambda *args, **kwargs: {"valid":False}
    with pytest.raises(RuntimeError, match="target sequential proof validation failed"):
        run()


def test_proof_raises_without_masking_error(tmp_path):
    cfg, calls, ledger, run = _case(tmp_path)
    cfg["append_sequence_proof"]=lambda *args: (_ for _ in ()).throw(ValueError("invalid frozen lineage"))
    with pytest.raises(ValueError, match="invalid frozen lineage"):
        run()


def test_learning_failure_prevents_proof_creation(tmp_path):
    cfg, calls, ledger, run = _case(tmp_path)
    cfg["append_learning_update"]=lambda *args: (_ for _ in ()).throw(ValueError("learning not eligible"))
    with pytest.raises(ValueError, match="learning not eligible"):
        run()
    assert not [c for c in calls if c[0]=="proof"]
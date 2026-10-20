from __future__ import annotations

import hashlib

import pytest

import smart_3054_terminal_executor as engine


@pytest.mark.parametrize("resuming_partial", [False, True])
def test_historical_evidence_gate_precedes_all_result_writes(tmp_path, monkeypatch, resuming_partial):
    freeze = tmp_path / "freeze.json"
    freeze.write_bytes(b"immutable-frozen-prediction")
    ledger = tmp_path / "ledger.json"
    ledger.write_text('{"events":[]}', encoding="utf-8")
    original = ledger.read_bytes()
    binding = {
        "mode": "ACTIVE_EPOCH",
        "freeze": freeze,
        "freeze_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(),
        "ledger": ledger,
        "state": tmp_path / "state.json",
        "data": tmp_path / "cutoff.xlsx",
    }
    monkeypatch.setattr(engine, "TARGET", 9001)
    monkeypatch.setattr(engine, "_runtime_binding", lambda root: binding)
    events = [{"event_type":"ADJUDICATION", "target_contest":9001}] if resuming_partial else []
    monkeypatch.setattr(engine.champion_challenger, "load_ledger", lambda path: {"events":events})
    monkeypatch.setattr(engine, "_preflight_readiness", lambda root, b: {"readiness_status":"PASS"})

    payload = {"numero": 9001, "listaDezenas": ["01", "02", "03", "04", "05", "06"]}
    consensus = {"primary": {"validated": True}}

    if resuming_partial:
        monkeypatch.setattr(engine, "_load_existing_official_evidence", lambda root: (payload, consensus))

        def fetch(target):
            raise RuntimeError("offline result source")
    else:
        monkeypatch.setattr(engine, "_load_existing_official_evidence", lambda root: None)

        def fetch(target):
            return payload, consensus

    def unavailable_history(*args, **kwargs):
        raise ValueError("frozen artifact missing")

    def illegal_mutation(*args, **kwargs):
        raise AssertionError("write attempted before historical freeze audit")

    monkeypatch.setattr(engine.independent_audit, "audit_prospective_ledger", unavailable_history)
    for name in (
        "_ensure_primary_payload",
        "_ensure_monotonic_consensus",
        "_ensure_ingest",
        "_ensure_adjudication",
        "_ensure_learned_state",
        "_ensure_learning_and_sequence",
    ):
        monkeypatch.setattr(engine, name, illegal_mutation)

    with pytest.raises(ValueError, match="frozen artifact missing"):
        engine.execute(tmp_path, fetcher=fetch)

    assert ledger.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["freeze.json", "ledger.json"]

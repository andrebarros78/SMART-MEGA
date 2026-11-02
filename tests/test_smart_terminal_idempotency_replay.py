"""Immutable ingest and adjudication replay without duplicate writes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from smart_terminal_idempotency import (
    verified_existing_ingest, replay_existing_adjudication,
)


def _ingest_case(tmp_path):
    output, proof_path = tmp_path / "result.xlsx", tmp_path / "ingest.json"
    output.write_bytes(b"official-row")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    evidence = {"target_contest": 3080, "actual_numbers": [1,2,3,4,5,6],
                "output_sha256": digest, "status": "INGESTED"}
    proof_path.write_text(json.dumps(evidence), encoding="utf-8")
    calls = []
    def load(path):
        calls.append(("read",path))
        return json.loads(path.read_text())
    def fingerprint(path):
        calls.append(("hash",path))
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def draws(path):
        calls.append(("draws",path))
        return [], [3079,3080]
    opts = dict(read_json=load, sha256_file=fingerprint, load_draws=draws)
    def run():
        return verified_existing_ingest(
            output, proof_path, {"numbers":[1,2,3,4,5,6]}, target=3080,
            **opts)
    return output, proof_path, evidence, calls, opts, run


def test_missing_ingest_and_proof_returns_none_without_read(tmp_path):
    calls=[]
    assert verified_existing_ingest(tmp_path/"out.xlsx", tmp_path/"proof.json",
        {"numbers":[1,2,3,4,5,6]}, target=3080,
        read_json=lambda x: calls.append("read"),
        sha256_file=lambda x: calls.append("hash"),
        load_draws=lambda x: calls.append("draws")) is None
    assert calls == []


@pytest.mark.parametrize("missing", ["proof","output"])
def test_partial_ingest_is_rejected_before_content_checks(tmp_path, missing):
    output, proof, evidence, calls, opts, run = _ingest_case(tmp_path)
    (proof if missing == "proof" else output).unlink()
    with pytest.raises(ValueError, match="official result ingest is partially present"):
        run()
    assert calls == []


def test_complete_existing_ingest_is_reused_unchanged(tmp_path):
    output, proof, evidence, calls, opts, run = _ingest_case(tmp_path)
    data_before = output.read_bytes()
    proof_before = proof.read_bytes()
    assert run() == evidence
    assert calls == [("read",proof),("hash",output),("draws",output)]
    assert output.read_bytes() == data_before and proof.read_bytes() == proof_before


@pytest.mark.parametrize("bad,match", [
    ("target","proof conflicts with official result"),
    ("numbers","proof conflicts with official result"),
    ("hash","output hash mismatch"),
    ("last","does not end at target"),
])
def test_conflicting_ingest_replay_rejected_without_write(tmp_path, bad, match):
    output, proof, evidence, calls, opts, run = _ingest_case(tmp_path)
    if bad == "target": evidence["target_contest"] = 3079
    if bad == "numbers": evidence["actual_numbers"] = [1,2,3,4,5,7]
    if bad == "hash": evidence["output_sha256"] = "0"*64
    if bad == "last": opts["load_draws"] = lambda path: ([],[3079,3079])
    proof.write_text(json.dumps(evidence), encoding="utf-8")
    saved = proof.read_bytes()
    with pytest.raises(ValueError, match=match):
        run()
    assert proof.read_bytes() == saved


def test_replay_ingest_dependency_error_propagates(tmp_path):
    output, proof, evidence, calls, opts, run = _ingest_case(tmp_path)
    opts["sha256_file"] = lambda path: (_ for _ in ()).throw(OSError("hash unavailable"))
    with pytest.raises(OSError, match="hash unavailable"):
        run()


def _adjudication_case():
    event = {"actual_numbers":[6,5,4,3,2,1],"freeze_sha256":"f"*64,
             "champion_hits":"3","challenger_hits":"1","e_value_after":"2.5"}
    return event


def test_no_adjudication_returns_none():
    assert replay_existing_adjudication([], [1,2,3,4,5,6], "f"*64, 3080) is None


def test_existing_adjudication_preserves_report_and_source():
    event = _adjudication_case()
    before = copy.deepcopy(event)
    result = replay_existing_adjudication([event],[1,2,3,4,5,6],"f"*64,3080)
    assert result == {"status":"ALREADY_ADJUDICATED_EVENT_PRESERVED",
        "target_contest":3080,"actual_numbers":[6,5,4,3,2,1],
        "champion_hits":3,"challenger_hits":1,"e_value_after":2.5}
    assert result["actual_numbers"] is event["actual_numbers"]
    assert event == before


@pytest.mark.parametrize("bad,match", [
    ("duplicates","multiple 3054 adjudications are forbidden"),
    ("numbers","conflicts with official result"),
    ("freeze","outside the active epoch"),
])
def test_existing_adjudication_rejects_conflicts(bad,match):
    event = _adjudication_case()
    events=[event]
    if bad == "duplicates": events.append(dict(event))
    if bad == "numbers": event["actual_numbers"] = [1,2,3,4,5,7]
    if bad == "freeze": event["freeze_sha256"] = "e"*64
    with pytest.raises(ValueError,match=match):
        replay_existing_adjudication(events,[1,2,3,4,5,6],"f"*64,3080)


def test_corrupt_replay_numeric_fields_fail_closed():
    event=_adjudication_case()
    event["champion_hits"]="not-int"
    with pytest.raises(ValueError):
        replay_existing_adjudication([event],[1,2,3,4,5,6],"f"*64,3080)


def test_replay_does_not_invent_result_metadata():
    event=_adjudication_case()
    event.pop("e_value_after")
    with pytest.raises(KeyError,match="e_value_after"):
        replay_existing_adjudication([event],[1,2,3,4,5,6],"f"*64,3080)

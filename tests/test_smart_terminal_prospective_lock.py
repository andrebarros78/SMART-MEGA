"""Characterization of legacy prospective lock authority binding."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from smart_terminal_prospective_lock import preserved_lock_binding


def _fixture(tmp_path):
    for name, payload in (
        ("freeze.json", b"frozen-choice"),
        ("history.xlsx", b"causal-history"),
        ("signal.json", b"causal-signal"),
        ("ledger.json", b"immutable-ledger"),
    ):
        (tmp_path / name).write_bytes(payload)

    def fingerprint(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    sha = lambda filename: fingerprint(tmp_path / filename)
    authority = {
        "target_contest": 3080,
        "cutoff_contest": 3079,
        "eligible_for_scientific_adjudication": True,
        "eligible_to_prove_post_freeze_engineering_version": False,
        "immutable_until_adjudication": True,
        "freeze_file": "freeze.json", "freeze_sha256": sha("freeze.json"),
        "data_file": "history.xlsx", "data_sha256": sha("history.xlsx"),
        "signal_state_file": "signal.json", "signal_state_sha256": sha("signal.json"),
        "ledger_file": "ledger.json", "ledger_sha256": sha("ledger.json"),
    }
    lock = {"experiment_authority": authority}
    events = []
    recorded = {"events": events}
    freeze_event = {"freeze_sha256": authority["freeze_sha256"]}

    def execute():
        return preserved_lock_binding(
            tmp_path, target=3080, cutoff=3079, learned_state="learned.json",
            verify_lock=lambda path: lock, sha256_file=fingerprint,
            load_ledger=lambda path: recorded,
            active_freeze=lambda ledger, target: freeze_event,
            target_events=lambda ledger, kind: [
                event for event in ledger["events"] if event["event_type"] == kind
            ],
        )
    return authority, events, freeze_event, execute


def test_unadjudicated_lock_preserves_read_only_authority(tmp_path):
    authority, events, freeze_event, execute = _fixture(tmp_path)
    binding = execute()
    assert binding == {
        "mode": "LOCKED_PROSPECTIVE_AUTHORITY",
        "freeze": tmp_path / "freeze.json",
        "freeze_sha256": authority["freeze_sha256"],
        "ledger": tmp_path / "ledger.json",
        "state": tmp_path / "signal.json",
        "data": tmp_path / "history.xlsx",
        "learned": tmp_path / "learned.json",
    }
    assert not events
    assert not (tmp_path / "learned.json").exists()


def test_adjudicated_lock_accepts_bound_single_result(tmp_path):
    authority, events, freeze_event, execute = _fixture(tmp_path)
    events.append({
        "event_type": "ADJUDICATION",
        "freeze_sha256": authority["freeze_sha256"],
        "actual_numbers": [1, 12, 23, 34, 45, 56],
    })
    assert execute()["mode"] == "LOCKED_PROSPECTIVE_AUTHORITY"


@pytest.mark.parametrize("mutation, expected", [
    ("wrong_target", "target/cutoff mismatch"),
    ("no_science", "lacks scientific adjudication"),
    ("future_engineering", "falsely credit post-freeze engineering"),
    ("mutable", "not immutable"),
    ("missing_ledger", "ledger missing"),
    ("changed_data", "dependency mismatch"),
    ("changed_ledger", "ledger hash changed"),
    ("wrong_freeze", "active frozen attempt"),
    ("duplicate", "multiple 3054 adjudications"),
    ("unbound_adjudication", "not bound to the preserved freeze"),
    ("invalid_result", "actual numbers are invalid"),
])
def test_lock_binding_fails_closed_for_invalid_evidence(tmp_path, mutation, expected):
    authority, events, freeze_event, execute = _fixture(tmp_path)
    if mutation == "wrong_target":
        authority["target_contest"] += 1
    elif mutation == "no_science":
        authority["eligible_for_scientific_adjudication"] = False
    elif mutation == "future_engineering":
        authority["eligible_to_prove_post_freeze_engineering_version"] = True
    elif mutation == "mutable":
        authority["immutable_until_adjudication"] = False
    elif mutation == "missing_ledger":
        (tmp_path / "ledger.json").unlink()
    elif mutation == "changed_data":
        (tmp_path / "history.xlsx").write_bytes(b"changed")
    elif mutation == "changed_ledger":
        (tmp_path / "ledger.json").write_bytes(b"changed")
    elif mutation == "wrong_freeze":
        freeze_event["freeze_sha256"] = "0" * 64
    elif mutation == "duplicate":
        events.extend([
            {"event_type": "ADJUDICATION"},
            {"event_type": "ADJUDICATION"},
        ])
    elif mutation == "unbound_adjudication":
        events.append({
            "event_type": "ADJUDICATION",
            "freeze_sha256": "1" * 64, "actual_numbers": [1, 2, 3, 4, 5, 6],
        })
    else:
        events.append({
            "event_type": "ADJUDICATION",
            "freeze_sha256": authority["freeze_sha256"],
            "actual_numbers": [1, 1, 3, 4, 5, 6],
        })
    with pytest.raises(ValueError, match=expected):
        execute()
"""Characterization of frozen active-epoch terminal authority resolution."""
from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from smart_terminal_active_epoch import active_epoch_binding


def _scenario(tmp_path):
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text("{}", encoding="utf-8")
    for name, data in (("freeze.json", b"frozen"), ("ledger.json", b"ledger"),
                       ("state.json", b"state"), ("data.xlsx", b"data")):
        (epoch / name).write_bytes(data)

    def fingerprint(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    freeze_hash = fingerprint(epoch / "freeze.json")
    freeze_doc = {
        "target_contest": 3080, "cutoff_contest": 3079,
        "frozen_before_result": True, "causal_cutoff": True,
    }
    active = {
        "target_contest": 3080, "cutoff_contest": 3079,
        "status": "FROZEN", "result_used": False,
        "data_file": "epoch/data.xlsx",
        "data_sha256": fingerprint(epoch / "data.xlsx"),
        "state_paths": {"freeze": "epoch/freeze.json", "ledger": "epoch/ledger.json",
                        "state": "epoch/state.json"},
        "freeze_authority": {
            "target_contest": 3080, "cutoff_contest": 3079, "sha256": freeze_hash,
        },
        "learning_state_authority": {"sha256": fingerprint(epoch / "state.json")},
        "ledger_sha256": fingerprint(epoch / "ledger.json"),
    }
    current = {
        "status": "FROZEN", "target_contest": 3080,
        "freeze_authority_present": True, "generation_proof_valid": True,
        "freeze_sha256": freeze_hash,
    }
    ledger_doc = {"events": []}
    freeze_event = {"freeze_sha256": freeze_hash}
    temporal_calls = []

    def project_local(root, relative, label):
        result = (root / relative).resolve()
        result.relative_to(root.resolve())
        return result

    def execute():
        return active_epoch_binding(
            tmp_path, target=3080, cutoff=3079,
            learned_state="learned.json", verify_active_epoch=lambda path: active,
            project_local=project_local, sha256_file=fingerprint,
            read_json=lambda path: freeze_doc,
            load_ledger=lambda path: ledger_doc,
            active_freeze=lambda ledger, target: freeze_event,
            target_events=lambda ledger, kind: [
                event for event in ledger["events"] if event["event_type"] == kind
            ],
            resolve_current_epoch=lambda root: current,
            validate_temporal_guard=lambda a, f, t: temporal_calls.append(t),
        )
    return active, freeze_doc, current, ledger_doc["events"], freeze_event, temporal_calls, execute


def test_no_active_epoch_returns_none_without_creating_files(tmp_path):
    *_, execute = _scenario(tmp_path)
    (tmp_path / "SMART_ACTIVE_EPOCH.json").unlink()
    assert execute() is None
    assert not (tmp_path / "epoch/learned.json").exists()


def test_different_active_target_does_not_grant_current_authority(tmp_path):
    active, *_, execute = _scenario(tmp_path)
    active["target_contest"] = 3079
    assert execute() is None


def test_frozen_epoch_resolves_current_freeze_and_immutable_paths(tmp_path):
    active, freeze_doc, current, events, freeze_event, guard, execute = _scenario(tmp_path)
    binding = execute()
    assert binding["mode"] == "ACTIVE_EPOCH"
    assert binding["freeze"] == (tmp_path / "epoch/freeze.json").resolve()
    assert binding["ledger"] == (tmp_path / "epoch/ledger.json").resolve()
    assert binding["data"] == (tmp_path / "epoch/data.xlsx").resolve()
    assert binding["learned"] == (tmp_path / "epoch/learned.json").resolve()
    assert binding["current"] is current
    assert guard == []
    assert not (tmp_path / "epoch/learned.json").exists()


def test_adjudicated_epoch_recovery_does_not_restore_generation_authority(tmp_path):
    active, freeze_doc, current, events, freeze_event, guard, execute = _scenario(tmp_path)
    events.append({
        "event_type": "ADJUDICATION",
        "freeze_sha256": active["freeze_authority"]["sha256"],
        "actual_numbers": [1, 12, 23, 34, 45, 56],
        "retroactive_rewrite": False,
    })
    binding = execute()
    assert binding["mode"] == "ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY"
    assert binding["current"]["generation_proof_valid"] is False
    assert binding["current"]["historical_pre_result_authority_preserved"] is True
    assert guard == [3080]


@pytest.mark.parametrize("mutation, expected", [
    ("cutoff", "target/cutoff mismatch"),
    ("not_frozen", "not a frozen authority"),
    ("state_paths", "state paths missing"),
    ("missing_data", "cutoff data missing"),
    ("freeze_hash", "freeze hash mismatch"),
    ("freeze_authority_target", "freeze authority target/cutoff mismatch"),
    ("data_hash", "cutoff data hash mismatch"),
    ("state_hash", "learning state hash mismatch"),
    ("document_target", "freeze document target/cutoff mismatch"),
    ("not_causal", "freeze is not causally pre-result"),
    ("ledger_freeze", "ledger does not preserve"),
    ("current_unverified", "lacks frozen generation authority"),
    ("current_freeze", "current epoch freeze differs"),
    ("ledger_hash", "ledger hash changed"),
    ("duplicate_adjudication", "multiple target adjudications"),
    ("retroactive", "permits retroactive rewrite"),
    ("bad_result", "adjudication numbers are invalid"),
])
def test_binding_rejects_corrupt_authority_without_writes(tmp_path, mutation, expected):
    active, freeze_doc, current, events, freeze_event, guard, execute = _scenario(tmp_path)
    if mutation == "cutoff":
        active["cutoff_contest"] = 3078
    elif mutation == "not_frozen":
        active["status"] = "PREPARING"
    elif mutation == "state_paths":
        active["state_paths"] = None
    elif mutation == "missing_data":
        (tmp_path / "epoch/data.xlsx").unlink()
    elif mutation == "freeze_hash":
        active["freeze_authority"]["sha256"] = "b" * 64
    elif mutation == "freeze_authority_target":
        active["freeze_authority"]["target_contest"] = 4000
    elif mutation == "data_hash":
        active["data_sha256"] = "b" * 64
    elif mutation == "state_hash":
        active["learning_state_authority"]["sha256"] = "b" * 64
    elif mutation == "document_target":
        freeze_doc["target_contest"] = 4000
    elif mutation == "not_causal":
        freeze_doc["causal_cutoff"] = False
    elif mutation == "ledger_freeze":
        freeze_event["freeze_sha256"] = "b" * 64
    elif mutation == "current_unverified":
        current["generation_proof_valid"] = False
    elif mutation == "current_freeze":
        current["freeze_sha256"] = "b" * 64
    elif mutation == "ledger_hash":
        active["ledger_sha256"] = "b" * 64
    else:
        events.append({
            "event_type": "ADJUDICATION",
            "freeze_sha256": active["freeze_authority"]["sha256"],
            "actual_numbers": [1, 2, 3, 4, 5, 6],
            "retroactive_rewrite": False,
        })
        if mutation == "duplicate_adjudication":
            events.append(dict(events[-1]))
        elif mutation == "retroactive":
            events[-1]["retroactive_rewrite"] = True
        elif mutation == "bad_result":
            events[-1]["actual_numbers"] = [1, 1, 3, 4, 5, 6]
    with pytest.raises(ValueError, match=expected):
        execute()
    assert not (tmp_path / "epoch/learned.json").exists()
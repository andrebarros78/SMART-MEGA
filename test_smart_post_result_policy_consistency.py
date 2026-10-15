"""TDD: post-result learning must reproduce the policy frozen before the draw."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import smart_terminal_engine as terminal


def _prestate(target: int) -> dict:
    from smart_signal_agent import SmartSignalAgent
    agent = SmartSignalAgent(start=30)
    agent._configure_target_profile(target)
    agent._reset_states()
    return {
        "last_contest": target - 1,
        "start_index": agent.start,
        "eta": agent.eta,
        "redundancy_consensus_threshold": agent.redundancy_threshold,
        "meta_strength": agent.meta_strength,
        "calibration_strength": agent.calibration_strength,
        "architecture_profile": agent.architecture_profile,
        "online_learning_max_abs_step": agent.online_max_abs_step,
        "data_sha256": "a" * 64,
    }


def test_post_result_agent_preserves_hardened_policy_of_frozen_target():
    original = _prestate(3070)
    replay = terminal._agent_from_prestate(original, target_contest=3070)
    assert replay.architecture_profile == "DIVERSITY_HARDENED_V1"
    assert replay.online_max_abs_step == 0.75
    assert replay.expert_learning_guard.max_abs_step == 0.75
    assert replay.family_learning_guard.max_abs_step == 0.75
    assert replay.redundancy_threshold == original["redundancy_consensus_threshold"]


def test_pre_hardening_legacy_policy_is_maintained():
    original = _prestate(3055)
    replay = terminal._agent_from_prestate(original, target_contest=3055)
    assert replay.architecture_profile == "LEGACY_COMPATIBLE"
    assert replay.expert_learning_guard.max_abs_step == 2.5
    assert replay.redundancy_threshold == original["redundancy_consensus_threshold"]


def test_inconsistent_frozen_policy_is_rejected_instead_of_recalibrated():
    original = _prestate(3070)
    original["online_learning_max_abs_step"] = 2.5
    with pytest.raises(ValueError, match="frozen.*policy|profile.*mismatch"):
        terminal._agent_from_prestate(original, target_contest=3070)


def test_already_persisted_inconsistent_learning_cannot_be_silently_reused(tmp_path, monkeypatch):
    """Idempotence must not accept a state learned under the wrong profile."""
    target = 3070
    original = _prestate(target)
    learned = {
        "last_contest": target, "data_sha256": "c" * 64,
        "architecture_profile": "LEGACY_COMPATIBLE",
        "online_learning_max_abs_step": 2.5,
        "redundancy_consensus_threshold": 0.85,
    }
    old = tmp_path / "SMART_SIGNAL_STATE_3070_LEARNED.json"
    old.write_text(json.dumps(learned), encoding="utf-8")
    before = old.read_bytes()
    pre = tmp_path / "SMART_SIGNAL_STATE.json"
    pre.write_text(json.dumps(original), encoding="utf-8")
    through = tmp_path / "through.xlsx"
    through.write_bytes(b"original history untouched")
    monkeypatch.setattr(terminal, "RESULT_DATA", through.name)
    monkeypatch.setattr(terminal, "TARGET", target)
    monkeypatch.setattr(terminal, "CUTOFF", target - 1)
    monkeypatch.setattr(terminal, "sha256_file", lambda p: "c" * 64 if Path(p) == through else "a" * 64)
    binding = {"learned": old, "state": pre, "data": tmp_path / "before.xlsx"}
    with pytest.raises(ValueError, match="learned state.*policy|legacy learned state"):
        terminal._ensure_learned_state(tmp_path, binding)
    assert old.read_bytes() == before


def test_calibration_cannot_be_implicitly_promoted_from_prestate():
    frozen = _prestate(3070)
    frozen["calibration_strength"] = 0.5
    with pytest.raises(ValueError, match="independent promotion authority"):
        terminal._agent_from_prestate(frozen, target_contest=3070)


def test_consistent_post_result_state_is_idempotently_reused(tmp_path, monkeypatch):
    frozen = _prestate(3070)
    frozen["training_rows"] = 2069
    frozen["bounded_online_learning"] = {
        "expert": {"clipped_update_count": 2598},
        "family": {"clipped_update_count": 437},
    }
    frozen["meta_governor"] = {"selected_cumulative_hits": 1244}
    learned = {
        "last_contest": 3070, "data_sha256": "c"*64,
        "architecture_profile": frozen["architecture_profile"],
        "online_learning_max_abs_step": frozen["online_learning_max_abs_step"],
        "redundancy_consensus_threshold": frozen["redundancy_consensus_threshold"],
        "calibration_strength": 0.0,
        "training_rows": 2070,
        "bounded_online_learning": {
            "expert": {"max_abs_step": 0.75, "clipped_update_count": 2599},
            "family": {"max_abs_step": 0.75, "clipped_update_count": 439},
        },
        "meta_governor": {"selected_cumulative_hits": 1246},
    }
    pre_path = tmp_path / "SMART_SIGNAL_STATE.json"
    pre_path.write_text(json.dumps(frozen), encoding="utf-8")
    learned_path = tmp_path / "SMART_SIGNAL_STATE_3070_LEARNED.json"
    learned_path.write_text(json.dumps(learned), encoding="utf-8")
    through = tmp_path / "through.xlsx"
    through.write_bytes(b"data existing")
    before = learned_path.read_bytes()
    monkeypatch.setattr(terminal, "RESULT_DATA", through.name)
    monkeypatch.setattr(terminal, "TARGET", 3070)
    monkeypatch.setattr(terminal, "sha256_file", lambda path: "c" * 64)
    binding = {"learned": learned_path, "state": pre_path, "data": tmp_path / "before.xlsx"}
    assert terminal._ensure_learned_state(tmp_path, binding) == learned
    assert learned_path.read_bytes() == before


def test_same_profile_but_regressed_learning_counters_fails_closed():
    frozen = _prestate(3070)
    frozen["training_rows"] = 2069
    frozen["bounded_online_learning"] = {
        "expert": {"clipped_update_count": 2598},
        "family": {"clipped_update_count": 437},
    }
    frozen["meta_governor"] = {"selected_cumulative_hits": 1244}
    after = {
        "last_contest": 3070,
        "architecture_profile": frozen["architecture_profile"],
        "online_learning_max_abs_step": frozen["online_learning_max_abs_step"],
        "redundancy_consensus_threshold": frozen["redundancy_consensus_threshold"],
        "calibration_strength": 0.0,
        "training_rows": 2070,
        "bounded_online_learning": {
            "expert": {"max_abs_step": 0.75, "clipped_update_count": 1},
            "family": {"max_abs_step": 0.75, "clipped_update_count": 438},
        },
        "meta_governor": {"selected_cumulative_hits": 1245},
    }
    with pytest.raises(ValueError, match="counter regression"):
        terminal._verify_existing_learned_policy(frozen, after, 3070)
    after["bounded_online_learning"]["expert"]["clipped_update_count"] = 2598
    after["meta_governor"]["selected_cumulative_hits"] = 1286
    with pytest.raises(ValueError, match="governor counter anomaly"):
        terminal._verify_existing_learned_policy(frozen, after, 3070)

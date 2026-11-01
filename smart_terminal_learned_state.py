"""Frozen post-result learning policy checks and idempotent replay.

Only previously authorized frozen target parameters are used to reconstruct
the agent. No pre-result calibration or scientific promotion is performed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


def agent_from_prestate(
    prestate: dict[str, Any], *, target_contest: int,
    agent_factory: Callable,
) -> Any:
    """Rebuild under frozen target policy; no automatic calibration promotion."""
    target = int(target_contest)
    if int(prestate["last_contest"]) + 1 != target:
        raise ValueError("frozen learning policy cutoff mismatch")
    if float(prestate["calibration_strength"]) != 0.0:
        raise ValueError("predictive calibration requires independent promotion authority")
    agent = agent_factory(
        start=int(prestate["start_index"]),
        eta=float(prestate["eta"]),
        redundancy_threshold=float(prestate["redundancy_consensus_threshold"]),
        meta_strength=float(prestate["meta_strength"]),
        calibration_strength=0.0,
    )
    agent._configure_target_profile(target)
    agent._reset_states()  # binds expert and family guards to the target-specific cap
    expected = (str(prestate["architecture_profile"]),
                float(prestate["online_learning_max_abs_step"]),
                float(prestate["redundancy_consensus_threshold"]))
    observed = (agent.architecture_profile, agent.online_max_abs_step, agent.redundancy_threshold)
    if observed != expected:
        raise ValueError("frozen learning policy/profile mismatch; replay rejected")
    return agent


def verify_existing_learned_policy(
    prestate: dict[str, Any], learned: dict[str, Any], target: int, *,
    agent_from_prestate: Callable,
) -> None:
    """Detect incompatible immutable historical snapshots; never silently re-use."""
    agent = agent_from_prestate(prestate, target_contest=target)
    expected = (agent.architecture_profile, agent.online_max_abs_step, agent.redundancy_threshold, 0.0)
    observed = (learned.get("architecture_profile"),
                learned.get("online_learning_max_abs_step"),
                learned.get("redundancy_consensus_threshold"),
                learned.get("calibration_strength"))
    if observed != expected:
        raise ValueError("existing learned state policy differs from frozen target; immutable audit required")
    for family in ("expert", "family"):
        preguard = prestate.get("bounded_online_learning", {}).get(family, {})
        guard = learned.get("bounded_online_learning", {}).get(family, {})
        if guard.get("max_abs_step") != agent.online_max_abs_step:
            raise ValueError("existing learned state policy guard cap mismatch")
        if int(guard.get("clipped_update_count", -1)) < int(preguard.get("clipped_update_count", 0)):
            raise ValueError("existing learned state policy guard counter regression")
    before = int(prestate.get("meta_governor", {}).get("selected_cumulative_hits", -1))
    after = int(learned.get("meta_governor", {}).get("selected_cumulative_hits", -1))
    if before >= 0 and not 0 <= after - before <= 6:
        raise ValueError("existing learned state policy governor counter anomaly")
    if learned.get("training_rows") != int(prestate.get("training_rows", -2)) + 1:
        raise ValueError("existing learned state policy training-row count mismatch")


def ensure_learned_state(
    root: Path, binding: dict[str, Any], *,
    target: int, cutoff: int, result_data: str, sha256_file: Callable,
    read_json: Callable, load_draws: Callable,
    agent_from_prestate: Callable, verify_existing_learned_policy: Callable,
    atomic_write_json: Callable,
) -> dict[str, Any]:
    through = root / result_data
    learned_path = binding["learned"]
    prestate_path = binding["state"]
    pre_result_data = binding["data"]
    data_sha = sha256_file(through)
    if learned_path.exists():
        state = read_json(learned_path)
        if int(state.get("last_contest", -1)) != target or state.get("data_sha256") != data_sha:
            raise ValueError("existing learned state is not bound to official target data")
        prestate = read_json(prestate_path)
        verify_existing_learned_policy(prestate, state, target)
        return state
    prestate = read_json(prestate_path)
    if int(prestate.get("last_contest", -1)) != cutoff:
        raise ValueError("active epoch prestate does not end at cutoff")
    if prestate.get("data_sha256") != sha256_file(pre_result_data):
        raise ValueError("active epoch prestate data hash mismatch")
    draws, contests = load_draws(through)
    if int(contests[-1]) != target:
        raise ValueError("official result data does not end at target")
    agent = agent_from_prestate(prestate, target_contest=target)
    cwd = Path.cwd()
    try:
        os.chdir(root)
        agent.replay_history(draws, contests)
        state = agent.state_document(data_sha256=data_sha)
    finally:
        os.chdir(cwd)
    state.update({
        "sequential_learning_target": target,
        "learning_after_adjudication": True,
        "official_result_learning": True,
        "retroactive_rewrite": False,
        "source_prestate_sha256": sha256_file(prestate_path),
        "source_freeze_sha256": binding["freeze_sha256"],
        "authority_mode": binding["mode"],
    })
    atomic_write_json(learned_path, state)
    return state
"""Hash-bound terminal proof persistence, gated by evaluation eligibility.

This module performs no prediction, learning, calibration or eligibility scoring.
It preserves the original mission authority and rollback on status write failure.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def promote_terminal_mission(
    root: Path, evaluation: dict[str, Any], consensus: dict[str, Any],
    audit: dict[str, Any], sequence: dict[str, Any],
    binding: dict[str, Any] | None = None, *,
    target: int, terminal_proof: str, consensus_file: str,
    independent_audit_file: str, load_mission_status: Callable,
    write_mission_status: Callable, runtime_binding: Callable,
    sha256_file: Callable, mission_sha256_json: Callable,
    atomic_write_json: Callable,
) -> dict[str, Any]:
    if evaluation.get("eligible_for_mission_proven") is not True:
        raise ValueError("terminal mission promotion requires a fully eligible evaluation")
    mission_path = root / "SMART_MISSION_STATUS.json"
    mission = load_mission_status(mission_path, root=root)
    if mission.get("terminal_6of6_proven") is True:
        return mission
    if mission.get("status") != "MISSION_ACTIVE":
        raise ValueError("unexpected mission state before terminal promotion")
    binding = binding or runtime_binding(root)
    proof = {
        "schema": "SMART_TERMINAL_6OF6_PROOF_1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": target,
        "terminal_rule": mission.get("terminal_rule"),
        "evaluation": evaluation,
        "freeze_file": binding["freeze"].resolve().relative_to(root.resolve()).as_posix(),
        "freeze_sha256": binding["freeze_sha256"],
        "signal_ledger_file": binding["ledger"].resolve().relative_to(root.resolve()).as_posix(),
        "signal_ledger_sha256": sha256_file(binding["ledger"]),
        "official_evidence_file": consensus_file,
        "official_evidence_sha256": sha256_file(root / consensus_file),
        "independent_audit_file": independent_audit_file,
        "independent_audit_sha256": sha256_file(root / independent_audit_file),
        "sequence_sha256": sequence.get("sequence_sha256"),
        "all_attempts_counted": evaluation["checks"]["all_attempts_counted"],
        "independent_audit_pass": audit.get("status") == "PASS",
        "source_corroborated": consensus.get("terminal_source_corroboration_authorized") is True,
        "retroactive_selection_prohibited": True,
        "status": "MISSION_PROVEN",
    }
    proof["sha256"] = mission_sha256_json(proof)
    proof_path = root / terminal_proof
    atomic_write_json(proof_path, proof)
    mission = dict(mission)
    mission.update({
        "status": "MISSION_PROVEN",
        "terminal_6of6_proven": True,
        "scientific_predictive_status": "TERMINAL_PROSPECTIVE_6OF6_OBSERVED",
        "proven_target_contest": target,
        "proven_top6": evaluation["frozen_top6"],
        "official_actual_numbers": evaluation["actual_numbers"],
        "terminal_proof_file": terminal_proof,
        "terminal_proof_sha256": sha256_file(proof_path),
        "independent_audit_file": independent_audit_file,
        "official_evidence_file": consensus_file,
        "proven_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    try:
        write_mission_status(mission_path, mission, root=root)
    except Exception:
        # Active-epoch proof is non-authoritative until SMART_MISSION_STATUS binds it.
        # Remove the just-written candidate on ordinary failure; if the process is
        # interrupted before cleanup, epoch-scoped placement keeps top-level
        # terminal claim inventory consistent.
        if proof_path.is_file() and sha256_file(proof_path) == mission.get("terminal_proof_sha256"):
            proof_path.unlink()
        raise
    return mission
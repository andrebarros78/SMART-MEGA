"""Deterministic prepared-epoch artifact layout and active document construction.

Only computes paths and document data. The operator retains certification,
result-availability checks, filesystem writes, lifecycle, and CAS authority.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def epoch_artifact_paths(epoch_dir: Path, target: int) -> dict[str, Path]:
    """Compute names used by the existing operator prepare transaction."""
    return {
        "snapshot": epoch_dir / f"Mega-Sena_cutoff_{int(target)-1}.xlsx",
        "ledger": epoch_dir / "SMART_SIGNAL_LEDGER.json",
        "state": epoch_dir / "SMART_SIGNAL_STATE.json",
        "activation_authority": epoch_dir / "SMART_LEARNING_ACTIVATION_AUTHORITY.json",
        "expansion_registry": epoch_dir / "SMART_SIGNAL_EXPANSION_REGISTRY.json",
        "freeze": epoch_dir / f"SMART_{int(target)}_CHAMPION_CHALLENGER_FREEZE.json",
    }


def build_active_epoch_document(
    *,
    root: Path,
    target: int,
    epoch_id: str,
    created_utc: str,
    schema: str,
    certification_file: Path,
    certification_sha256: str,
    layout: dict[str, Path],
    data_sha256: str,
    canonical_history_sha256: str,
    schedule: dict[str, Any],
    temporal: dict[str, Any],
    previous_sha256: str | None,
    ledger_seed: dict[str, Any],
) -> dict[str, Any]:
    """Build the identical pre-result document without writing or promotion."""
    root = Path(root)
    def rel(path: Path) -> str:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    return {
        "schema": schema,
        "status": "RESET_READY",
        "project": "SMART-MEGA",
        "epoch_id": epoch_id,
        "created_utc": created_utc,
        "product_certification_file": str(certification_file).replace("\\", "/"),
        "product_certification_sha256": certification_sha256,
        "operator_selected_target": True,
        "state_paths": {
            "ledger": rel(layout["ledger"]),
            "state": rel(layout["state"]),
            "activation_authority": rel(layout["activation_authority"]),
            "expansion_registry": rel(layout["expansion_registry"]),
            "freeze": rel(layout["freeze"]),
        },
        "data_file": rel(layout["snapshot"]),
        "data_sha256": data_sha256,
        "canonical_source_file": "Mega-Sena.xlsx",
        "canonical_source_sha256_at_prepare": canonical_history_sha256,
        "immutable_history_snapshot": True,
        "cutoff_contest": int(target) - 1,
        "target_contest": int(target),
        "authority_mode": "OPERATOR_SELECTED_TARGET",
        "current_engineering_role": "PRODUCT_CERTIFIED_OPERATION",
        "first_possible_authoritative_target_for_current_engineering": int(target),
        "target_schedule": schedule,
        "temporal_guard": temporal,
        "result_used": False,
        "freeze_authority": None,
        "learning_state_authority": None,
        "supersedes_active_epoch_sha256": previous_sha256,
        "canonical_ledger_seed_sha256": ledger_seed["sha256"],
        "canonical_ledger_seed_event_count": ledger_seed["event_count"],
    }

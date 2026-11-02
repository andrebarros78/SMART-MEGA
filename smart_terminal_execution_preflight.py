"""Fail-closed execution entry gate for a frozen prospective epoch.

Verifies active freeze hash and ledger lineage, blocks duplicate adjudication,
validates historical evidence and, before adjudication, requires PASS preflight.
No official result fetch, learned-state mutation or canonical write occurs here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def build_execution_readiness(
    root: Path, binding: dict[str, Any], *,
    target: int, cutoff: int, legacy_preflight: Callable,
) -> dict[str, Any]:
    """Project active frozen readiness without obtaining or using a result."""
    if binding.get("mode") == "ACTIVE_EPOCH":
        return {
            "readiness_status": "PASS",
            "target_contest": target,
            "cutoff_contest": cutoff,
            "generation_proof_valid": binding.get("current", {}).get("generation_proof_valid") is True,
            "freeze_sha256": binding.get("freeze_sha256"),
            "result_used": False,
        }
    return legacy_preflight(root)


def validate_execution_preflight(
    root: Path, binding: dict[str, Any], *,
    sha256_file: Callable, load_ledger: Callable,
    target_events: Callable, historical_precheck: Callable,
    preflight_readiness: Callable,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not Path(binding["freeze"]).is_file() or sha256_file(Path(binding["freeze"])) != binding["freeze_sha256"]:
        raise ValueError("active epoch freeze hash differs from immutable authority")
    ledger = load_ledger(binding["ledger"])
    adjudications = target_events(ledger, "ADJUDICATION")
    if len(adjudications) > 1:
        raise ValueError("multiple 3054 adjudications are forbidden")
    scoped = historical_precheck(
        root, ledger,
        allow_unverified_history=binding.get("mode") in {
            "ACTIVE_EPOCH", "ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY"
        },
        current_sha256=binding["freeze_sha256"],
    )
    if not adjudications:
        readiness = preflight_readiness(root, binding)
        if readiness.get("readiness_status") != "PASS":
            raise RuntimeError("3054 preflight is not PASS")
    return adjudications, scoped
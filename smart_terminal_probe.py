"""Read-only official result probe with preserved freeze authority checks.

No canonical writes, evidence upgrades or scientific promotion are performed.
The terminal engine supplies the operator fetcher, frozen authority and validators.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def probe_terminal_result(
    root: str | Path, fetcher: Callable | None = None, *,
    target: int, schema: str, canonical_root: Callable,
    default_operator_fetcher: Callable, runtime_binding: Callable,
    sha256_file: Callable, load_ledger: Callable, target_events: Callable,
    load_existing_official_evidence: Callable, preflight_readiness: Callable,
    normalize_primary: Callable,
) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    if fetcher is None:
        fetcher = default_operator_fetcher(root)
    binding = runtime_binding(root)
    if not Path(binding["freeze"]).is_file() or sha256_file(Path(binding["freeze"])) != binding["freeze_sha256"]:
        raise ValueError("active epoch freeze hash differs from immutable authority")
    ledger = load_ledger(binding["ledger"])
    adjudications = target_events(ledger, "ADJUDICATION")
    existing = load_existing_official_evidence(root)
    if not adjudications:
        readiness = preflight_readiness(root, binding)
        if readiness.get("readiness_status") != "PASS":
            raise RuntimeError("3054 preflight is not PASS")
    else:
        readiness = {"readiness_status": "POST_RESULT_SEQUENCE_IN_PROGRESS_OR_COMPLETE"}
    try:
        payload, consensus = fetcher(target)
    except Exception as exc:
        if existing is None and not adjudications:
            return {
                "schema": schema,
                "target_contest": target,
                "status": "WAITING_OFFICIAL_RESULT",
                "preflight_status": readiness["readiness_status"],
                "official_result_available": False,
                "canonical_writes_performed": False,
                "error_type": type(exc).__name__,
                "terminal_6of6_proven": False,
            }
        if existing is None:
            raise
        payload, consensus = existing
        return {
            "schema": schema,
            "target_contest": target,
            "status": "OFFICIAL_RESULT_ALREADY_CAPTURED_REFRESH_UNAVAILABLE",
            "preflight_status": readiness["readiness_status"],
            "official_result_available": True,
            "canonical_writes_performed": False,
            "error_type": type(exc).__name__,
            "terminal_source_corroboration_authorized": consensus.get("terminal_source_corroboration_authorized") is True,
            "terminal_6of6_proven": False,
        }
    normalized = normalize_primary(payload)
    return {
        "schema": schema,
        "target_contest": target,
        "status": "OFFICIAL_RESULT_AVAILABLE",
        "preflight_status": readiness["readiness_status"],
        "official_result_available": True,
        "actual_numbers": normalized["numbers"],
        "draw_date": normalized["draw_date"],
        "terminal_source_corroboration_authorized": consensus.get("terminal_source_corroboration_authorized") is True,
        "result_input_authority": consensus.get("primary", {}).get("channel"),
        "canonical_writes_performed": False,
        "terminal_6of6_proven": False,
    }
"""Pure terminal post-result status projection.

The caller performs all authority checks, evidence writes, evaluation, and
mission promotion. This module only reports the observed outcome and never
creates scientific proof or upgrades status on its own.
"""
from __future__ import annotations

from typing import Any


def build_terminal_execution_status(
    *, schema: str, target: int, created_at_utc: str,
    normalized: dict[str, Any], consensus: dict[str, Any],
    ingest: dict[str, Any], adjudication: dict[str, Any],
    learned: dict[str, Any], sequence_validation: dict[str, Any],
    audit: dict[str, Any], result_store: dict[str, Any],
    evaluation: dict[str, Any], mission: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": schema,
        "created_at_utc": created_at_utc,
        "target_contest": target,
        "status": evaluation["status"] if mission.get("terminal_6of6_proven") is not True else "MISSION_PROVEN",
        "official_result_available": True,
        "actual_numbers": normalized["numbers"],
        "official_evidence_status": consensus.get("status"),
        "terminal_source_corroboration_authorized": consensus.get("terminal_source_corroboration_authorized") is True,
        "ingest_status": ingest.get("schema"),
        "adjudication_status": adjudication.get("status", "ADJUDICATED"),
        "champion_hits": int(adjudication["champion_hits"]),
        "challenger_hits": int(adjudication["challenger_hits"]),
        "learned_state_last_contest": int(learned["last_contest"]),
        "sequence_valid": sequence_validation.get("valid") is True,
        "independent_audit_status": audit.get("status"),
        "audited_pair_count": audit.get("prospective_ledger", {}).get("pair_count"),
        "canonical_result_store_status": result_store.get("status"),
        "terminal_evaluation": evaluation,
        "mission_state": mission.get("status"),
        "terminal_6of6_proven": mission.get("terminal_6of6_proven") is True,
    }
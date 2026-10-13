"""Prospective triple-card preregistration gate, using the canonical signal ledger.

The gate is read-only. A pre-result CANDIDATE is NOT a registered experiment:
independent immutable Git publication prior to the draw is still required.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path


SCHEMA = "SMART_PROSPECTIVE_TRIPLE_CARD_PRECOMMIT_1"


def _sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _six(values, label):
    if (not isinstance(values, list) or len(values) != 6
            or any(type(n) is not int or not 1 <= n <= 60 for n in values)
            or len(set(values)) != 6):
        raise ValueError(f"{label}: requires six unique integers 1..60")
    return values


def _hash64(value, label):
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label}: SHA-256 missing")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label}: SHA-256 malformed") from exc
    return value.lower()


def _timestamp(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label}: timezone-aware timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label}: invalid timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{label}: timezone required")
    return parsed


def protocol():
    """Ex-ante rules; changing them requires a new version and new Git commit."""
    p = {
        "schema": SCHEMA,
        "comparison_units": ["champion_top6", "challenger_top6", "primary_card"],
        "evaluation_metric": "exact_intersection_hit_count_each_six_number_card",
        "reference": {
            "distribution": "uniform_six_without_replacement",
            "expected_hits_per_card": 0.6,
            "six_hit_guarantee": False,
        },
        "paired_comparisons": [
            "challenger_minus_champion_hits",
            "primary_minus_champion_hits",
        ],
        "prospective_inclusion": "only frozen target cards independently published on Git before draw and adjudicated after",
        "registration_source": "SMART_SIGNAL_LEDGER.json FREEZE event (active target only)",
        "registration_before_draw_required": True,
        "registration_independent_git_publication_required": True,
        "minimum_prospective_contests_for_p13_gate": 20,
        "sequential_e_value_threshold_for_p13_gate": 10.0,
        "statistical_gate_authority": "existing smart_promotion_gate and independent P14/P15 checks",
        "post_result_reweighting_of_same_target_forbidden": True,
        "historical_backfill_forbidden": True,
        "missing_frozen_artifact_policy": "exclude_and_report_never_reconstruct",
        "missing_card_policy": "ineligible_never_infer",
        "reporting": "report all attempts and exclusions; no cherry-picking",
        "production_switch_authorized": False,
        "predictive_superiority_proven": False,
    }
    p["protocol_sha256"] = _sha(p)
    return p


def preflight(root):
    """Observe live authorities without changing lifecycle, freezes or ledger."""
    root = Path(root)
    lifecycle = json.loads((root / "SMART_OPERATIONAL_LIFECYCLE.json").read_text(encoding="utf-8-sig"))
    hold = json.loads((root / "SMART_NEXT_CYCLE_HOLD.json").read_text(encoding="utf-8-sig"))
    ledger = json.loads((root / "SMART_SIGNAL_LEDGER.json").read_text(encoding="utf-8-sig"))
    if ledger.get("schema") != "SMART_SIGNAL_LEDGER_1" or not isinstance(ledger.get("events"), list):
        raise ValueError("canonical signal ledger missing or malformed")
    target = lifecycle.get("target_contest")
    completed = lifecycle.get("completed_contest")
    if (type(target) is not int or type(completed) is not int
            or target != completed + 1 or hold.get("next_target") != target
            or hold.get("completed_contest") != completed):
        raise ValueError("live target/cutoff/HOLD authorities inconsistent")
    frozen = [ev for ev in ledger["events"] if ev.get("target_contest") == target and ev.get("event_type") == "FREEZE"]
    adjudicated = [ev for ev in ledger["events"] if ev.get("target_contest") == target and ev.get("event_type") == "ADJUDICATION"]
    if adjudicated:
        raise ValueError("prospective registration after result forbidden")
    blocked = (lifecycle.get("state") == "HOLD" or hold.get("generation_allowed") is False)
    return {
        "schema": SCHEMA,
        "target_contest": target,
        "completed_contest": completed,
        "lifecycle_state": lifecycle.get("state"),
        "active_target_freeze_events": len(frozen),
        "status": "BLOCKED_BY_OPERATOR_HOLD" if blocked else "REQUIRES_AUTHENTIC_FROZEN_CARD",
        "generation_authorized": False,
        "retrospective_registration_authorized": False,
        "pre_result_git_registration_exists": False,
        "production_promotion_authorized": False,
        "protocol_sha256": protocol()["protocol_sha256"],
    }


def candidate_from_frozen_event(event, ledger, *, completed_contest):
    """Build non-authoritative candidate from one FREEZE, never a backfill.

    Hashes here bind contents declared in the canonical event. The returned
    candidate must separately be published AND independently dated before
    the target draw; this function does not attest either property.
    """
    if not isinstance(event, dict) or not isinstance(ledger, dict):
        raise ValueError("canonical freeze event and ledger required")
    target, cutoff = event.get("target_contest"), event.get("cutoff_contest")
    if (type(target) is not int or type(cutoff) is not int
            or type(completed_contest) is not int
            or target != cutoff + 1 or target <= completed_contest):
        raise ValueError("prospective target must follow historical cutoff")
    if (event.get("event_type") != "FREEZE"
            or event.get("frozen_before_result") is not True
            or event.get("causal_cutoff") is not True):
        raise ValueError("pre-result frozen event required")
    freeze_time = _timestamp(event.get("created_utc"), "freeze event")
    freeze_hash = _hash64(event.get("freeze_sha256"), "frozen model")
    portfolio_hash = _hash64(event.get("portfolio_sha256"), "frozen portfolio")
    champion = _six(event.get("champion_top6"), "champion")
    challenger = _six(event.get("challenger_top6"), "challenger")
    card = event.get("primary_card")
    if not isinstance(card, dict):
        raise ValueError("frozen primary card absent")
    final = _six(card.get("numbers"), "primary card")
    if (card.get("product_role") != "FINAL_SINGLE_CARD_PRODUCT"
            or card.get("freeze_sha256") != freeze_hash
            or card.get("target_contest") != target
            or card.get("cutoff_contest") != cutoff
            or card.get("selector", {}).get("result_used") is not False
            or card.get("false_negative_rescue", {}).get("result_used") is not False):
        raise ValueError("primary card lacks causal freeze/selector linkage")
    events = ledger.get("events")
    if not isinstance(events, list):
        raise ValueError("canonical ledger missing events")
    associated = [x for x in events if x.get("target_contest") == target]
    if (len([x for x in associated if x.get("event_type") == "FREEZE"]) != 1
            or any(x.get("event_type") in ("ADJUDICATION", "LEARNING_UPDATE", "SEQUENTIAL_PROOF")
                   for x in associated)):
        raise ValueError("ambiguous freeze or result already observed")
    if associated[0] is not event and event not in associated:
        raise ValueError("candidate freeze not contained in canonical ledger")
    commitment = {
        "schema": SCHEMA,
        "protocol_sha256": protocol()["protocol_sha256"],
        "target_contest": target,
        "cutoff_contest": cutoff,
        "freeze_created_utc": freeze_time.isoformat(),
        "freeze_sha256": freeze_hash,
        "portfolio_sha256": portfolio_hash,
        "champion_top6": list(champion),
        "challenger_top6": list(challenger),
        "primary_card": list(final),
        "result_used": False,
        "historical_backfill": False,
        "status": "UNPUBLISHED_CANDIDATE_NOT_PROSPECTIVE_EVIDENCE",
        "independent_git_registration_required": True,
        "promotion_authorized": False,
    }
    commitment["candidate_sha256"] = _sha(commitment)
    return commitment

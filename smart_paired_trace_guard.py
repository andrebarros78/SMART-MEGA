"""Fail-closed per-contest holdout pairing with point-in-time and outcome checks.

This module proves *consistency* of a trace with independently supplied
replayed predictions and archived outcomes. It never certifies future skill,
authenticates a purported source without checking its external hash, or
authorizes model promotion.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

SCHEMA = "SMART_PAIRED_HOLDOUT_TRACE_1"


def paired_sign_test(wins: int, losses: int) -> float:
    """Exact one-sided paired sign tail under symmetric exchangeability."""
    if type(wins) is not int or type(losses) is not int or wins < 0 or losses < 0:
        raise ValueError("paired wins/losses must be nonnegative integers")
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / (2**n)


def _valid_numbers(values: Any) -> bool:
    return (
        isinstance(values, list)
        and len(values) == 6
        and all(type(x) is int and 1 <= x <= 60 for x in values)
        and len(set(values)) == 6
    )


def _valid_sha(value: Any, length: int) -> bool:
    return isinstance(value, str) and bool(re.fullmatch("[0-9a-f]{" + str(length) + "}", value))


def validate_trace(
    doc: Mapping[str, Any],
    official_results: Mapping[int, Sequence[int]],
    *,
    replay_predictions: Sequence[tuple[Sequence[int], Sequence[int]]] | None = None,
) -> dict[str, Any]:
    """Verify a trace against independent chronological results and model replay.

    One row is required for every contest of the specified uninterrupted
    holdout. Every row's prediction_cutoff must be exactly contest-1, not merely
    below the 3075 target, preventing late 'predictions'. Running a holdout on
    already known results is retrospective and not a prospective skill proof.
    """
    errors: set[str] = set()
    rows = doc.get("rows")
    start = doc.get("holdout_start")
    end = doc.get("holdout_end")
    target = doc.get("target_contest")
    cutoff = doc.get("cutoff_contest")

    if (doc.get("schema") != SCHEMA
        or doc.get("future_result_used") is not False
        or doc.get("promotion_authorized") is not False
        or type(target) is not int or type(cutoff) is not int or cutoff != target - 1
        or type(start) is not int or type(end) is not int or start > end or end > cutoff
        or not _valid_sha(doc.get("snapshot_sha256"), 64)
        or not _valid_sha(doc.get("baseline_engine_git_blob"), 40)
        or not _valid_sha(doc.get("candidate_engine_git_blob"), 40)):
        errors.add("MANIFEST_OR_TEMPORAL_SOURCE_INVALID")

    if not isinstance(rows, list) or type(start) is not int or type(end) is not int:
        rows = []
        errors.add("HOLDOUT_SEQUENCE_INVALID")
    elif len(rows) != end - start + 1:
        errors.add("HOLDOUT_SEQUENCE_INVALID")

    if replay_predictions is not None and len(replay_predictions) != len(rows):
        errors.add("PREDICTION_REPLAY_MISMATCH")

    wins = losses = ties = b_hits = c_hits = 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.add("HOLDOUT_SEQUENCE_INVALID")
            continue
        contest = row.get("contest")
        if type(contest) is not int or start is None or contest != start + i:
            errors.add("HOLDOUT_SEQUENCE_INVALID")
        if type(contest) is not int or row.get("prediction_cutoff") != contest - 1:
            errors.add("PIT_CUTOFF_INVALID")
        b = row.get("baseline_top6")
        c = row.get("candidate_top6")
        if not _valid_numbers(b) or not _valid_numbers(c):
            errors.add("INVALID_CARD")
            continue
        outcome = official_results.get(contest)
        if (not isinstance(outcome, (list, tuple))
            or len(outcome) != 6 or set(outcome) != set(int(n) for n in outcome)
            or any(type(n) is not int or not 1 <= n <= 60 for n in outcome)
            or len(set(outcome)) != 6):
            errors.add("OFFICIAL_RESULT_MISSING_OR_INVALID")
            continue
        known = set(outcome)
        bh = len(set(b) & known)
        ch = len(set(c) & known)
        if row.get("baseline_hits") != bh or row.get("candidate_hits") != ch:
            errors.add("HITS_MISMATCH")
        b_hits += bh
        c_hits += ch
        if ch > bh:
            wins += 1
        elif ch < bh:
            losses += 1
        else:
            ties += 1
        if replay_predictions is not None and i < len(replay_predictions):
            predicted = replay_predictions[i]
            try:
                if sorted(predicted[0]) != sorted(b) or sorted(predicted[1]) != sorted(c):
                    errors.add("PREDICTION_REPLAY_MISMATCH")
            except (TypeError, IndexError, ValueError):
                errors.add("PREDICTION_REPLAY_MISMATCH")

    paired_p = paired_sign_test(wins, losses)
    s = doc.get("summary")
    if not isinstance(s, dict):
        errors.add("PAIRED_COUNTS_MISMATCH")
    else:
        expected = dict(baseline_hits=b_hits, candidate_hits=c_hits,
                        candidate_wins=wins, baseline_wins=losses, ties=ties)
        if any(type(s.get(k)) is not int or s[k] != v for k, v in expected.items()):
            errors.add("PAIRED_COUNTS_MISMATCH")
        value = s.get("one_sided_p")
        if (type(value) not in (int, float)
            or not math.isfinite(value)
            or not math.isclose(float(value), paired_p, abs_tol=1e-12, rel_tol=0.0)):
            errors.add("PAIRED_COUNTS_MISMATCH")

    replayed = replay_predictions is not None and "PREDICTION_REPLAY_MISMATCH" not in errors
    status = "FAIL" if errors else ("PASS" if replayed else "INCOMPLETE_REPLAY")
    return {
        "schema": "SMART_PAIRED_HOLDOUT_TRACE_AUDIT_1",
        "status": status,
        "errors": sorted(errors),
        "holdout": dict(start=start, end=end, n=len(rows)),
        "paired": dict(baseline_hits=b_hits, candidate_hits=c_hits,
                       baseline_wins=losses, candidate_wins=wins, ties=ties,
                       one_sided_p=paired_p),
        "per_draw_prediction_replayed": replayed,
        "prospective_advantage_proven": False,
        "promotion_authorized": False,
    }

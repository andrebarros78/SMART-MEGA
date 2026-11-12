"""Champion vs native research Challenger — causal paired replay, no promotion.

Brier here measures a hard binary Top-6 selection, not a calibrated
per-number probability. No result is accepted by the pre-result phase.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from smart_frontier_signal_lab import sha256_file
from smart_native_signal_research import (
    _approved_local, build_research_challenger, canonical_hash,
    hash_document, validate_contribution,
)
from smart_rank_score_calibration import brier_score


SCHEMA_PRE = "SMART_NATIVE_PAIRED_PRE_RESULT_V1"
SCHEMA_POST = "SMART_NATIVE_PAIRED_POST_RESULT_V1"
BRIER_KIND = "HARD_TOP6_BINARY_SELECTION_NOT_CALIBRATED_PROBABILITY"
NUMBERS = set(range(1, 61))


def _ranking(value: Any) -> list[int]:
    if (not isinstance(value, list) or len(value) != 60
            or any(type(n) is not int for n in value)
            or set(value) != NUMBERS):
        raise ValueError("ranking60 must be a strict permutation of 1..60")
    return list(value)


def _top6(value: Any) -> list[int]:
    if (not isinstance(value, list) or len(value) != 6
            or any(type(n) is not int or n not in NUMBERS for n in value)
            or len(set(value)) != 6):
        raise ValueError("top6 must be six unique integers in 1..60")
    return list(value)


def _validate_scores(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != {str(n) for n in NUMBERS}:
        raise ValueError("scores require exactly sixty string-number keys")
    out = {}
    for n in range(1, 61):
        v = value[str(n)]
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError("scores must be finite real numbers")
        out[str(n)] = float(v)
    return out


def rank_comparison(left: list[int], right: list[int]) -> dict[str, Any]:
    a = _ranking(left)
    b = _ranking(right)
    pos_a = {n: index + 1 for index, n in enumerate(a)}
    pos_b = {n: index + 1 for index, n in enumerate(b)}
    differences = [pos_a[n] - pos_b[n] for n in range(1, 61)]
    rho = 1.0 - 6.0 * sum(d * d for d in differences) / (60 * (60**2 - 1))
    return {
        "spearman_rho": float(rho),
        "mean_absolute_rank_shift": float(sum(abs(d) for d in differences) / 60),
        "max_absolute_rank_shift": max(abs(d) for d in differences),
        "top6_overlap": len(set(a[:6]) & set(b[:6])),
        "top6_changed": set(a[:6]) != set(b[:6]),
    }


def hard_selection_brier(top6: list[int], actual: list[int]) -> float:
    selection = set(_top6(top6))
    _top6(actual)
    # Reuse canonical Brier implementation. 0/1 are *decisions*, not
    # estimated probabilities; the distinction remains in the output schema.
    binary = {n: float(n in selection) for n in range(1, 61)}
    return brier_score(binary, actual)


def _arm(candidate: dict[str, Any]) -> dict[str, Any]:
    ranked = _ranking(candidate["ranking60"])
    selected = _top6(candidate["top6"])
    if set(ranked[:6]) != set(selected):
        raise ValueError("candidate top6 not aligned with ranking60")
    return {
        "sha256": candidate["sha256"],
        "ranking60": ranked,
        "top6": selected,
        "scores_by_number": _validate_scores(candidate["scores_by_number"]),
    }


def _champion(source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("champion policy must be an object")
    ranked = _ranking(source.get("ranking60"))
    selected = _top6(source.get("top6"))
    if set(ranked[:6]) != set(selected):
        raise ValueError("champion top6/ranking misaligned")
    scores = _validate_scores(source.get("aggregate_scores"))
    return {
        "ranking60": ranked,
        "top6": selected,
        "scores_by_number": scores,
        "policy_kind": "EXISTING_CHAMPION_CURRENT_POLICY",
    }


def _comp(full: dict, arm: dict) -> dict:
    ranks = rank_comparison(full["ranking60"], arm["ranking60"])
    scores_a, scores_b = full["scores_by_number"], arm["scores_by_number"]
    difference = {str(n): float(scores_a[str(n)] - scores_b[str(n)])
                  for n in range(1, 61)}
    return {
        **ranks,
        "score_semantics": "RESEARCH_UNCALIBRATED_RELATIVE_SCORES",
        "score_delta_by_number": difference,
        "max_abs_score_delta": max(abs(x) for x in difference.values()),
        "mean_abs_score_delta": sum(abs(x) for x in difference.values()) / 60,
    }


def build_pre_result_paired_comparison(
    contributions: Iterable[dict[str, Any]],
    weights: dict[str, float],
    champion_policy: dict[str, Any],
    *,
    data_path: Path, epoch_id: str,
    target_contest: int, champion_engine_sha256: str,
) -> dict[str, Any]:
    """All inputs cut at N-1. No post-result argument exists."""
    if (type(target_contest) is not int or target_contest < 2
            or not isinstance(epoch_id, str) or not epoch_id):
        raise ValueError("invalid target contest or epoch")
    if (not isinstance(champion_engine_sha256, str)
            or len(champion_engine_sha256) != 64
            or any(x not in "0123456789abcdef" for x in champion_engine_sha256)):
        raise ValueError("champion engine SHA malformed")
    path = _approved_local(Path(data_path))
    if not path.is_file():
        raise ValueError("missing N-1 historical snapshot")
    rows = list(contributions)
    if not rows:
        raise ValueError("missing contributions")
    for row in rows:
        validate_contribution(row, path)
        if (row["target_contest"] != target_contest
                or row["cutoff_contest"] != target_contest - 1
                or row["epoch_id"] != epoch_id):
            raise ValueError("producer target/cutoff/epoch mismatch")
    full_model = build_research_challenger(rows, weights)
    full = _arm(full_model)
    champion = _champion(champion_policy)
    neutral = _arm(build_research_challenger(rows, {n: 0.0 for n in weights}))
    minus_producer = {
        n: _arm(build_research_challenger(rows, {
            k: (0.0 if k == n else v) for k, v in weights.items()
        }))
        for n in sorted(weights)
    }
    families = {r["feature_family"] for r in rows}
    minus_family = {
        family: _arm(build_research_challenger(rows, {
            k: (0.0 if any(
                x["producer_id"] == k and x["feature_family"] == family for x in rows
            ) else v) for k, v in weights.items()
        }))
        for family in sorted(families)
    }
    comparisons = {
        "champion": rank_comparison(full["ranking60"], champion["ranking60"]),
        "uniform": _comp(full, neutral),
        "by_producer": {n: _comp(full, arm) for n, arm in minus_producer.items()},
        "by_family": {f: _comp(full, arm) for f, arm in minus_family.items()},
    }
    return hash_document({
        "schema": SCHEMA_PRE,
        "epoch_id": epoch_id,
        "target_contest": target_contest,
        "cutoff_contest": target_contest - 1,
        "snapshot_sha256": sha256_file(path),
        "champion_engine_sha256": champion_engine_sha256,
        "producer_signal_sha256s": {r["producer_id"]: r["sha256"] for r in rows},
        "weights": {n: float(weights[n]) for n in sorted(weights)},
        "champion": champion,
        "arms": {
            "full": full,
            "uniform": neutral,
            "without_each_producer": minus_producer,
            "without_each_family": minus_family,
        },
        "comparisons_vs_full": comparisons,
        "arms_frozen_before_result": True,
        "target_result_used": False,
        "research_only": True,
        "production_authority": False,
        "predictive_gain_proven": False,
        "calibrated_probabilities_claimed": False,
    })


def adjudicate_paired_comparison(
    frozen: dict[str, Any], result: dict[str, Any], *,
    source_verified: bool,
) -> dict[str, Any]:
    """Only the post-result side may receive an authenticated historical draw."""
    if source_verified is not True:
        raise ValueError("verified historical result source required")
    if (not isinstance(frozen, dict)
            or frozen.get("sha256") != canonical_hash({
                k: v for k, v in frozen.items() if k != "sha256"
            })
            or frozen.get("schema") != SCHEMA_PRE
            or frozen.get("target_result_used") is not False
            or frozen.get("production_authority") is not False
            or frozen.get("research_only") is not True):
        raise ValueError("pre-result comparison freeze invalid")
    if not isinstance(result, dict) or set(result) != {
        "contest", "numbers", "source_sha256", "source_kind"
    }:
        raise ValueError("historical result contract invalid")
    if (type(result["contest"]) is not int
            or result["contest"] != frozen["target_contest"]):
        raise ValueError("historical result target mismatch")
    numbers = _top6(result["numbers"])
    source_sha = result["source_sha256"]
    if (not isinstance(source_sha, str) or len(source_sha) != 64
            or any(x not in "0123456789abcdef" for x in source_sha)
            or result["source_kind"] != "HISTORICAL_REPLAY"):
        raise ValueError("historical result provenance invalid")
    won = set(numbers)

    def metric(arm: dict[str, Any]) -> dict[str, Any]:
        selected = _top6(arm["top6"])
        return {
            "top6": selected,
            "hits": len(set(selected) & won),
            "selection_brier": hard_selection_brier(selected, numbers),
        }
    champion = metric(frozen["champion"])
    full = metric(frozen["arms"]["full"])
    uniform = metric(frozen["arms"]["uniform"])
    per_producer = {name: metric(arm) for name, arm in
                    frozen["arms"]["without_each_producer"].items()}
    per_family = {family: metric(arm) for family, arm in
                  frozen["arms"]["without_each_family"].items()}
    contribution = {
        name: {
            "delta_hits_full_minus_ablated": full["hits"] - arm["hits"],
            "delta_brier_full_minus_ablated": (
                full["selection_brier"] - arm["selection_brier"]
            ),
        }
        for name, arm in per_producer.items()
    }
    return hash_document({
        "schema": SCHEMA_POST,
        "target_contest": frozen["target_contest"],
        "cutoff_contest": frozen["cutoff_contest"],
        "pre_result_freeze_sha256": frozen["sha256"],
        "historical_result_sha256": canonical_hash(result),
        "historical_source_sha256": source_sha,
        "historical_source_verified": True,
        "numbers_result": sorted(numbers),
        "champion": champion,
        "full": full,
        "uniform": uniform,
        "without_each_producer": per_producer,
        "without_each_family": per_family,
        "by_producer_contribution": contribution,
        "challenger_minus_champion_hits": full["hits"] - champion["hits"],
        "challenger_minus_champion_brier": (
            full["selection_brier"] - champion["selection_brier"]
        ),
        "brier_semantics": BRIER_KIND,
        "calibrated_probability_brier": "NOT_MEASURED_NEUTRALIZED",
        "research_only": True,
        "production_authority": False,
        "predictive_gain_proven": False,
    })

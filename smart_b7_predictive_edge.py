from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "SMART_B7_PREDICTIVE_EDGE_V1"
N_NUMBERS = 60
DRAW_SIZE = 6
UNIFORM_PROBABILITY = DRAW_SIZE / N_NUMBERS
UNIFORM_BRIER = UNIFORM_PROBABILITY * (1.0 - UNIFORM_PROBABILITY)
EPS = 1e-15


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_embedded_hash(document: dict[str, Any]) -> None:
    observed = document.get("sha256")
    canonical = dict(document)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError("source embedded hash mismatch")


def _actual_vector(actual_numbers: list[int] | tuple[int, ...]) -> np.ndarray:
    actual = [int(x) for x in actual_numbers]
    if len(actual) != DRAW_SIZE or len(set(actual)) != DRAW_SIZE or min(actual) < 1 or max(actual) > N_NUMBERS:
        raise ValueError("actual_numbers must contain six unique numbers in [1,60]")
    out = np.zeros(N_NUMBERS, dtype=float)
    out[np.asarray(actual, dtype=int) - 1] = 1.0
    return out


def probability_vector(values: Any) -> np.ndarray:
    if not isinstance(values, dict) or set(values) != {str(i) for i in range(1, N_NUMBERS + 1)}:
        raise ValueError("probabilities must contain keys 1..60")
    arr = np.asarray([float(values[str(i)]) for i in range(1, N_NUMBERS + 1)], dtype=float)
    if np.any(~np.isfinite(arr)) or np.any((arr < 0.0) | (arr > 1.0)):
        raise ValueError("probabilities must be finite in [0,1]")
    if not math.isclose(float(arr.sum()), float(DRAW_SIZE), rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("probabilities must sum to six")
    return arr


def binary_log_loss(probabilities: np.ndarray, actual: np.ndarray) -> float:
    p = np.clip(np.asarray(probabilities, dtype=float), EPS, 1.0 - EPS)
    y = np.asarray(actual, dtype=float)
    if p.shape != (N_NUMBERS,) or y.shape != (N_NUMBERS,):
        raise ValueError("log loss expects 60 probabilities and outcomes")
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def brier_score(probabilities: np.ndarray, actual: np.ndarray) -> float:
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(actual, dtype=float)
    if p.shape != (N_NUMBERS,) or y.shape != (N_NUMBERS,):
        raise ValueError("Brier score expects 60 probabilities and outcomes")
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(probabilities: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> float:
    p = np.asarray(probabilities, dtype=float).ravel()
    y = np.asarray(outcomes, dtype=float).ravel()
    if p.shape != y.shape or p.size == 0 or bins < 2:
        raise ValueError("invalid calibration arrays")
    edges = np.linspace(0.0, 1.0, int(bins) + 1)
    total = float(p.size)
    ece = 0.0
    for i in range(int(bins)):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        if not np.any(mask):
            continue
        ece += float(np.sum(mask)) / total * abs(float(np.mean(p[mask])) - float(np.mean(y[mask])))
    return float(ece)


def _row_metrics(row: dict[str, Any], actual_numbers: list[int]) -> dict[str, float]:
    p = probability_vector(row.get("probabilities"))
    y = _actual_vector(actual_numbers)
    score = brier_score(p, y)
    declared = float(row.get("brier", score))
    if not math.isclose(score, declared, rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError("retained probabilities do not reproduce declared Brier score")
    return {"brier": score, "log_loss": binary_log_loss(p, y), "hits": float(row.get("hits", 0)), "p": p, "y": y}


def audit_candidate(rows: list[dict[str, Any]], outcomes_by_contest: dict[int, list[int]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("candidate rows are empty")
    metrics = []
    for row in rows:
        contest = int(row["contest"])
        if int(row.get("cutoff_contest", -1)) != contest - 1:
            raise ValueError("causal cutoff violation")
        if contest not in outcomes_by_contest:
            raise ValueError(f"missing outcome for contest {contest}")
        metrics.append(_row_metrics(row, outcomes_by_contest[contest]))
    brier = np.asarray([m["brier"] for m in metrics], dtype=float)
    logloss = np.asarray([m["log_loss"] for m in metrics], dtype=float)
    hits = np.asarray([m["hits"] for m in metrics], dtype=float)
    all_p = np.vstack([m["p"] for m in metrics])
    all_y = np.vstack([m["y"] for m in metrics])
    uniform_p = np.full(N_NUMBERS, UNIFORM_PROBABILITY, dtype=float)
    uniform_y = _actual_vector([1, 2, 3, 4, 5, 6])
    uniform_logloss = binary_log_loss(uniform_p, uniform_y)
    mean_brier = float(brier.mean())
    mean_logloss = float(logloss.mean())
    mean_hits = float(hits.mean())
    brier_edge = (UNIFORM_BRIER - mean_brier) / UNIFORM_BRIER
    logloss_edge = (uniform_logloss - mean_logloss) / uniform_logloss
    hit_edge = (mean_hits - 0.6) / 0.6
    conservative_edge = min(brier_edge, logloss_edge)
    return {
        "n": int(len(metrics)),
        "mean_brier": mean_brier,
        "uniform_brier": float(UNIFORM_BRIER),
        "brier_edge_fraction": float(brier_edge),
        "brier_edge_pct": float(100.0 * brier_edge),
        "mean_log_loss": mean_logloss,
        "uniform_log_loss": float(uniform_logloss),
        "log_loss_edge_fraction": float(logloss_edge),
        "log_loss_edge_pct": float(100.0 * logloss_edge),
        "mean_hits": mean_hits,
        "uniform_mean_hits": 0.6,
        "hit_edge_fraction": float(hit_edge),
        "hit_edge_pct": float(100.0 * hit_edge),
        "ece_10": expected_calibration_error(all_p, all_y, bins=10),
        "prospective_edge_fraction": float(conservative_edge),
        "prospective_edge_pct": float(100.0 * conservative_edge),
        "proper_scores_both_better_than_uniform": bool(brier_edge > 0.0 and logloss_edge > 0.0),
        "interpretation": "relative proper-score improvement; not a percent increase in jackpot probability",
    }


def build_historical_diagnostic(source: dict[str, Any], outcomes_by_contest: dict[int, list[int]], partition: str = "holdout") -> dict[str, Any]:
    verify_embedded_hash(source)
    if source.get("future_leakage") is not False:
        raise ValueError("source must declare future_leakage=false")
    rows_by_candidate = source.get("rows")
    if not isinstance(rows_by_candidate, dict) or not rows_by_candidate:
        raise ValueError("source candidate rows missing")
    candidates: dict[str, Any] = {}
    for name in sorted(rows_by_candidate):
        rows = [row for row in rows_by_candidate[name] if row.get("split") == partition]
        candidates[name] = audit_candidate(rows, outcomes_by_contest)
    ranked = sorted(candidates, key=lambda name: (candidates[name]["prospective_edge_fraction"], candidates[name]["brier_edge_fraction"]), reverse=True)
    best = ranked[0]
    result = {
        "schema": SCHEMA,
        "mode": "HISTORICAL_DIAGNOSTIC_ONLY",
        "source_schema": source.get("schema"),
        "source_sha256": source.get("sha256"),
        "partition": partition,
        "candidate_count": len(candidates),
        "candidate_names": sorted(candidates),
        "candidates": candidates,
        "ranking_by_conservative_proper_score_edge": ranked,
        "best_candidate": best,
        "best_prospective_edge_pct": float(candidates[best]["prospective_edge_pct"]),
        "production_authority": False,
        "predictive_claim": False,
        "prospective_proof": False,
        "guardrail": "historical edge is diagnostic only; future frozen contests are required for predictive proof",
    }
    result["sha256"] = sha256_json(result)
    return result


def write_historical_diagnostic(source_path: str | Path, data_path: str | Path, out_path: str | Path, partition: str = "holdout") -> dict[str, Any]:
    import pandas as pd
    source = json.loads(Path(source_path).read_text(encoding="utf-8-sig"))
    frame = pd.read_excel(data_path)
    outcomes = {
        int(row["Concurso"]): [int(row[f"Bola{i}"]) for i in range(1, 7)]
        for _, row in frame.iterrows()
    }
    result = build_historical_diagnostic(source, outcomes, partition=partition)
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

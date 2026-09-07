from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import smart_v2_engine as e
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import load_registry, write_registry

SCHEMA = "SMART_FRONTIER_SIGNAL_LAB_1"
FREEZE_SCHEMA = "SMART_FRONTIER_SHADOW_FREEZE_1"
CANDIDATES = {
    "frontier_gap_hazard": "recurrence_hazard",
    "frontier_transition_markov": "conditional_transition",
    "frontier_cooccurrence_graph": "hypergraph_link",
    "frontier_weekday_bayes": "procedural_calendar",
    "frontier_recent_lift": "bayesian_change",
}
GAP_BOUNDS = (1, 2, 4, 8, 16)
UNIFORM_PROBABILITY = 0.1
UNIFORM_BRIER = 0.09


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _minmax(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if not np.all(np.isfinite(arr)):
        raise ValueError("candidate produced a non-finite score")
    if hi - lo <= 1e-15:
        return np.zeros(60, dtype=float)
    return (arr - lo) / (hi - lo)


def scores_to_probabilities(values: np.ndarray) -> np.ndarray:
    score = _minmax(values) + 1e-9
    probabilities = 6.0 * score / float(score.sum())
    for _ in range(60):
        over = probabilities > 1.0
        if not np.any(over):
            break
        excess = float(np.sum(probabilities[over] - 1.0))
        probabilities[over] = 1.0
        under = ~over
        if not np.any(under) or excess <= 1e-15:
            break
        base = score[under]
        probabilities[under] += excess * base / float(base.sum())
    if abs(float(probabilities.sum()) - 6.0) > 1e-8:
        raise RuntimeError("candidate probabilities must sum to six")
    return probabilities


def brier(probabilities: np.ndarray, actual: np.ndarray) -> float:
    outcome = np.zeros(60, dtype=float)
    outcome[np.asarray(actual, dtype=int) - 1] = 1.0
    return float(np.mean((np.asarray(probabilities, dtype=float) - outcome) ** 2))


def _gap_bucket(gap: int) -> int:
    for index, bound in enumerate(GAP_BOUNDS):
        if int(gap) <= bound:
            return index
    return len(GAP_BOUNDS)


@dataclass
class FrontierPrediction:
    scores: dict[str, np.ndarray]

    def document(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, raw in self.scores.items():
            normalized = _minmax(raw)
            probabilities = scores_to_probabilities(raw)
            top6, order = e.rank_top6(normalized)
            result[name] = {
                "family": CANDIDATES[name],
                "top6": top6,
                "ranking60": e.NUMBERS[order].tolist(),
                "scores": {str(i + 1): float(normalized[i]) for i in range(60)},
                "probabilities": {str(i + 1): float(probabilities[i]) for i in range(60)},
                "probability_sum": float(probabilities.sum()),
                "production_authority": False,
                "status": "SHADOW_ONLY",
            }
        return result


class FrontierState:
    def __init__(self, recent_window: int = 64) -> None:
        self.step = 0
        self.last_seen = np.full(60, -1, dtype=int)
        self.gap_trials = np.zeros(len(GAP_BOUNDS) + 1, dtype=float)
        self.gap_successes = np.zeros(len(GAP_BOUNDS) + 1, dtype=float)
        self.transition = np.zeros((60, 60), dtype=float)
        self.cooccurrence = np.zeros((60, 60), dtype=float)
        self.weekday_counts = np.zeros((7, 60), dtype=float)
        self.weekday_draws = np.zeros(7, dtype=float)
        self.global_counts = np.zeros(60, dtype=float)
        self.recent: deque[np.ndarray] = deque(maxlen=int(recent_window))
        self.previous_draw: np.ndarray | None = None

    def _current_gaps(self) -> np.ndarray:
        unseen = self.last_seen < 0
        gaps = self.step - self.last_seen
        gaps[unseen] = self.step + 1
        return np.maximum(gaps, 1)

    def predict(self, target_weekday: int) -> FrontierPrediction:
        weekday = int(target_weekday)
        if weekday < 0 or weekday > 6:
            raise ValueError("target weekday must be in [0,6]")
        gaps = self._current_gaps()
        gap_score = np.asarray([
            (self.gap_successes[_gap_bucket(int(gap))] + 1.0)
            / (self.gap_trials[_gap_bucket(int(gap))] + 10.0)
            for gap in gaps
        ], dtype=float)

        if self.previous_draw is None:
            transition_score = np.full(60, UNIFORM_PROBABILITY)
            graph_score = np.full(60, UNIFORM_PROBABILITY)
        else:
            rows = self.previous_draw - 1
            transition_den = self.transition[rows].sum(axis=1, keepdims=True) + 60.0
            transition_score = np.mean((self.transition[rows] + 1.0) / transition_den, axis=0)
            graph_den = self.cooccurrence[rows].sum(axis=1, keepdims=True) + 60.0
            graph_score = np.mean((self.cooccurrence[rows] + 1.0) / graph_den, axis=0)

        weekday_score = (self.weekday_counts[weekday] + 1.0) / (self.weekday_draws[weekday] + 10.0)
        global_rate = (self.global_counts + 1.0) / (self.step + 10.0)
        if self.recent:
            recent_counts = np.sum(np.vstack(self.recent), axis=0)
            recent_rate = (recent_counts + 1.0) / (len(self.recent) + 10.0)
        else:
            recent_rate = np.full(60, UNIFORM_PROBABILITY)
        recent_lift = np.log(np.clip(recent_rate, 1e-9, 1.0)) - np.log(np.clip(global_rate, 1e-9, 1.0))
        recent_lift = np.exp(np.clip(recent_lift, -4.0, 4.0))

        return FrontierPrediction({
            "frontier_gap_hazard": gap_score,
            "frontier_transition_markov": transition_score,
            "frontier_cooccurrence_graph": graph_score,
            "frontier_weekday_bayes": weekday_score,
            "frontier_recent_lift": recent_lift,
        })

    def update(self, draw: np.ndarray, weekday: int) -> None:
        values = np.asarray(draw, dtype=int)
        if values.shape != (6,) or len(set(values.tolist())) != 6 or values.min() < 1 or values.max() > 60:
            raise ValueError("draw must contain six unique numbers in [1,60]")
        gaps = self._current_gaps()
        actual = set(values.tolist())
        for number in range(1, 61):
            bucket = _gap_bucket(int(gaps[number - 1]))
            self.gap_trials[bucket] += 1.0
            if number in actual:
                self.gap_successes[bucket] += 1.0
        if self.previous_draw is not None:
            for source in self.previous_draw:
                self.transition[int(source) - 1, values - 1] += 1.0
        for i, left in enumerate(values):
            others = np.delete(values, i)
            self.cooccurrence[int(left) - 1, others - 1] += 1.0
        self.weekday_counts[int(weekday), values - 1] += 1.0
        self.weekday_draws[int(weekday)] += 1.0
        self.global_counts[values - 1] += 1.0
        onehot = np.zeros(60, dtype=float)
        onehot[values - 1] = 1.0
        self.recent.append(onehot)
        self.last_seen[values - 1] = self.step
        self.previous_draw = values.copy()
        self.step += 1


def sign_flip_pvalue(differences: list[float], seed: int, replications: int = 20000) -> float:
    values = np.asarray(differences, dtype=float)
    if values.size == 0:
        return 1.0
    observed = float(np.mean(values))
    if observed <= 0.0:
        return 1.0
    rng = np.random.default_rng(int(seed))
    exceed = 0
    chunk = 1000
    remaining = int(replications)
    while remaining:
        size = min(chunk, remaining)
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=(size, values.size))
        simulated = np.mean(signs * values, axis=1)
        exceed += int(np.sum(simulated >= observed - 1e-15))
        remaining -= size
    return float((exceed + 1) / (int(replications) + 1))


def holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for index, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, float(value) * (total - index)))
        adjusted[name] = running
    return adjusted


def _split_name(contest: int) -> str:
    if int(contest) <= 2200:
        return "calibration"
    if int(contest) <= 2700:
        return "validation"
    return "holdout"


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    n = len(rows)
    return {
        "n": n,
        "hits": int(sum(row["hits"] for row in rows)),
        "mean_hits": float(np.mean([row["hits"] for row in rows])),
        "champion_hits": int(sum(row["champion_hits"] for row in rows)),
        "mean_delta_hits_vs_champion": float(np.mean([row["delta_hits"] for row in rows])),
        "mean_brier": float(np.mean([row["brier"] for row in rows])),
        "mean_brier_delta_vs_uniform": float(np.mean([row["brier"] - UNIFORM_BRIER for row in rows])),
        "events_3plus": int(sum(row["hits"] >= 3 for row in rows)),
        "events_4plus": int(sum(row["hits"] >= 4 for row in rows)),
        "events_5plus": int(sum(row["hits"] >= 5 for row in rows)),
        "events_6": int(sum(row["hits"] == 6 for row in rows)),
        "mean_novelty_vs_champion": float(np.mean([row["novelty"] for row in rows])),
    }


def run_historical(data_path: Path, start_index: int = 1000) -> tuple[dict[str, Any], FrontierState, pd.DataFrame]:
    frame = pd.read_excel(data_path)
    draws, contests = e.load_draws(data_path)
    dates = pd.to_datetime(frame["Data do Sorteio"], format="mixed", dayfirst=True, errors="raise")
    if len(dates) != len(draws):
        raise ValueError("date and draw lengths differ")
    champion = e.walk_forward(draws, contests, start=int(start_index))
    champion_by_contest = {int(row["contest"]): row for row in champion.rows}
    state = FrontierState()
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in CANDIDATES}

    for t in range(len(draws)):
        prediction = state.predict(int(dates.iloc[t].weekday())).document()
        if t >= int(start_index):
            contest = int(contests[t])
            actual = set(int(value) for value in draws[t])
            champion_row = champion_by_contest[contest]
            champion_top6 = set(int(value) for value in champion_row["top6"])
            for name, document in prediction.items():
                top6 = set(int(value) for value in document["top6"])
                probabilities = np.asarray([document["probabilities"][str(i)] for i in range(1, 61)], dtype=float)
                hits = len(top6 & actual)
                rows[name].append({
                    "contest": contest,
                    "cutoff_contest": int(contests[t - 1]),
                    "split": _split_name(contest),
                    "top6": sorted(top6),
                    "hits": int(hits),
                    "champion_hits": int(champion_row["hits"]),
                    "delta_hits": int(hits - int(champion_row["hits"])),
                    "novelty": float(1.0 - len(top6 & champion_top6) / 6.0),
                    "brier": brier(probabilities, draws[t]),
                    "probabilities": {str(i + 1): float(probabilities[i]) for i in range(60)},
                    "probability_sum": float(probabilities.sum()),
                })
        state.update(draws[t], int(dates.iloc[t].weekday()))

    raw_p = {
        name: sign_flip_pvalue([row["delta_hits"] for row in candidate_rows], 20260904 + index)
        for index, (name, candidate_rows) in enumerate(rows.items())
    }
    adjusted = holm_adjust(raw_p)
    summaries: dict[str, Any] = {}
    for name, candidate_rows in rows.items():
        split = {
            part: _summarize([row for row in candidate_rows if row["split"] == part])
            for part in ("calibration", "validation", "holdout")
        }
        overall = _summarize(candidate_rows)
        stable = (
            split["calibration"].get("mean_delta_hits_vs_champion", -math.inf) >= 0.0
            and split["validation"].get("mean_delta_hits_vs_champion", -math.inf) >= 0.0
            and split["holdout"].get("mean_delta_hits_vs_champion", -math.inf) > 0.0
        )
        summaries[name] = {
            "family": CANDIDATES[name],
            "overall": overall,
            "splits": split,
            "paired_sign_flip_p_vs_champion": raw_p[name],
            "holm_adjusted_p": adjusted[name],
            "stable_nonnegative_then_positive_holdout": bool(stable),
            "historical_diagnostic_pass": bool(stable and adjusted[name] < 0.05),
            "production_authority": False,
            "status": "HISTORICAL_DIAGNOSTIC_ONLY",
        }
    result = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "data_file": Path(data_path).name,
        "data_sha256": sha256_file(data_path),
        "start_index": int(start_index),
        "contest_count": int(len(draws)),
        "evaluated_contests": int(len(draws) - int(start_index)),
        "candidate_count": len(CANDIDATES),
        "all_candidates_reported": True,
        "future_leakage": False,
        "partitions": {"calibration": "1001-2200", "validation": "2201-2700", "holdout": f"2701-{int(contests[-1])}"},
        "multiple_testing": {"method": "Holm", "family_size": len(CANDIDATES), "alpha": 0.05},
        "summaries": summaries,
        "rows": rows,
        "interpretation": {
            "historical_data_already_seen": True,
            "historical_results_cannot_authorize_material_weight": True,
            "prospective_evidence_starts_after_registration_cutoff": int(contests[-1]),
            "falsification_over_promotion": True,
        },
    }
    result["sha256"] = sha256_json(result)
    return result, state, frame


def register_candidates(registry_path: Path, cutoff: int) -> dict[str, Any]:
    governance = load_registry(registry_path, tuple(SIGNAL_NAMES))
    for candidate_id, family in CANDIDATES.items():
        if candidate_id not in governance.candidates:
            governance.register(candidate_id, family, int(cutoff))
        else:
            state = governance.candidates[candidate_id]
            if state.family != family or state.registered_cutoff != int(cutoff):
                raise ValueError("existing frontier candidate registration differs")
    registry_sha = write_registry(registry_path, governance)
    return {"sha256": registry_sha, "snapshot": governance.snapshot()}


def freeze_shadow(
    state: FrontierState,
    data_path: Path,
    target: int,
    target_date: str,
    report_path: Path,
    freeze_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    if freeze_path.exists():
        raise FileExistsError(f"refusing to overwrite existing frontier freeze: {freeze_path}")
    draw_date = datetime.strptime(str(target_date), "%d/%m/%Y")
    prediction = state.predict(draw_date.weekday()).document()
    cutoff = int(target) - 1
    registration = register_candidates(registry_path, cutoff)
    freeze = {
        "schema": FREEZE_SCHEMA,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": int(target),
        "target_date": draw_date.strftime("%d/%m/%Y"),
        "cutoff_contest": cutoff,
        "data_file": Path(data_path).name,
        "data_sha256": sha256_file(data_path),
        "engine_file": Path(__file__).name,
        "engine_sha256": sha256_file(Path(__file__)),
        "historical_report_file": report_path.name,
        "historical_report_sha256": sha256_file(report_path),
        "registry_file": registry_path.name,
        "registry_sha256": registration["sha256"],
        "registry_snapshot_sha256": registration["snapshot"]["sha256"],
        "candidate_predictions": prediction,
        "candidate_count": len(prediction),
        "all_candidates_frozen": True,
        "production_authority": False,
        "material_weight": 0.0,
        "status": "FROZEN_SHADOW_ONLY",
        "promotion_requires_future_oos_evidence": True,
        "result_used": False,
    }
    freeze["sha256"] = sha256_json(freeze)
    freeze_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")
    return freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--target", required=True, type=int)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--registry", default="SMART_SIGNAL_EXPANSION_REGISTRY.json")
    parser.add_argument("--start", default=1000, type=int)
    args = parser.parse_args()
    data_path = Path(args.data)
    report_path = Path(args.report)
    freeze_path = Path(args.freeze)
    if report_path.exists():
        raise FileExistsError(f"refusing to overwrite existing frontier report: {report_path}")
    historical, state, _ = run_historical(data_path, args.start)
    report_path.write_text(json.dumps(historical, ensure_ascii=False, indent=2), encoding="utf-8")
    freeze = freeze_shadow(
        state,
        data_path,
        args.target,
        args.target_date,
        report_path,
        freeze_path,
        Path(args.registry),
    )
    print(json.dumps({
        "historical": {
            "report": report_path.name,
            "sha256": sha256_file(report_path),
            "summaries": historical["summaries"],
        },
        "freeze": {
            "file": freeze_path.name,
            "sha256": sha256_file(freeze_path),
            "target": freeze["target_contest"],
            "candidate_top6": {name: row["top6"] for name, row in freeze["candidate_predictions"].items()},
        },
        "registry_sha256": freeze["registry_sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

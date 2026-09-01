from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import river
from river import drift

import smart_v2_engine as e

ROUNDS_PER_SCENARIO = 10
BASE_SEED = 20260828
VAR_ONE = 6 * (6 / 60) * (1 - 6 / 60) * (54 / 59)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def zscore(excess: float, n: int) -> float:
    return float(excess / math.sqrt(max(1e-12, n * VAR_ONE)))


def gen_uniform(rng: np.random.Generator, steps: int) -> np.ndarray:
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(steps)], dtype=int)


def gen_weighted(rng: np.random.Generator, steps: int, target: np.ndarray, weight: float = 3.0) -> np.ndarray:
    w = np.ones(60, dtype=float)
    w[np.asarray(target, dtype=int) - 1] = weight
    p = w / w.sum()
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False, p=p)) for _ in range(steps)], dtype=int)


def disjoint_targets(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    a = np.sort(rng.choice(e.NUMBERS, 6, replace=False))
    remaining = np.setdiff1d(e.NUMBERS, a)
    b = np.sort(rng.choice(remaining, 6, replace=False))
    return a, b


def evaluate(draws: np.ndarray, warmup: int) -> dict:
    contests = np.arange(1, len(draws) + 1)
    r = e.walk_forward(draws, contests, warmup)
    n = len(draws) - warmup
    return {
        "eval_draws": int(n),
        "hits": int(r.total_hits),
        "expected": float(r.uniform_expected),
        "excess": float(r.excess_hits),
        "z": zscore(r.excess_hits, n),
        "max_abs_corr": float(r.max_abs_corr),
        "final_family_weights": r.family_weights,
        "finite": bool(np.isfinite(r.total_hits) and np.isfinite(r.excess_hits) and np.isfinite(r.max_abs_corr)),
    }


def adwin_shift(draws: np.ndarray, target: np.ndarray, boundary: int) -> dict:
    detector = drift.ADWIN()
    detections: list[int] = []
    target_set = set(int(x) for x in target)
    for i, row in enumerate(draws):
        value = len(target_set.intersection(int(x) for x in row)) / 6.0
        detector.update(value)
        if detector.drift_detected:
            detections.append(i)
    after = [x for x in detections if x >= boundary]
    return {
        "detections": detections,
        "detected_after_boundary": bool(after),
        "first_after_boundary": int(after[0]) if after else None,
        "delay": int(after[0] - boundary) if after else None,
    }


def round_record(round_id: int, scenario: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    record = {"round": round_id, "scenario": scenario, "seed": seed}

    if scenario == "iid_null":
        draws = gen_uniform(rng, 700)
        record["result"] = evaluate(draws, 200)

    elif scenario == "persistent_bias":
        target = np.sort(rng.choice(e.NUMBERS, 6, replace=False))
        draws = gen_weighted(rng, 900, target, 3.0)
        record["target"] = target.tolist()
        record["result"] = evaluate(draws, 200)

    elif scenario == "regime_shift":
        target_a, target_b = disjoint_targets(rng)
        draws = np.vstack([
            gen_weighted(rng, 450, target_a, 3.0),
            gen_weighted(rng, 450, target_b, 3.0),
        ])
        record["target_a"] = target_a.tolist()
        record["target_b"] = target_b.tolist()
        record["result"] = evaluate(draws, 200)
        record["river_adwin"] = adwin_shift(draws, target_a, 450)

    elif scenario == "signal_vanishes":
        target = np.sort(rng.choice(e.NUMBERS, 6, replace=False))
        draws = np.vstack([
            gen_weighted(rng, 450, target, 3.0),
            gen_uniform(rng, 450),
        ])
        record["target"] = target.tolist()
        record["result"] = evaluate(draws, 200)
        record["uniform_tail"] = evaluate(draws[450:], 150)
        record["river_adwin"] = adwin_shift(draws, target, 450)

    elif scenario == "alternating_adversarial":
        target_a, target_b = disjoint_targets(rng)
        parts = []
        for i in range(900):
            target = target_a if i % 2 == 0 else target_b
            parts.append(gen_weighted(rng, 1, target, 3.0)[0])
        draws = np.asarray(parts, dtype=int)
        record["target_a"] = target_a.tolist()
        record["target_b"] = target_b.tolist()
        record["result"] = evaluate(draws, 200)

    else:
        raise ValueError(f"unknown scenario: {scenario}")

    return record


def summarize(records: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for scenario in sorted(set(r["scenario"] for r in records)):
        rs = [r for r in records if r["scenario"] == scenario]
        zs = np.array([r["result"]["z"] for r in rs], dtype=float)
        excess = np.array([r["result"]["excess"] for r in rs], dtype=float)
        hits = np.array([r["result"]["hits"] for r in rs], dtype=float)
        item = {
            "rounds": len(rs),
            "mean_hits": float(hits.mean()),
            "mean_excess": float(excess.mean()),
            "mean_z": float(zs.mean()),
            "min_z": float(zs.min()),
            "max_z": float(zs.max()),
            "rate_z_ge_2": float(np.mean(zs >= 2.0)),
            "all_finite": bool(all(r["result"]["finite"] for r in rs)),
        }
        if scenario == "signal_vanishes":
            tail_z = np.array([r["uniform_tail"]["z"] for r in rs], dtype=float)
            item["uniform_tail_mean_z"] = float(tail_z.mean())
            item["uniform_tail_rate_abs_z_ge_2"] = float(np.mean(np.abs(tail_z) >= 2.0))
        if scenario in {"regime_shift", "signal_vanishes"}:
            flags = [r["river_adwin"]["detected_after_boundary"] for r in rs]
            delays = [r["river_adwin"]["delay"] for r in rs if r["river_adwin"]["delay"] is not None]
            item["adwin_detection_rate"] = float(np.mean(flags))
            item["adwin_mean_delay"] = float(np.mean(delays)) if delays else None
        summary[scenario] = item
    return summary


def main() -> None:
    scenarios = (
        ["iid_null"] * ROUNDS_PER_SCENARIO
        + ["persistent_bias"] * ROUNDS_PER_SCENARIO
        + ["regime_shift"] * ROUNDS_PER_SCENARIO
        + ["signal_vanishes"] * ROUNDS_PER_SCENARIO
        + ["alternating_adversarial"] * ROUNDS_PER_SCENARIO
    )
    records = []
    for idx, scenario in enumerate(scenarios, start=1):
        seed = BASE_SEED + idx * 1009
        records.append(round_record(idx, scenario, seed))

    summary = summarize(records)
    structural_checks = {
        "exactly_50_rounds": len(records) == 50,
        "ten_per_scenario": all(v["rounds"] == 10 for v in summary.values()),
        "all_metrics_finite": all(v["all_finite"] for v in summary.values()),
        "null_false_positive_rate_le_0_10": summary["iid_null"]["rate_z_ge_2"] <= 0.10,
        "persistent_bias_detected_majority": summary["persistent_bias"]["rate_z_ge_2"] >= 0.50,
        "regime_shift_detected_majority": summary["regime_shift"]["rate_z_ge_2"] >= 0.50,
        "river_adwin_detects_shift_majority": summary["regime_shift"]["adwin_detection_rate"] >= 0.50,
        "river_adwin_detects_vanishing_signal_majority": summary["signal_vanishes"]["adwin_detection_rate"] >= 0.50,
    }

    report = {
        "schema": "SMART_50_ROUND_SIMULATION_1",
        "purpose": "Simulated robustness exercise only; not prospective predictive proof.",
        "river_version": river.__version__,
        "engine_sha256": file_sha256(Path("smart_v2_engine.py")),
        "simulation_sha256": file_sha256(Path(__file__)),
        "base_seed": BASE_SEED,
        "rounds_total": len(records),
        "scenario_distribution": {name: scenarios.count(name) for name in sorted(set(scenarios))},
        "summary": summary,
        "structural_checks": structural_checks,
        "passed": bool(all(structural_checks.values())),
        "records": records,
    }
    out = Path("SMART_50_ROUND_SIMULATION.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "rounds_total": report["rounds_total"],
        "summary": report["summary"],
        "structural_checks": report["structural_checks"],
        "passed": report["passed"],
        "output": str(out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

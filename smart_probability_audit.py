from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from smart_experiment_lab import monte_carlo_null_hits
from smart_falsification_lab import holm_adjust
from smart_v2_engine import _strict_integral

SCHEMA = "SMART_PROBABILITY_AUDIT_V1"
UNIFORM_INCLUSION_PROBABILITY = 0.1
UNIFORM_MEAN_BRIER = 0.09
UNIFORM_EXPECTED_HITS = 0.6
DEFAULT_MC_REPLICATIONS = 20_000
DEFAULT_BOOTSTRAP_REPLICATIONS = 5_000
DEFAULT_SEED = 20260904


def _canonical_json(document: Any) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(document: Any) -> str:
    return hashlib.sha256(_canonical_json(document)).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_embedded_hash(document: dict[str, Any]) -> None:
    observed = document.get("sha256")
    canonical = dict(document)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError("source embedded hash mismatch")


def moving_block_mean_ci(
    values: np.ndarray,
    replications: int,
    seed: int,
    block_size: int = 25,
    alpha: float = 0.05,
) -> dict[str, float]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 2 or np.any(~np.isfinite(x)):
        raise ValueError("values must be a finite 1D sample with at least two items")
    if replications < 100:
        raise ValueError("bootstrap replications must be at least 100")
    if block_size < 1:
        raise ValueError("block_size must be positive")
    rng = np.random.default_rng(seed)
    blocks = int(math.ceil(len(x) / block_size))
    offsets = np.arange(block_size)
    estimates = np.empty(replications, dtype=float)
    for index in range(replications):
        starts = rng.integers(0, len(x), size=blocks)
        selection = ((starts[:, None] + offsets[None, :]) % len(x)).ravel()[: len(x)]
        estimates[index] = float(x[selection].mean())
    return {
        "mean": float(x.mean()),
        "lower": float(np.quantile(estimates, alpha / 2.0)),
        "upper": float(np.quantile(estimates, 1.0 - alpha / 2.0)),
        "alpha": float(alpha),
        "block_size": int(block_size),
        "replications": int(replications),
    }


def _strict_top6(values: Any) -> list[int]:
    if not isinstance(values, list) or len(values) != 6:
        raise ValueError("top6 must contain exactly six numbers")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("top6 must contain integers")
    result = [int(value) for value in values]
    if len(set(result)) != 6 or min(result) < 1 or max(result) > 60:
        raise ValueError("top6 must contain six unique values in [1,60]")
    return result


def audit_historical(
    source: dict[str, Any],
    partition: str = "holdout",
    mc_replications: int = DEFAULT_MC_REPLICATIONS,
    bootstrap_replications: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    verify_embedded_hash(source)
    if source.get("future_leakage") is not False:
        raise ValueError("source does not declare future_leakage=false")
    rows_by_candidate = source.get("rows")
    if not isinstance(rows_by_candidate, dict) or not rows_by_candidate:
        raise ValueError("source rows are missing")

    candidates: dict[str, Any] = {}
    raw_hit_pvalues: list[float] = []
    ordered_names = sorted(rows_by_candidate)
    for candidate_index, name in enumerate(ordered_names):
        rows = [
            row for row in rows_by_candidate[name] if row.get("split") == partition
        ]
        if not rows:
            raise ValueError(f"candidate {name} has no rows for partition {partition}")
        contests = np.asarray([_strict_integral(row["contest"], "contest") for row in rows], dtype=int)
        cutoffs = np.asarray([_strict_integral(row["cutoff_contest"], "cutoff_contest") for row in rows], dtype=int)
        if np.any(np.diff(contests) <= 0) or np.any(cutoffs != contests - 1):
            raise ValueError(f"candidate {name} violates causal contest ordering")
        for row in rows:
            _strict_top6(row["top6"])
        hits = np.asarray([_strict_integral(row["hits"], "hits") for row in rows], dtype=int)
        if np.any((hits < 0) | (hits > 6)):
            raise ValueError(f"candidate {name} has invalid hit counts")
        brier = np.asarray([float(row["brier"]) for row in rows], dtype=float)
        if np.any(~np.isfinite(brier)) or np.any((brier < 0.0) | (brier > 1.0)):
            raise ValueError(f"candidate {name} has invalid Brier scores")

        null = monte_carlo_null_hits(
            hits,
            replications=mc_replications,
            seed=seed + candidate_index,
        )
        brier_delta = brier - UNIFORM_MEAN_BRIER
        brier_ci = moving_block_mean_ci(
            brier_delta,
            replications=bootstrap_replications,
            seed=seed + 10_000 + candidate_index,
        )
        raw_hit_pvalues.append(float(null["p_null_ge_observed"]))
        candidates[name] = {
            "partition": partition,
            "n": int(len(rows)),
            "contest_min": int(contests.min()),
            "contest_max": int(contests.max()),
            "causal_cutoff_verified": True,
            "mean_hits": float(hits.mean()),
            "total_hits": int(hits.sum()),
            "uniform_expected_mean_hits": UNIFORM_EXPECTED_HITS,
            "uniform_expected_total_hits": float(len(hits) * UNIFORM_EXPECTED_HITS),
            "hit_null": null,
            "mean_brier": float(brier.mean()),
            "uniform_mean_brier": UNIFORM_MEAN_BRIER,
            "mean_brier_delta_vs_uniform": float(brier_delta.mean()),
            "brier_delta_moving_block_ci95": brier_ci,
            "events_6of6": int(np.count_nonzero(hits == 6)),
            "full_probability_vectors_retained": False,
            "reliability_diagram_status": "UNAVAILABLE_HISTORICAL_PROBABILITIES_NOT_RETAINED",
            "predictive_weight_authorized": False,
        }

    adjusted = holm_adjust(raw_hit_pvalues)
    for name, p_adjusted in zip(ordered_names, adjusted):
        row = candidates[name]
        row["hits_holm_adjusted_p"] = float(p_adjusted)
        row["hits_reject_uniform_at_fwer_0_05"] = bool(p_adjusted <= 0.05)
        brier_better = row["brier_delta_moving_block_ci95"]["upper"] < 0.0
        row["brier_materially_better_than_uniform"] = bool(brier_better)
        row["historical_dual_gate_pass"] = bool(
            row["hits_reject_uniform_at_fwer_0_05"] and brier_better
        )
        row["decision"] = (
            "HISTORICAL_SIGNAL_ONLY_NO_PROMOTION"
            if row["historical_dual_gate_pass"]
            else "RETAIN_UNIFORM_BASELINE"
        )

    all_causal = all(
        candidate["causal_cutoff_verified"] for candidate in candidates.values()
    )
    any_terminal = any(candidate["events_6of6"] > 0 for candidate in candidates.values())
    return {
        "schema": SCHEMA,
        "source_schema": source.get("schema"),
        "source_sha256": source.get("sha256"),
        "partition": partition,
        "historical_data_already_seen": True,
        "candidate_count": len(candidates),
        "candidate_names": ordered_names,
        "causal_cutoff_verified_all": all_causal,
        "baselines": {
            "uniform_inclusion_probability": UNIFORM_INCLUSION_PROBABILITY,
            "uniform_expected_hits_per_top6": UNIFORM_EXPECTED_HITS,
            "uniform_mean_brier_per_number": UNIFORM_MEAN_BRIER,
        },
        "multiplicity": {
            "method": "Holm",
            "family_size": len(candidates),
            "alpha": 0.05,
        },
        "candidates": candidates,
        "calibration_limitation": (
            "Historical rows retain Brier scores but not all 60 probabilities; "
            "reliability bins and ECE cannot be independently reconstructed."
        ),
        "prospective_contract": {
            "retain_all_60_probabilities": True,
            "retain_official_outcome_vector": True,
            "score_before_any_retraining": True,
            "compare_brier_and_hits_with_uniform": True,
            "promotion_requires_multiple_contests": True,
        },
        "predictive_weight_authorized": False,
        "terminal_6of6_observed_in_audited_partition": bool(any_terminal),
        "terminal_6of6_proven": False,
        "mission_state": "MISSION_ACTIVE",
    }


def write_audit(
    source_path: str | Path,
    output_path: str | Path,
    partition: str = "holdout",
    mc_replications: int = DEFAULT_MC_REPLICATIONS,
    bootstrap_replications: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    source_path = Path(source_path)
    source = json.loads(source_path.read_text(encoding="utf-8-sig"))
    audit = audit_historical(
        source,
        partition=partition,
        mc_replications=mc_replications,
        bootstrap_replications=bootstrap_replications,
        seed=seed,
    )
    audit.update(
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_file": source_path.name,
            "source_file_sha256": sha256_file(source_path),
            "mc_replications": int(mc_replications),
            "bootstrap_replications": int(bootstrap_replications),
            "seed": int(seed),
        }
    )
    audit["audit_sha256"] = sha256_json(audit)
    Path(output_path).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="SMART_FRONTIER_HISTORICAL_3053.json")
    parser.add_argument("--output", default="SMART_PROBABILITY_AUDIT.json")
    parser.add_argument("--partition", default="holdout")
    parser.add_argument("--mc-replications", type=int, default=DEFAULT_MC_REPLICATIONS)
    parser.add_argument(
        "--bootstrap-replications", type=int, default=DEFAULT_BOOTSTRAP_REPLICATIONS
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    audit = write_audit(
        args.source,
        args.output,
        partition=args.partition,
        mc_replications=args.mc_replications,
        bootstrap_replications=args.bootstrap_replications,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "schema": audit["schema"],
                "partition": audit["partition"],
                "candidate_count": audit["candidate_count"],
                "decisions": {
                    name: row["decision"] for name, row in audit["candidates"].items()
                },
                "predictive_weight_authorized": audit[
                    "predictive_weight_authorized"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

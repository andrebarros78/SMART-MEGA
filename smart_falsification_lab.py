from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

import smart_randomness_cartography as rc
from smart_cartography_extended import binary_mi, network_structure
from smart_v2_engine import load_draws, onehot

SCHEMA = "SMART_FALSIFICATION_LAB_V1"
PREREG_SCHEMA = "SMART_P4_P5_PREREGISTRATION_V1"
DEFAULT_SEED = 20260904
DEFAULT_HOLDOUT_FRACTION = 0.30
ALPHA = 0.05

HYPOTHESES: dict[str, dict[str, Any]] = {
    "H_MARGINAL_001": {
        "metric": "marginal_std",
        "direction": "greater",
        "nulls": ("U0",),
        "claim": "marginal dispersion exceeds uniform 6-of-60 sampling variation",
    },
    "H_MEMORY_001": {
        "metric": "lag1_binary_mutual_information_mean_bits",
        "direction": "greater",
        "nulls": ("U1", "U3", "U4"),
        "claim": "lag-1 inclusion dependence exceeds temporal and fixed-marginal surrogates",
    },
    "H_GRAPH_001": {
        "metric": "network_average_clustering",
        "direction": "greater",
        "nulls": ("U0", "U4"),
        "claim": "cooccurrence clustering exceeds iid and fixed-marginal surrogates",
    },
    "H_REGIME_001": {
        "metric": "regime_max_cusum",
        "direction": "greater",
        "nulls": ("U0", "U1", "U3", "U5"),
        "claim": "the causal feature stream has a change-point score beyond declared nulls",
    },
}

FAMILY_SIZE = sum(len(hypothesis["nulls"]) for hypothesis in HYPOTHESES.values())
MIN_REPLICATIONS_FOR_HOLM_RESOLUTION = int(math.ceil(FAMILY_SIZE / ALPHA - 1))
DEFAULT_REPLICATIONS = max(200, MIN_REPLICATIONS_FOR_HOLM_RESOLUTION)
ALL_METRICS = frozenset(hypothesis["metric"] for hypothesis in HYPOTHESES.values())


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(document: Any) -> str:
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate(draws: np.ndarray, contests: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = rc._v(draws)
    c = np.asarray(contests, dtype=int)
    if c.ndim != 1 or len(c) != len(a):
        raise ValueError("contests length mismatch")
    if len(a) < 80:
        raise ValueError("at least 80 draws are required")
    if np.any(np.diff(c) <= 0):
        raise ValueError("contests must be strictly increasing")
    return a, c


def _regime_max_cusum_validated(a: np.ndarray, trim_fraction: float = 0.10) -> float:
    n = len(a)
    features = np.column_stack([a.sum(axis=1), (a % 2 == 0).sum(axis=1), a[:, -1] - a[:, 0]]).astype(float)
    scale = features.std(axis=0, ddof=1)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z = (features - features.mean(axis=0)) / scale
    cumulative = np.cumsum(z, axis=0) / math.sqrt(n)
    trim = max(5, int(math.ceil(n * trim_fraction)))
    if n - trim <= trim:
        raise ValueError("sample too small for trimmed CUSUM")
    interior = cumulative[trim : n - trim]
    return float(np.linalg.norm(interior, axis=1).max())


def regime_max_cusum(draws: np.ndarray, trim_fraction: float = 0.10) -> float:
    return _regime_max_cusum_validated(rc._v(draws), trim_fraction)


def _lag1_binary_mutual_information_mean_bits(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.uint8)
    if len(x) < 2:
        return 0.0
    left = x[:-1]
    right = x[1:]
    n = float(len(left))
    n11 = (left * right).sum(axis=0).astype(float)
    sx = left.sum(axis=0).astype(float)
    sy = right.sum(axis=0).astype(float)
    joints = (
        (n - sx - sy + n11) / n,
        (sy - n11) / n,
        (sx - n11) / n,
        n11 / n,
    )
    px = (1.0 - sx / n, sx / n)
    py = (1.0 - sy / n, sy / n)
    mi = np.zeros(x.shape[1], dtype=float)
    for i, j, joint in ((0, 0, joints[0]), (0, 1, joints[1]), (1, 0, joints[2]), (1, 1, joints[3])):
        denom = px[i] * py[j]
        mask = (joint > 0.0) & (denom > 0.0)
        mi[mask] += joint[mask] * np.log2(joint[mask] / denom[mask])
    return float(mi.mean())


def _network_average_clustering_from_onehot(x: np.ndarray) -> float:
    pairs = x.T @ x
    np.fill_diagonal(pairs, 0)
    upper = pairs[np.triu_indices(60, 1)].astype(float)
    threshold = float(upper.mean() + upper.std(ddof=1))
    adjacency = (pairs > threshold).astype(np.int64)
    np.fill_diagonal(adjacency, 0)
    degree = adjacency.sum(axis=1).astype(float)
    # diag(A^3) = 2 * triangles incident to each vertex. NetworkX's
    # unweighted local clustering is diag(A^3)/(d*(d-1)).
    diag_a3 = np.diag(adjacency @ adjacency @ adjacency).astype(float)
    denominator = degree * (degree - 1.0)
    local = np.divide(diag_a3, denominator, out=np.zeros_like(diag_a3), where=denominator > 0.0)
    return float(local.mean())


def metric_vector(draws: np.ndarray, metrics: set[str] | frozenset[str] | None = None) -> dict[str, float]:
    a = rc._v(draws)
    requested = ALL_METRICS if metrics is None else frozenset(metrics)
    unknown = requested - ALL_METRICS
    if unknown:
        raise ValueError(f"unknown metrics requested: {sorted(unknown)}")
    result: dict[str, float] = {}
    x = None
    needs_x = bool(requested & {"marginal_std", "lag1_binary_mutual_information_mean_bits", "network_average_clustering"})
    if needs_x:
        x = onehot(a)
    if "marginal_std" in requested:
        result["marginal_std"] = float(x.mean(axis=0).std(ddof=1))
    if "lag1_binary_mutual_information_mean_bits" in requested:
        result["lag1_binary_mutual_information_mean_bits"] = _lag1_binary_mutual_information_mean_bits(x)
    if "network_average_clustering" in requested:
        result["network_average_clustering"] = _network_average_clustering_from_onehot(x)
    if "regime_max_cusum" in requested:
        result["regime_max_cusum"] = _regime_max_cusum_validated(a)
    return result


def holm_adjust(pvalues: list[float]) -> list[float]:
    if not pvalues:
        return []
    p = np.asarray(pvalues, dtype=float)
    if np.any(~np.isfinite(p)) or np.any((p < 0.0) | (p > 1.0)):
        raise ValueError("p-values must be finite and within [0,1]")
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(len(p), dtype=float)
    running = 0.0
    total = len(p)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (total - rank) * float(p[index])))
        adjusted[index] = running
    return adjusted.tolist()


def _surrogate(
    family: str,
    draws: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    u4_masks=None,
    u5_model=None,
) -> np.ndarray:
    generators: dict[str, Callable[[], np.ndarray]] = {
        "U0": lambda: rc.u0_uniform_iid(len(draws), rng),
        "U1": lambda: draws[rng.permutation(len(draws))].copy(),
        "U3": lambda: rc.u3_block_shuffle(draws, rng, block_size),
        "U4": lambda: rc.u4_marginals_preserved(draws, rng, prepared_masks=u4_masks),
        "U5": lambda: rc.u5_fitted_dynamic(
            draws,
            rng,
            transition_weights=None if u5_model is None else u5_model[0],
            base_marginals=None if u5_model is None else u5_model[1],
        ),
    }
    try:
        return generators[family]()
    except KeyError as exc:
        raise ValueError(f"unsupported null family: {family}") from exc


def _tail_summary(observed: float, values: list[float]) -> dict[str, float]:
    sample = np.asarray(values, dtype=float)
    exceedances = int(np.count_nonzero(sample >= observed))
    p_value = (exceedances + 1.0) / (len(sample) + 1.0)
    mcse = math.sqrt(p_value * (1.0 - p_value) / (len(sample) + 1.0))
    mean = float(sample.mean())
    std = float(sample.std(ddof=1)) if len(sample) > 1 else 0.0
    z = (observed - mean) / std if std > 0.0 else 0.0
    return {
        "observed": float(observed),
        "null_mean": mean,
        "null_std": std,
        "null_q05": float(np.quantile(sample, 0.05)),
        "null_q50": float(np.quantile(sample, 0.50)),
        "null_q95": float(np.quantile(sample, 0.95)),
        "z": float(z),
        "exceedances": exceedances,
        "empirical_p_greater_add_one": float(p_value),
        "p_mcse": float(mcse),
    }


def build_preregistration(
    contests: np.ndarray,
    data_file: str,
    data_sha256: str,
    code_sha256: str,
    replications: int,
    seed: int,
    holdout_fraction: float,
) -> dict[str, Any]:
    c = np.asarray(contests, dtype=int)
    split = int(math.floor(len(c) * (1.0 - holdout_fraction)))
    design = {
        "schema": PREREG_SCHEMA,
        "objective": "falsify four diagnostic structure hypotheses against declared null universes",
        "data_file": data_file,
        "data_sha256": data_sha256,
        "code_sha256": code_sha256,
        "contest_min": int(c.min()),
        "cutoff_contest": int(c.max()),
        "calibration_end_contest": int(c[split - 1]),
        "evaluation_start_contest": int(c[split]),
        "evaluation_end_contest": int(c[-1]),
        "holdout_fraction": float(holdout_fraction),
        "holdout_integrity": "RETROSPECTIVE_TIME_SPLIT_NOT_PRISTINE",
        "replications": int(replications),
        "seed": int(seed),
        "alpha_familywise": ALPHA,
        "multiplicity": "Holm correction across every hypothesis-null comparison",
        "tail": "greater; add-one empirical Monte Carlo p-value",
        "hypotheses": HYPOTHESES,
        "minimum_replications_for_holm_resolution": MIN_REPLICATIONS_FOR_HOLM_RESOLUTION,
        "resolution_sufficient": bool(replications >= MIN_REPLICATIONS_FOR_HOLM_RESOLUTION),
        "promotion_authority": False,
        "terminal_6of6_claim": False,
    }
    design["design_sha256"] = _sha256_json(design)
    return design


def evaluate_falsification(
    draws: np.ndarray,
    contests: np.ndarray,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
    block_size: int = 25,
) -> dict[str, Any]:
    a, c = _validate(draws, contests)
    if replications < 20:
        raise ValueError("replications must be at least 20")
    if not 0.20 <= holdout_fraction <= 0.50:
        raise ValueError("holdout_fraction must be within [0.20,0.50]")
    split = int(math.floor(len(a) * (1.0 - holdout_fraction)))
    evaluation = a[split:]
    evaluation_contests = c[split:]
    if len(evaluation) < 40:
        raise ValueError("evaluation segment must contain at least 40 draws")

    observed = metric_vector(evaluation)
    required: dict[str, set[str]] = {}
    for hypothesis in HYPOTHESES.values():
        required.setdefault(hypothesis["metric"], set()).update(hypothesis["nulls"])
    null_metrics: dict[tuple[str, str], list[float]] = {
        (metric, family): [] for metric, families in required.items() for family in families
    }
    metrics_by_family: dict[str, set[str]] = {}
    for metric, families_for_metric in required.items():
        for family in families_for_metric:
            metrics_by_family.setdefault(family, set()).add(metric)

    rng = np.random.default_rng(seed)
    families = sorted(metrics_by_family)
    u4_masks = rc.prepare_u4_marginals(evaluation)
    u5_model = rc.prepare_u5_dynamic(evaluation)
    for _ in range(replications):
        for family in families:
            surrogate = _surrogate(
                family,
                evaluation,
                rng,
                block_size,
                u4_masks=u4_masks,
                u5_model=u5_model,
            )
            values = metric_vector(surrogate, metrics_by_family[family])
            for metric in metrics_by_family[family]:
                null_metrics[(metric, family)].append(values[metric])

    comparisons: list[dict[str, Any]] = []
    for hypothesis_id, hypothesis in HYPOTHESES.items():
        metric = hypothesis["metric"]
        for family in hypothesis["nulls"]:
            row = {
                "hypothesis_id": hypothesis_id,
                "claim": hypothesis["claim"],
                "metric": metric,
                "null_family": family,
                "direction": hypothesis["direction"],
                **_tail_summary(observed[metric], null_metrics[(metric, family)]),
            }
            comparisons.append(row)

    family_size = len(comparisons)
    minimum_replications_for_holm_resolution = int(math.ceil(family_size / ALPHA - 1))
    resolution_sufficient = replications >= minimum_replications_for_holm_resolution
    adjusted = holm_adjust([row["empirical_p_greater_add_one"] for row in comparisons])
    for row, p_adjusted in zip(comparisons, adjusted):
        row["holm_adjusted_p"] = float(p_adjusted)
        row["reject_at_familywise_0_05"] = bool(p_adjusted <= ALPHA)
        row["predictive_weight_authorized"] = False

    controls = rc.u6_adversarial_controls(len(evaluation), np.random.default_rng(seed + 1))
    control_metrics = {name: metric_vector(value) for name, value in controls.items()}
    sensitivity = {
        "persistent_bias_detected_by_marginal_dispersion": bool(
            control_metrics["u6_persistent_bias"]["marginal_std"] > control_metrics["u6_null_control"]["marginal_std"]
        ),
        "repeated_motif_detected_by_lag1_mi": bool(
            control_metrics["u6_repeated_motif"]["lag1_binary_mutual_information_mean_bits"]
            > control_metrics["u6_null_control"]["lag1_binary_mutual_information_mean_bits"]
        ),
        "regime_switch_detected_by_cusum": bool(
            control_metrics["u6_regime_switch"]["regime_max_cusum"] > control_metrics["u6_null_control"]["regime_max_cusum"]
        ),
    }

    rejected = [
        f'{row["hypothesis_id"]}:{row["null_family"]}'
        for row in comparisons
        if row["reject_at_familywise_0_05"]
    ]
    conclusion = (
        "INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE: Monte Carlo resolution is insufficient for the declared Holm family."
        if not resolution_sufficient
        else "RETROSPECTIVE_DIAGNOSTIC_ONLY: Monte Carlo resolution is sufficient for the declared Holm family, but the split is not pristine and cannot authorize prediction."
    )
    return {
        "schema": SCHEMA,
        "contest_min": int(c.min()),
        "cutoff_contest": int(c.max()),
        "calibration_draws": int(split),
        "evaluation_draws": int(len(evaluation)),
        "evaluation_start_contest": int(evaluation_contests[0]),
        "evaluation_end_contest": int(evaluation_contests[-1]),
        "holdout_integrity": "RETROSPECTIVE_TIME_SPLIT_NOT_PRISTINE",
        "replications": int(replications),
        "seed": int(seed),
        "observed_evaluation_metrics": observed,
        "comparisons": comparisons,
        "multiplicity": {
            "method": "Holm",
            "family_size": family_size,
            "alpha": ALPHA,
            "rejected_comparisons": rejected,
            "minimum_replications_for_resolution": minimum_replications_for_holm_resolution,
            "resolution_sufficient": bool(resolution_sufficient),
        },
        "adversarial_sensitivity": {
            "checks": sensitivity,
            "all_expected_directions_detected": all(sensitivity.values()),
            "metrics": control_metrics,
        },
        "scientific_conclusion": conclusion,
        "predictive_weight_authorized": False,
        "terminal_6of6_proven": False,
        "mission_state": "MISSION_ACTIVE",
    }


def write_artifacts(
    data_path: str | Path,
    preregistration_path: str | Path,
    report_path: str | Path,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
    expected_max_contest: int = 3053,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data_path = Path(data_path)
    preregistration_path = Path(preregistration_path)
    report_path = Path(report_path)
    draws, contests = load_draws(data_path)
    draws, contests = _validate(draws, contests)
    if int(contests.max()) > int(expected_max_contest):
        raise ValueError("future contest detected beyond expected cutoff")

    prereg = build_preregistration(
        contests=contests,
        data_file=data_path.name,
        data_sha256=_sha256_file(data_path),
        code_sha256=_sha256_file(Path(__file__)),
        replications=replications,
        seed=seed,
        holdout_fraction=holdout_fraction,
    )
    if preregistration_path.exists():
        existing = json.loads(preregistration_path.read_text(encoding="utf-8-sig"))
        if existing.get("design_sha256") != prereg["design_sha256"]:
            raise ValueError("existing preregistration differs from the requested design")
    else:
        prereg_document = dict(prereg)
        prereg_document["registered_at_utc"] = datetime.now(timezone.utc).isoformat()
        preregistration_path.write_text(json.dumps(prereg_document, ensure_ascii=False, indent=2), encoding="utf-8")

    report = evaluate_falsification(
        draws,
        contests,
        replications=replications,
        seed=seed,
        holdout_fraction=holdout_fraction,
    )
    report.update(
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "data_file": data_path.name,
            "data_sha256": _sha256_file(data_path),
            "code_file": Path(__file__).name,
            "code_sha256": _sha256_file(Path(__file__)),
            "preregistration_file": preregistration_path.name,
            "preregistration_design_sha256": prereg["design_sha256"],
        }
    )
    report["report_sha256"] = _sha256_json(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return prereg, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--preregistration", default="SMART_P4_P5_PREREGISTRATION.json")
    parser.add_argument("--report", default="SMART_FALSIFICATION_REPORT_V2.json")
    parser.add_argument("--replications", type=int, default=DEFAULT_REPLICATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--holdout-fraction", type=float, default=DEFAULT_HOLDOUT_FRACTION)
    parser.add_argument("--expected-max-contest", type=int, required=True)
    args = parser.parse_args()
    _, report = write_artifacts(
        args.data,
        args.preregistration,
        args.report,
        replications=args.replications,
        seed=args.seed,
        holdout_fraction=args.holdout_fraction,
        expected_max_contest=args.expected_max_contest,
    )
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "cutoff": report["cutoff_contest"],
                "comparisons": len(report["comparisons"]),
                "holm_rejections": report["multiplicity"]["rejected_comparisons"],
                "resolution_sufficient": report["multiplicity"]["resolution_sufficient"],
                "predictive_weight_authorized": report["predictive_weight_authorized"],
                "mission_state": report["mission_state"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

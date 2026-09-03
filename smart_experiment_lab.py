from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

EXPERIMENT_SCHEMA = "SMART_EXPERIMENT_PROTOCOL_V1"
RESULT_SCHEMA = "SMART_EXPERIMENT_RESULT_V1"
MEMORY_SCHEMA = "SMART_EXPERIMENT_MEMORY_V1"
NULL_SCHEMA = "SMART_MONTE_CARLO_NULL_V1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(_canonical_json(obj)).hexdigest()


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    hypothesis: str
    primary_metric: str
    direction: str
    baseline: str
    cutoff_contest: int
    dataset_sha256: str
    code_sha256: str
    seed: int = 42
    minimum_effect: float | None = None
    guardrails: tuple[str, ...] = ()
    analysis_plan: str = "compare challenger against declared baseline on protected evaluation data"
    tags: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")
        if not self.hypothesis.strip():
            raise ValueError("hypothesis is required")
        if not self.primary_metric.strip():
            raise ValueError("primary_metric is required")
        if self.direction not in {"maximize", "minimize"}:
            raise ValueError("direction must be 'maximize' or 'minimize'")
        if not self.baseline.strip():
            raise ValueError("baseline is required")
        if self.cutoff_contest < 1:
            raise ValueError("cutoff_contest must be positive")
        for name, digest in (("dataset_sha256", self.dataset_sha256), ("code_sha256", self.code_sha256)):
            if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
                raise ValueError(f"{name} must be a SHA-256 hex digest")
        if self.minimum_effect is not None and not math.isfinite(float(self.minimum_effect)):
            raise ValueError("minimum_effect must be finite")
        if not self.analysis_plan.strip():
            raise ValueError("analysis_plan is required")

    def payload(self) -> dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["tags"] = dict(self.tags)
        data["schema"] = EXPERIMENT_SCHEMA
        return data


class ExperimentRegistry:
    """Persistent local experiment registry with optional MLflow tracking.

    JSON remains the canonical human-auditable record. MLflow is a secondary index
    for search/comparison and never replaces the SMART proof files.
    """

    def __init__(self, root: str | Path, use_mlflow: bool = True) -> None:
        self.root = Path(root)
        self.prereg_dir = self.root / "preregistrations"
        self.result_dir = self.root / "results"
        self.memory_dir = self.root / "memory"
        self.mlflow_dir = self.root / "mlruns"
        for path in (self.prereg_dir, self.result_dir, self.memory_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.use_mlflow = use_mlflow

    def preregister(self, spec: ExperimentSpec) -> dict[str, Any]:
        payload = spec.payload()
        payload["registered_at_utc"] = _utc_now()
        comparable = {k: v for k, v in payload.items() if k != "registered_at_utc"}
        spec_hash = sha256_json(comparable)
        payload["spec_sha256"] = spec_hash
        path = self.prereg_dir / f"{spec.experiment_id}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8-sig"))
            existing_cmp = {k: v for k, v in existing.items() if k not in {"registered_at_utc", "spec_sha256"}}
            if sha256_json(existing_cmp) != spec_hash:
                raise ValueError("experiment_id already exists with a different preregistration")
            return existing
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def load_preregistration(self, experiment_id: str) -> dict[str, Any]:
        path = self.prereg_dir / f"{experiment_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"experiment not preregistered: {experiment_id}")
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def record_result(
        self,
        experiment_id: str,
        metrics: Mapping[str, float],
        decision: str,
        lesson: str,
        guardrail_status: Mapping[str, bool] | None = None,
        artifacts: Sequence[str] = (),
    ) -> dict[str, Any]:
        prereg = self.load_preregistration(experiment_id)
        if prereg["primary_metric"] not in metrics:
            raise ValueError("primary metric missing from result")
        if decision not in {"PROMOTE", "REJECT", "INCONCLUSIVE", "RETAIN_BASELINE"}:
            raise ValueError("unsupported decision")
        numeric_metrics = {str(k): float(v) for k, v in metrics.items()}
        if any(not math.isfinite(v) for v in numeric_metrics.values()):
            raise ValueError("all metrics must be finite")
        guards = {str(k): bool(v) for k, v in (guardrail_status or {}).items()}
        required_guards = set(prereg.get("guardrails", []))
        missing_guards = required_guards.difference(guards)
        if missing_guards:
            raise ValueError(f"missing guardrail results: {sorted(missing_guards)}")
        if decision == "PROMOTE" and any(not guards[g] for g in required_guards):
            raise ValueError("cannot promote with a failed declared guardrail")
        if not lesson.strip():
            raise ValueError("lesson is required for experiment memory")

        payload = {
            "schema": RESULT_SCHEMA,
            "experiment_id": experiment_id,
            "spec_sha256": prereg["spec_sha256"],
            "recorded_at_utc": _utc_now(),
            "metrics": numeric_metrics,
            "guardrail_status": guards,
            "decision": decision,
            "lesson": lesson.strip(),
            "artifacts": list(artifacts),
        }
        payload["result_sha256"] = sha256_json({k: v for k, v in payload.items() if k != "result_sha256"})
        result_path = self.result_dir / f"{experiment_id}.json"
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_memory(prereg, payload)
        if self.use_mlflow:
            self._log_mlflow(prereg, payload)
        return payload

    def _append_memory(self, prereg: Mapping[str, Any], result: Mapping[str, Any]) -> None:
        classification = {
            "PROMOTE": "validated_gain",
            "REJECT": "unsuccessful_direction",
            "RETAIN_BASELINE": "baseline_retained",
            "INCONCLUSIVE": "insufficient_evidence",
        }[result["decision"]]
        entry = {
            "schema": MEMORY_SCHEMA,
            "experiment_id": result["experiment_id"],
            "classification": classification,
            "hypothesis": prereg["hypothesis"],
            "context": {
                "cutoff_contest": prereg["cutoff_contest"],
                "baseline": prereg["baseline"],
                "primary_metric": prereg["primary_metric"],
            },
            "lesson": result["lesson"],
            "evidence": {
                "spec_sha256": prereg["spec_sha256"],
                "result_sha256": result["result_sha256"],
                "metrics": result["metrics"],
            },
            "recorded_at_utc": result["recorded_at_utc"],
        }
        ledger = self.memory_dir / "experiment_memory.jsonl"
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def _log_mlflow(self, prereg: Mapping[str, Any], result: Mapping[str, Any]) -> None:
        try:
            import mlflow
        except ImportError as exc:  # pragma: no cover - environment guard
            raise RuntimeError("MLflow tracking requested but mlflow is not installed") from exc
        self.mlflow_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.root / "mlflow.db"
        tracking_uri = f"sqlite:///{db_path.resolve().as_posix()}"
        mlflow.set_tracking_uri(tracking_uri)
        from mlflow import MlflowClient
        client = MlflowClient(tracking_uri=tracking_uri)
        experiment = client.get_experiment_by_name("SMART-MEGA")
        if experiment is None:
            experiment_id = client.create_experiment(
                "SMART-MEGA", artifact_location=self.mlflow_dir.resolve().as_uri()
            )
        else:
            experiment_id = experiment.experiment_id
        with mlflow.start_run(experiment_id=experiment_id, run_name=result["experiment_id"]):
            mlflow.log_params(
                {
                    "experiment_id": result["experiment_id"],
                    "cutoff_contest": prereg["cutoff_contest"],
                    "baseline": prereg["baseline"],
                    "primary_metric": prereg["primary_metric"],
                    "direction": prereg["direction"],
                    "seed": prereg["seed"],
                    "spec_sha256": prereg["spec_sha256"],
                    "dataset_sha256": prereg["dataset_sha256"],
                    "code_sha256": prereg["code_sha256"],
                }
            )
            mlflow.log_metrics(result["metrics"])
            mlflow.set_tags(
                {
                    "smart.decision": result["decision"],
                    "smart.schema": RESULT_SCHEMA,
                    "smart.result_sha256": result["result_sha256"],
                    **{f"smart.tag.{k}": str(v) for k, v in prereg.get("tags", {}).items()},
                }
            )
            mlflow.log_dict(dict(prereg), "preregistration.json")
            mlflow.log_dict(dict(result), "result.json")


def monte_carlo_null_hits(
    observed_hits: Sequence[int],
    replications: int = 10_000,
    seed: int = 42,
) -> dict[str, Any]:
    """Uniform-lottery null for the total hits of frozen 6-number predictions.

    Under a fair 6/60 draw, the number of overlaps between any fixed six-number
    prediction and the draw follows Hypergeometric(N=60, K=6, n=6). The function
    simulates the total over the same number of contests and reports a one-sided
    Monte Carlo tail probability for observing at least the SMART total.
    """
    hits = np.asarray(list(observed_hits), dtype=int)
    if hits.ndim != 1 or len(hits) == 0:
        raise ValueError("observed_hits must be a non-empty 1D sequence")
    if np.any((hits < 0) | (hits > 6)):
        raise ValueError("hit counts must be between 0 and 6")
    if replications < 1_000:
        raise ValueError("replications must be at least 1000")

    rng = np.random.default_rng(seed)
    totals = np.zeros(replications, dtype=np.int32)
    remaining = len(hits)
    # Batch by contest count to keep memory bounded for long histories.
    batch = 256
    for start in range(0, remaining, batch):
        width = min(batch, remaining - start)
        totals += rng.hypergeometric(6, 54, 6, size=(replications, width)).sum(axis=1)

    observed_total = int(hits.sum())
    exceed = int(np.count_nonzero(totals >= observed_total))
    p_ge = (exceed + 1.0) / (replications + 1.0)
    mcse = math.sqrt(p_ge * (1.0 - p_ge) / (replications + 1.0))
    null_mean = float(totals.mean())
    null_std = float(totals.std(ddof=1))
    z = (observed_total - null_mean) / null_std if null_std > 0 else 0.0

    return {
        "schema": NULL_SCHEMA,
        "contest_count": int(len(hits)),
        "observed_total_hits": observed_total,
        "observed_mean_hits": float(hits.mean()),
        "uniform_expected_total_hits": float(len(hits) * 0.6),
        "replications": int(replications),
        "seed": int(seed),
        "null_mean_total_hits": null_mean,
        "null_std_total_hits": null_std,
        "null_q95": float(np.quantile(totals, 0.95)),
        "null_q99": float(np.quantile(totals, 0.99)),
        "p_null_ge_observed": float(p_ge),
        "p_mcse": float(mcse),
        "z_vs_null": float(z),
        "contract": {
            "null_model": "independent fair 6-of-60 draws",
            "no_future_information": True,
            "tail": "greater_or_equal_total_hits",
        },
    }


__all__ = [
    "ExperimentSpec",
    "ExperimentRegistry",
    "monte_carlo_null_hits",
    "sha256_json",
]

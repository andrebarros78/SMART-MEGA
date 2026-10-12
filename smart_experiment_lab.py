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


    def track_signed_post_result(self, report_file: str | Path, *, expected_report_file_sha256: str) -> dict[str, Any]:
        """Idempotently index an *already adjudicated* SMART result in local MLflow.

        Observational tracking is separate from scientific preregistration and
        predictive authority. Reuses this repository's ExperimentRegistry root
        and local SQLite MLflow backend, never changes canonical report files.
        """
        import re
        from smart_operation_lock import _acquire_os_lock, _release_os_lock
        from mlflow.tracking import MlflowClient

        report_path = Path(report_file)
        if report_path.is_symlink() or not report_path.is_file():
            raise ValueError('post-result MLflow requires a regular signed report')
        report_path = report_path.resolve()
        project_root = self.root.resolve().parent
        if report_path.parent != project_root or not re.fullmatch(r'SMART_POST_RESULT_REPORT_[0-9]+\.json', report_path.name):
            raise ValueError('post-result MLflow report outside canonical root or unexpected name')
        payload_bytes = report_path.read_bytes()
        actual_file_hash = hashlib.sha256(payload_bytes).hexdigest()
        if (not isinstance(expected_report_file_sha256, str)
                or actual_file_hash != expected_report_file_sha256):
            raise ValueError('post-result MLflow signed report file hash mismatch')
        report = json.loads(payload_bytes)
        if not isinstance(report, dict) or report.get('schema') != 'SMART_POST_RESULT_REPORT_1':
            raise ValueError('invalid SMART post-result report schema')
        recorded_hash = report.get('sha256')
        unsigned = dict(report)
        unsigned.pop('sha256', None)
        if recorded_hash != sha256_json(unsigned):
            raise ValueError('post-result MLflow report self-hash mismatch')
        contest = report.get('contest_number')
        if (isinstance(contest, bool) or not isinstance(contest, int) or contest <= 0
                or report_path.name != f'SMART_POST_RESULT_REPORT_{contest}.json'):
            raise ValueError('post-result MLflow report contest invalid')
        audit = report.get('process_audit')
        if (report.get('status') != 'PASS' or not isinstance(audit, dict)
                or audit.get('findings') != []
                or audit.get('freeze_authority_present') is not True):
            raise ValueError('post-result MLflow requires an integrity-clean adjudicated report')
        for name, value in [('source_fingerprint',report.get('source_fingerprint')),
                            ('freeze_sha256',audit.get('freeze_sha256')),
                            ('ledger_sha256',audit.get('ledger_sha256'))]:
            if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
                raise ValueError(f'post-result MLflow missing signed {name}')
        official,card = report.get('official_result'),report.get('generated_card')
        if not all(isinstance(v, list) and len(v)==6 and len(set(v))==6
                   and all(isinstance(n,int) and not isinstance(n,bool) and 1<=n<=60 for n in v)
                   for v in (official,card)):
            raise ValueError('post-result MLflow requires six valid official and frozen card numbers')
        observed_hits = len(set(official) & set(card))
        if observed_hits != report.get('hit_count'):
            raise ValueError('post-result MLflow hits do not reconstruct from immutable card')
        champion_hits = report.get('champion_hits')
        if isinstance(champion_hits, bool) or not isinstance(champion_hits,int) or not 0<=champion_hits<=6:
            raise ValueError('post-result MLflow Champion result invalid')

        metrics = {'primary_hits':float(observed_hits),'champion_hits':float(champion_hits)}
        native = report.get('operational_capability_consumption')
        if isinstance(native,dict) and native.get('status')=='PASS':
            metrics['native_receipt_count']=float(native.get('execution_receipt_count',0))
            proper = native.get('proper_scoring')
            if isinstance(proper,dict):
                for source,target in [('frozen_calibrated_brier','frozen_brier'),('uniform_brier','uniform_brier')]:
                    if source in proper:
                        metrics[target]=float(proper[source])
        structural = report.get('structural_capability_consumption')
        if isinstance(structural,dict) and structural.get('status')=='PASS':
            metrics['structural_receipt_count']=float(structural.get('execution_receipts_count',0))
        if any(not math.isfinite(v) or v<0 for v in metrics.values()):
            raise ValueError('post-result MLflow observation metric invalid')

        # MLflow is a *secondary index* and never grants an experiment promotion.
        tags = {
            'smart.observation_kind':'POST_RESULT_ADJUDICATED',
            'smart.target_contest':str(contest),
            'smart.report_sha256':recorded_hash,
            'smart.report_file_sha256':actual_file_hash,
            'smart.source_fingerprint':report['source_fingerprint'],
            'smart.freeze_sha256':audit['freeze_sha256'],
            'smart.ledger_sha256':audit['ledger_sha256'],
            'smart.scientific_decision':'INCONCLUSIVE',
            'smart.predictive_weight_authorized':'false',
            'smart.freeze_mutation_authorized':'false',
            'smart.not_preregistered_experiment':'true',
        }
        if not self.use_mlflow:
            raise RuntimeError('post-result MLflow consumer requires enabled local tracking')
        self.root.mkdir(parents=True,exist_ok=True)
        self.mlflow_dir.mkdir(parents=True,exist_ok=True)
        lock_file = self.root / '.post_result_mlflow.lock'
        with lock_file.open('a+b') as lock:
            if lock_file.stat().st_size==0:
                lock.write(b'0');lock.flush()
            _acquire_os_lock(lock)
            try:
                db_path=(self.root / 'mlflow.db').resolve()
                client=MlflowClient(tracking_uri=f'sqlite:///{db_path.as_posix()}')
                experiment=client.get_experiment_by_name('SMART-MEGA')
                exp_id=(client.create_experiment('SMART-MEGA',artifact_location=self.mlflow_dir.resolve().as_uri())
                        if experiment is None else experiment.experiment_id)
                existing=client.search_runs([exp_id],filter_string=f"tags.`smart.target_contest` = '{contest}'",max_results=20)
                if len(existing)>1:
                    raise ValueError('duplicate MLflow observations for same contest')
                if existing:
                    run=existing[0]
                    if any(run.data.tags.get(key)!=value for key,value in tags.items()):
                        raise ValueError('conflicting or modified MLflow post-result observation')
                    run_id=run.info.run_id
                    if run.info.status=='FINISHED':
                        if any(key not in run.data.metrics or abs(run.data.metrics[key]-value)>1e-10
                               for key,value in metrics.items()):
                            raise ValueError('persisted MLflow observation metrics changed')
                        status='EXISTING_VALID'
                    elif run.info.status=='RUNNING':
                        status='RECOVERED_PARTIAL'
                    else:
                        raise ValueError('MLflow observation exists with nonrecoverable status')
                else:
                    created=client.create_run(exp_id,tags={**tags,'mlflow.runName':f'SMART-RESULT-{contest}'})
                    run_id=created.info.run_id
                    status='RECORDED'
                if status!='EXISTING_VALID':
                    for key,value in metrics.items():
                        client.log_metric(run_id,key,value)
                    client.set_terminated(run_id,status='FINISHED')
                observed=client.get_run(run_id)
                if observed.info.status!='FINISHED' or any(
                    observed.data.tags.get(key)!=value for key,value in tags.items()
                ) or any(key not in observed.data.metrics or abs(observed.data.metrics[key]-value)>1e-10
                         for key,value in metrics.items()):
                    raise ValueError('MLflow readback did not reproduce verified source evidence')
                receipt = {
                    'schema':'SMART_POST_RESULT_MLFLOW_CONSUMPTION_1',
                    'capability':'mlflow',
                    'native_function_executed':'mlflow.tracking.MlflowClient.create_run/log_metric/get_run',
                    'consumer':'smart_operator.post_result_report_operation_or_mlflow_sync',
                    'third_party_mlflow_library_executed':True,
                    'status':status,
                    'target_contest':contest,
                    'experiment_id':exp_id,
                    'run_id':run_id,
                    'report_sha256':recorded_hash,
                    'report_file_sha256':actual_file_hash,
                    'source_fingerprint':report['source_fingerprint'],
                    'consumed_metrics':metrics,
                    'readback_verified':True,
                    'predictive_weight_authorized':False,
                    'freeze_mutation_authorized':False,
                    'experiment_preregistration_claimed':False,
                }
                receipt['sha256'] = sha256_json(receipt)
                return receipt
            finally:
                _release_os_lock(lock)


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

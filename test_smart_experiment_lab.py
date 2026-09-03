import json

import pytest

from smart_experiment_lab import ExperimentRegistry, ExperimentSpec, monte_carlo_null_hits


HASH_A = "a" * 64
HASH_B = "b" * 64


def _spec(**overrides):
    values = {
        "experiment_id": "exp-001",
        "hypothesis": "challenger improves the declared metric on protected data",
        "primary_metric": "mean_hits",
        "direction": "maximize",
        "baseline": "champion",
        "cutoff_contest": 3052,
        "dataset_sha256": HASH_A,
        "code_sha256": HASH_B,
        "seed": 42,
        "minimum_effect": 0.01,
        "guardrails": ("no_regression_3plus",),
    }
    values.update(overrides)
    return ExperimentSpec(**values)


def test_preregistration_is_idempotent_and_hashed(tmp_path):
    registry = ExperimentRegistry(tmp_path, use_mlflow=False)
    first = registry.preregister(_spec())
    second = registry.preregister(_spec())
    assert first["spec_sha256"] == second["spec_sha256"]
    assert len(first["spec_sha256"]) == 64


def test_preregistration_rejects_same_id_with_changed_hypothesis(tmp_path):
    registry = ExperimentRegistry(tmp_path, use_mlflow=False)
    registry.preregister(_spec())
    with pytest.raises(ValueError):
        registry.preregister(_spec(hypothesis="different hypothesis"))


def test_result_requires_declared_guardrails_and_writes_memory(tmp_path):
    registry = ExperimentRegistry(tmp_path, use_mlflow=False)
    registry.preregister(_spec())
    result = registry.record_result(
        "exp-001",
        metrics={"mean_hits": 0.71},
        guardrail_status={"no_regression_3plus": True},
        decision="PROMOTE",
        lesson="the challenger added measurable value under the declared cutoff",
    )
    assert result["decision"] == "PROMOTE"
    memory = (tmp_path / "memory" / "experiment_memory.jsonl").read_text(encoding="utf-8").strip()
    entry = json.loads(memory)
    assert entry["classification"] == "validated_gain"
    assert entry["evidence"]["result_sha256"] == result["result_sha256"]


def test_promotion_rejected_if_guardrail_failed(tmp_path):
    registry = ExperimentRegistry(tmp_path, use_mlflow=False)
    registry.preregister(_spec())
    with pytest.raises(ValueError):
        registry.record_result(
            "exp-001",
            metrics={"mean_hits": 0.71},
            guardrail_status={"no_regression_3plus": False},
            decision="PROMOTE",
            lesson="should not be accepted",
        )


def test_monte_carlo_null_is_reproducible_and_centered():
    observed = [0, 1, 0, 1, 2] * 20
    first = monte_carlo_null_hits(observed, replications=2000, seed=17)
    second = monte_carlo_null_hits(observed, replications=2000, seed=17)
    assert first == second
    assert abs(first["null_mean_total_hits"] - len(observed) * 0.6) < 1.0
    assert 0.0 < first["p_null_ge_observed"] <= 1.0
    assert first["p_mcse"] >= 0.0


def test_mlflow_local_tracking_is_created(tmp_path):
    registry = ExperimentRegistry(tmp_path, use_mlflow=True)
    registry.preregister(_spec(experiment_id="exp-mlflow"))
    registry.record_result(
        "exp-mlflow",
        metrics={"mean_hits": 0.65},
        guardrail_status={"no_regression_3plus": True},
        decision="RETAIN_BASELINE",
        lesson="baseline remains reference until evidence improves",
    )
    assert registry.mlflow_dir.exists()
    assert any(registry.mlflow_dir.iterdir())

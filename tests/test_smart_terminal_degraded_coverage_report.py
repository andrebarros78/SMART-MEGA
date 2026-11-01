"""Degraded P14 reports cannot act as scientific promotion authority."""
from __future__ import annotations

import hashlib
import json

import pytest

from smart_terminal_stale_coverage import build_degraded_result_audit


def _fixture(tmp_path):
    calls = []
    observations = [{
        "binding_file": "coverage-old.json",
        "historical_source_sha256": "a" * 64,
        "current_source_sha256": "b" * 64,
        "current_source_coverage_proven": False,
    }]
    evidence = {"ledger": tmp_path / "ledger.json", "data": tmp_path / "cutoff.xlsx"}
    paths = [tmp_path / "coverage-old.json"]
    functions = dict(
        target=3080, schema="SMART_INDEPENDENT_AUDIT_V1",
        verified_stale_coverage_observations=lambda root, binding_paths: observations,
        policy_snapshot=lambda: {"fail_closed": True},
        audit_independence=lambda root: {"status": "PASS"},
        audit_prospective_ledger=lambda root, ledger: {"status": "PASS", "pair_count": 1},
        audit_deterministic_replay=lambda root, data, target, start: {
            "status": "PASS", "independent_decision_oracle": {"verified": True},
        },
        load_material_deficiency_registry=lambda root: {"open_deficiencies": []},
        sha256_json=lambda doc: hashlib.sha256(
            json.dumps(doc, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
    )
    def run():
        return build_degraded_result_audit(tmp_path, evidence, paths, **functions)
    return observations, evidence, functions, calls, run


def test_historical_coverage_is_diagnostic_without_promotion(tmp_path):
    observations, evidence, funcs, calls, run = _fixture(tmp_path)
    output = run()
    assert output["status"] == "DEGRADED_P14_COVERAGE_STALE"
    assert output["schema"] == "SMART_INDEPENDENT_AUDIT_V1"
    assert output["scientific_coverage_certified"] is False
    assert output["terminal_promotion_permitted"] is False
    assert output["promotion_authority"] is False
    assert output["coverage"]["status"] == "BLOCKED_STALE_SOURCE_HASH"
    assert output["historical_coverage_source_bindings"] is observations
    assert output["checks"]["coverage_lines_and_branches"] is False
    assert output["checks"]["hash_integrity"] is False
    assert output["checks"]["independent_freeze_decision_oracle"] is True
    digest = output.pop("sha256")
    assert digest == funcs["sha256_json"](output)
    assert not list(tmp_path.iterdir())


def test_independent_replay_without_decision_oracle_is_not_reported_as_verified(tmp_path):
    observations, evidence, funcs, calls, run = _fixture(tmp_path)
    funcs["audit_deterministic_replay"] = lambda *args, **kwargs: {"status": "PASS"}
    output = run()
    assert output["checks"]["independent_freeze_decision_oracle"] is False
    assert output["terminal_promotion_permitted"] is False


def test_open_material_deficiencies_are_not_suppressed(tmp_path):
    observations, evidence, funcs, calls, run = _fixture(tmp_path)
    funcs["load_material_deficiency_registry"] = lambda root: {
        "open_deficiencies": [{"code": "P14_COVERAGE_STALE", "severity": "P0"}]
    }
    output = run()
    assert output["material_deficiencies"] == [
        {"code": "P14_COVERAGE_STALE", "severity": "P0"}]
    assert output["terminal_promotion_permitted"] is False


@pytest.mark.parametrize("failed_dependency", [
    "verified_stale_coverage_observations",
    "policy_snapshot",
    "audit_independence",
    "audit_prospective_ledger",
    "audit_deterministic_replay",
    "load_material_deficiency_registry",
])
def test_failed_independent_audit_dependency_remains_fatal(tmp_path, failed_dependency):
    observations, evidence, funcs, calls, run = _fixture(tmp_path)
    def fail(*args, **kwargs):
        raise ValueError("independent evidence invalid")
    funcs[failed_dependency] = fail
    with pytest.raises(ValueError, match="independent evidence invalid"):
        run()


def test_deficiency_registry_without_open_deficiencies_fails_closed(tmp_path):
    observations, evidence, funcs, calls, run = _fixture(tmp_path)
    funcs["load_material_deficiency_registry"] = lambda root: {"status": "PASS"}
    with pytest.raises(KeyError, match="open_deficiencies"):
        run()
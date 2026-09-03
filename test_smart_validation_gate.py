import pytest

from smart_validation_gate import enforce_evidence_bundle, validate_evidence_bundle


def _valid_bundle():
    return {
        "preregistered": True,
        "spec_sha256": "a" * 64,
        "dataset_sha256": "b" * 64,
        "code_sha256": "c" * 64,
        "data_quality_status": "PASS",
        "cutoff_respected": True,
        "no_future_information": True,
        "baseline": "champion",
        "primary_metric": "mean_hits",
        "metrics": {"mean_hits": 0.7},
        "guardrail_status": {"no_regression_3plus": True},
        "canonical_tests_status": "PASS",
        "non_regression_status": "PASS",
        "decision": "PROMOTE",
    }


def test_valid_bundle_allows_promotion():
    result = enforce_evidence_bundle(_valid_bundle())
    assert result.status == "PASS"
    assert result.promotion_allowed is True
    assert result.failed_checks == ()


def test_future_information_blocks_promotion():
    bundle = _valid_bundle()
    bundle["no_future_information"] = False
    result = validate_evidence_bundle(bundle)
    assert result.status == "FAIL"
    assert result.promotion_allowed is False
    assert "no_future_information" in result.failed_checks


def test_failed_guardrail_blocks_promotion():
    bundle = _valid_bundle()
    bundle["guardrail_status"] = {"no_regression_3plus": False}
    with pytest.raises(ValueError):
        enforce_evidence_bundle(bundle)


def test_missing_primary_metric_blocks_promotion():
    bundle = _valid_bundle()
    bundle["metrics"] = {"other": 1.0}
    result = validate_evidence_bundle(bundle)
    assert "primary_metric_present" in result.failed_checks

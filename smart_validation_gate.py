from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

VALIDATION_SCHEMA = "SMART_EVIDENCE_VALIDATION_GATE_V1"


@dataclass(frozen=True)
class EvidenceValidation:
    schema: str
    status: str
    checks: dict[str, bool]
    failed_checks: tuple[str, ...]
    promotion_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_evidence_bundle(bundle: Mapping[str, Any]) -> EvidenceValidation:
    """Validate a SMART experiment/proof bundle before promotion.

    The gate is intentionally structural: it checks that the evidence contract was
    satisfied. It does not manufacture missing evidence or reinterpret metrics.
    """
    guards = bundle.get("guardrail_status")
    guards_ok = isinstance(guards, Mapping) and bool(guards) and all(bool(v) for v in guards.values())
    metrics = bundle.get("metrics")
    primary_metric = bundle.get("primary_metric")
    primary_metric_present = isinstance(metrics, Mapping) and bool(primary_metric) and primary_metric in metrics

    checks = {
        "preregistered": bool(bundle.get("preregistered")),
        "spec_hash_bound": isinstance(bundle.get("spec_sha256"), str) and len(bundle.get("spec_sha256", "")) == 64,
        "dataset_hash_bound": isinstance(bundle.get("dataset_sha256"), str) and len(bundle.get("dataset_sha256", "")) == 64,
        "code_hash_bound": isinstance(bundle.get("code_sha256"), str) and len(bundle.get("code_sha256", "")) == 64,
        "data_quality_pass": bundle.get("data_quality_status") == "PASS",
        "cutoff_respected": bundle.get("cutoff_respected") is True,
        "no_future_information": bundle.get("no_future_information") is True,
        "baseline_declared": bool(bundle.get("baseline")),
        "primary_metric_present": primary_metric_present,
        "guardrails_pass": guards_ok,
        "canonical_tests_pass": bundle.get("canonical_tests_status") == "PASS",
        "non_regression_pass": bundle.get("non_regression_status") == "PASS",
    }
    failed = tuple(name for name, passed in checks.items() if not passed)
    status = "PASS" if not failed else "FAIL"
    requested_decision = str(bundle.get("decision", "")).upper()
    promotion_allowed = status == "PASS" and requested_decision == "PROMOTE"
    return EvidenceValidation(
        schema=VALIDATION_SCHEMA,
        status=status,
        checks=checks,
        failed_checks=failed,
        promotion_allowed=promotion_allowed,
    )


def enforce_evidence_bundle(bundle: Mapping[str, Any]) -> EvidenceValidation:
    validation = validate_evidence_bundle(bundle)
    if validation.status != "PASS":
        raise ValueError(f"evidence validation failed: {list(validation.failed_checks)}")
    return validation


__all__ = ["EvidenceValidation", "validate_evidence_bundle", "enforce_evidence_bundle"]

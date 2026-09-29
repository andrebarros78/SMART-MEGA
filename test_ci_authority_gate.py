from __future__ import annotations

from copy import deepcopy

from smart_ci_authority_gate import _sha_json, binding_checks


def _seal(doc: dict) -> dict:
    sealed = deepcopy(doc)
    sealed.pop("sha256", None)
    sealed["sha256"] = _sha_json(sealed)
    return sealed


def _fixture() -> tuple[dict, dict, dict, dict, dict, list[dict]]:
    live = {"tests": 100, "failures": 0, "errors": 0, "skipped": 0, "status": "PASS"}
    fingerprint = {"file_count": 2, "files": [{"path": "a.py", "sha256": "a"}, {"path": "b.py", "sha256": "b"}], "sha256": "fp-current"}
    manifest = [{"path": "a.py", "sha256": "a"}, {"path": "b.py", "sha256": "b"}]

    certification = _seal(
        {
            "schema": "SMART_PRODUCT_CERTIFICATION_V1",
            "status": "CONSTRUCTION_PROVEN",
            "checks": {"construction": True},
            "code_fingerprint": deepcopy(fingerprint),
            "critical_code_manifest": deepcopy(manifest),
            "regression": deepcopy(live),
            "canonical_root_authority": deepcopy(live),
        }
    )
    canonical = _seal(
        {
            "schema": "SMART_CANONICAL_ROOT_V1",
            "project": "SMART-MEGA",
            "canonical_state": "CANONICAL_ONLY",
            "legacy_alias_present": False,
            "certified_regression_tests": 100,
            "certified_regression_failures": 0,
            "certified_regression_errors": 0,
            "certified_regression_skipped": 0,
            "certified_regression": deepcopy(live),
        }
    )
    governance = _seal(
        {
            "status": "PASS",
            "checks": {"governance": True},
            "critical_code_manifest": deepcopy(manifest),
        }
    )
    return certification, canonical, governance, live, fingerprint, manifest


def _checks(certification: dict, canonical: dict, governance: dict, live: dict, fingerprint: dict, manifest: list[dict]) -> dict[str, bool]:
    return binding_checks(
        certification=certification,
        canonical_root=canonical,
        governance=governance,
        live_regression=live,
        current_code_fingerprint=fingerprint,
        current_critical_manifest=manifest,
    )


def test_coherent_authority_snapshot_passes() -> None:
    certification, canonical, governance, live, fingerprint, manifest = _fixture()
    checks = _checks(certification, canonical, governance, live, fingerprint, manifest)
    assert checks
    assert all(checks.values())


def test_stale_product_fingerprint_cannot_false_green() -> None:
    certification, canonical, governance, live, fingerprint, manifest = _fixture()
    certification["code_fingerprint"] = {**fingerprint, "sha256": "fp-stale"}
    certification = _seal(certification)
    checks = _checks(certification, canonical, governance, live, fingerprint, manifest)
    assert checks["product_certification_self_hash_valid"] is True
    assert checks["product_certification_code_fingerprint_current"] is False
    assert not all(checks.values())


def test_stale_canonical_regression_count_cannot_false_green() -> None:
    certification, canonical, governance, live, fingerprint, manifest = _fixture()
    canonical["certified_regression_tests"] = 99
    canonical["certified_regression"]["tests"] = 99
    canonical = _seal(canonical)
    checks = _checks(certification, canonical, governance, live, fingerprint, manifest)
    assert checks["canonical_root_self_hash_valid"] is True
    assert checks["canonical_root_regression_counts_current"] is False
    assert checks["canonical_root_nested_regression_counts_current"] is False
    assert not all(checks.values())

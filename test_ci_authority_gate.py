from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from smart_ci_authority_gate import _sha_json, binding_checks, junit_summary


def _seal(doc: dict) -> dict:
    sealed = deepcopy(doc)
    sealed.pop("sha256", None)
    sealed["sha256"] = _sha_json(sealed)
    return sealed


def _fixture() -> tuple[dict, dict, dict, dict, dict, dict]:
    live = {"tests": 100, "failures": 0, "errors": 0, "skipped": 0, "status": "PASS"}
    fingerprint = {
        "file_count": 2,
        "files": [{"path": "a.py", "sha256": "a"}, {"path": "b.py", "sha256": "b"}],
        "sha256": "fp-current",
    }
    manifest = {
        "schema": "SMART_CRITICAL_CODE_MANIFEST_1",
        "file_count": 2,
        "files": {"a.py": "a", "b.py": "b"},
        "fingerprint_sha256": "manifest-current",
    }

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


def _checks(
    certification: dict,
    canonical: dict,
    governance: dict,
    live: dict,
    fingerprint: dict,
    manifest: dict,
) -> dict[str, bool]:
    return binding_checks(
        certification=certification,
        canonical_root=canonical,
        governance=governance,
        live_regression=live,
        current_code_fingerprint=fingerprint,
        current_critical_manifest=manifest,
    )


class AuthorityFreshnessGateTests(unittest.TestCase):
    def test_coherent_authority_snapshot_passes(self) -> None:
        certification, canonical, governance, live, fingerprint, manifest = _fixture()
        checks = _checks(certification, canonical, governance, live, fingerprint, manifest)
        self.assertTrue(checks)
        self.assertTrue(all(checks.values()))

    def test_stale_product_fingerprint_cannot_false_green(self) -> None:
        certification, canonical, governance, live, fingerprint, manifest = _fixture()
        certification["code_fingerprint"] = {**fingerprint, "sha256": "fp-stale"}
        certification = _seal(certification)
        checks = _checks(certification, canonical, governance, live, fingerprint, manifest)
        self.assertTrue(checks["product_certification_self_hash_valid"])
        self.assertFalse(checks["product_certification_code_fingerprint_current"])
        self.assertFalse(all(checks.values()))

    def test_stale_canonical_regression_count_cannot_false_green(self) -> None:
        certification, canonical, governance, live, fingerprint, manifest = _fixture()
        canonical["certified_regression_tests"] = 99
        canonical["certified_regression"]["tests"] = 99
        canonical = _seal(canonical)
        checks = _checks(certification, canonical, governance, live, fingerprint, manifest)
        self.assertTrue(checks["canonical_root_self_hash_valid"])
        self.assertFalse(checks["canonical_root_regression_counts_current"])
        self.assertFalse(checks["canonical_root_nested_regression_counts_current"])
        self.assertFalse(all(checks.values()))

    def test_junit_parser_accepts_local_green_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "junit.xml"
            path.write_text(
                '<testsuites tests="3" failures="0" errors="0" skipped="1"><testsuite tests="3" failures="0" errors="0" skipped="1"/></testsuites>',
                encoding="utf-8",
            )
            summary = junit_summary(path)
            self.assertEqual(summary["tests"], 3)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["status"], "PASS")

    def test_junit_parser_rejects_doctype(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "junit.xml"
            path.write_text(
                '<!DOCTYPE testsuites [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><testsuites tests="1" failures="0" errors="0" skipped="0"/>',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                junit_summary(path)


if __name__ == "__main__":
    unittest.main()

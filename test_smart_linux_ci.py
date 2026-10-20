"""Contract tests for GitHub-Actions-independent SMART regression execution."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import smart_linux_ci as ci


class LinuxCIContract(unittest.TestCase):
    def test_missing_dependency_is_explicit_block_not_pass(self):
        missing = ci.missing_packages({"pytest": "9.1.1"}, installed=lambda _: None)
        self.assertEqual(missing, ["pytest==9.1.1"])

    def test_dependency_version_mismatch_is_rejected(self):
        self.assertEqual(ci.missing_packages({"pytest": "9.1.1"}, installed=lambda _: "9.1.0"),
                         ["pytest==9.1.1"])

    def test_matching_dependency_version_is_accepted(self):
        self.assertEqual(ci.missing_packages({"pytest": "9.1.1"}, installed=lambda _: "9.1.1"), [])

    def test_receipt_is_self_hashed_and_rejects_mutation(self):
        doc = {"schema": ci.SCHEMA, "profile": "focused", "status": "PASS", "test_count": 42}
        signed = ci.sign_receipt(doc)
        self.assertTrue(ci.verify_receipt(signed))
        signed["test_count"] = 99
        self.assertFalse(ci.verify_receipt(signed))

    def test_focused_passes_only_with_real_unittest_count(self):
        result = ci.interpret_focused(0, "Ran 42 tests in 0.6s\n\nOK\n", min_tests=42)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["test_count"], 42)
        self.assertEqual(ci.interpret_focused(0, "Ran 41 tests in 0.6s\n\nOK\n", min_tests=42)["status"], "FAIL")
        self.assertEqual(ci.interpret_focused(1, "Ran 42 tests\nFAILED\n", min_tests=42)["status"], "FAIL")

    def test_full_profile_cannot_pass_without_all_locked_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "requirements.lock.txt").write_text("pytest==9.1.1\npandas==3.0.5\n")
            check = ci.check_full_dependencies(Path(d), installed=lambda _: None)
            self.assertEqual(check["status"], "BLOCKED_DEPENDENCIES")
            self.assertEqual(check["missing"], ["pandas==3.0.5", "pytest==9.1.1"])

    def test_invalid_requirement_line_does_not_get_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "requirements.lock.txt").write_text("pytest>=9.0\n")
            with self.assertRaisesRegex(ValueError, "not pinned"):
                ci.read_lock(Path(d) / "requirements.lock.txt")

    def test_output_receipt_creates_no_false_full_certification(self):
        with tempfile.TemporaryDirectory() as d:
            receipt = ci.sign_receipt({"schema": ci.SCHEMA, "profile": "full", "status": "BLOCKED_DEPENDENCIES",
                                       "test_count": 0, "scientific_6of6_proven": False})
            path = ci.write_receipt(Path(d), receipt)
            self.assertTrue(ci.verify_receipt(json.loads(path.read_text())))
            self.assertEqual(json.loads(path.read_text())["status"], "BLOCKED_DEPENDENCIES")


    def test_certification_is_only_supported_with_full_profile(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "requires full"):
                ci.execute(Path(d), "focused", certify=True)

    def test_missing_dependencies_never_attempt_linux_certification(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root.parent / (root.name + "-evidence")
            with patch.object(ci, "_verified_identity", return_value={
                "source_commit": "a" * 40,
                "source_origin": "https://github.com/andrebarros78/SMART-MEGA.git",
                "checkout_clean": True
            }), patch.object(ci, "check_full_dependencies", return_value={
                "status": "BLOCKED_DEPENDENCIES", "missing": ["pytest==9.1.1"],
                "expected_count": 1, "installed_count": 0
            }), patch("subprocess.run", side_effect=AssertionError("No subprocess allowed")):
                result = ci.execute(root, "full", certify=True, evidence_dir=folder)
            self.assertEqual(result["status"], "BLOCKED_DEPENDENCIES")
            self.assertFalse(result["full_regression_proven"])
            proof = json.loads(Path(result["receipt"]).read_text())
            self.assertFalse(proof["certification_proven"])
            self.assertTrue(proof["certification_requested"])


    def test_forged_success_stdout_without_real_junit_is_not_full_proof(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            artifacts = root.parent / (root.name + "-evidence")
            fake = {
                "status": "PASS", "promoted": True,
                "candidate": {"tests": 1295, "status": "PASS",
                              "sha256": "a" * 64},
                "promotion": {"sha256": "a" * 64},
            }
            proc = SimpleNamespace(returncode=0, stdout=json.dumps(fake) + "\n", stderr="")
            with patch.object(ci, "_verified_identity", return_value={
                "source_commit": "a" * 40,
                "source_origin": "https://github.com/andrebarros78/SMART-MEGA.git",
                "checkout_clean": True
            }), patch.object(ci, "check_full_dependencies", return_value={
                "status": "PASS", "missing": [], "expected_count": 75, "installed_count": 75,
            }), patch("subprocess.run", return_value=proc):
                outcome = ci.execute(root, "full", evidence_dir=artifacts)
            self.assertEqual(outcome["status"], "FAIL")
            self.assertFalse(outcome["full_regression_proven"])

    def test_malformed_runner_output_returns_fail_receipt_not_uncaught_exception(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            artifacts = root.parent / (root.name + "-evidence")
            proc = SimpleNamespace(returncode=1, stdout="broken-json", stderr="runner failed")
            with patch.object(ci, "_verified_identity", return_value={
                "source_commit": "b" * 40,
                "source_origin": "https://github.com/andrebarros78/SMART-MEGA.git",
                "checkout_clean": True
            }), patch.object(ci, "check_full_dependencies", return_value={
                "status": "PASS", "missing": [], "expected_count": 75, "installed_count": 75,
            }), patch("subprocess.run", return_value=proc):
                outcome = ci.execute(root, "full", evidence_dir=artifacts)
            self.assertEqual(outcome["status"], "FAIL")
            self.assertFalse(outcome["full_regression_proven"])


    def test_full_junit_requires_matching_candidate_current_and_runner_controls(self):
        import hashlib
        import sys
        from types import SimpleNamespace
        from xml.etree import ElementTree as ET
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            xml = b'<testsuites tests="2" failures="0" errors="0" skipped="0"><testsuite tests="2" failures="0" errors="0" skipped="0"/></testsuites>'
            (root / "SMART_AUDIT_JUNIT_CANDIDATE.xml").write_bytes(xml)
            (root / "SMART_AUDIT_JUNIT_CURRENT.xml").write_bytes(xml)
            digest = hashlib.sha256(xml).hexdigest()
            def parsed(path):
                tree = ET.parse(path).getroot()
                return dict(status="PASS", tests=int(tree.get("tests")),
                            errors=int(tree.get("errors")), failures=int(tree.get("failures")),
                            skipped=int(tree.get("skipped")),
                            sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
            report = {"status": "PASS", "promoted": True,
                      "code_fingerprint_stable": True,
                      "canonical_environment_stable": True,
                      "isolated_python_environment": True,
                      "exclusive_runner_lock": True,
                      "current_preserved_during_test": True,
                      "candidate": {"tests": 2, "sha256": digest},
                      "promotion": {"sha256": digest},
                      "current_sha256": digest}
            with patch.dict(sys.modules, {"smart_regression_evidence": SimpleNamespace(junit_summary=parsed)}):
                self.assertTrue(ci.verify_full_junit(root, report))
                report["code_fingerprint_stable"] = False
                self.assertFalse(ci.verify_full_junit(root, report))
                report["code_fingerprint_stable"] = True
                (root / "SMART_AUDIT_JUNIT_CURRENT.xml").write_bytes(b'<testsuite tests="1" failures="0" errors="0"/>')
                self.assertFalse(ci.verify_full_junit(root, report))

    def test_invalid_candidate_metadata_returns_false(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = {"status": "PASS", "promoted": True,
                      "code_fingerprint_stable": True,
                      "canonical_environment_stable": True,
                      "isolated_python_environment": True,
                      "exclusive_runner_lock": True,
                      "current_preserved_during_test": True,
                      "candidate": "invalid", "promotion": {}}
            self.assertFalse(ci.verify_full_junit(root, report))


if __name__ == "__main__":
    unittest.main()

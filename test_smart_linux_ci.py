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


if __name__ == "__main__":
    unittest.main()

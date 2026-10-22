"""Regression checks for post-result operational/scientific separation.

No third-party dependencies required; also discovered by pytest.
"""
from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from smart_scoped_history_gate import inspect_freeze_evidence


def _freeze(target, name, sha):
    return {"event_type": "FREEZE", "target_contest": target,
            "freeze_file": name, "freeze_sha256": sha}


def _adjudication(target):
    return {"event_type": "ADJUDICATION", "target_contest": target}


def _actual_verifier(root, path, expected_sha, label):
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        raise ValueError(f"{label} file unavailable")
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_sha:
        raise ValueError(f"{label} SHA-256 mismatch")
    return candidate


class TestScopedHistoricalFreezeGate(unittest.TestCase):
    def test_missing_historical_evidence_is_not_promoted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "current.json"
            current.write_bytes(b"immutable original freeze")
            sha = hashlib.sha256(current.read_bytes()).hexdigest()
            ledger = {"events": [
                _freeze(3060, "missing-3060.json", "a" * 64),
                _adjudication(3060),
                _freeze(3061, "missing-3061.json", "b" * 64),
                _adjudication(3061),
                _freeze(3071, "current.json", sha),
            ]}
            before = json.dumps(ledger, sort_keys=True)
            status = inspect_freeze_evidence(root, ledger, 3071, _actual_verifier, current_sha256=sha)
            self.assertEqual(status["unverified_contests"], [3060, 3061])
            self.assertFalse(status["promotion_authority"])
            self.assertFalse(status["scientific_audit_substituted"])
            self.assertFalse(status["historical_verified"])
            self.assertTrue(status["active_freeze_verified"])
            self.assertEqual(json.dumps(ledger, sort_keys=True), before)

    def test_current_freeze_missing_fails_closed(self):
        with TemporaryDirectory() as tmp:
            ledger = {"events": [_freeze(3071, "not-here.json", "c" * 64)]}
            with self.assertRaisesRegex(ValueError, "current active freeze evidence unavailable"):
                inspect_freeze_evidence(Path(tmp), ledger, 3071, _actual_verifier)

    def test_current_freeze_tampering_fails_closed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "active.json").write_bytes(b"tampered")
            ledger = {"events": [_freeze(3071, "active.json", hashlib.sha256(b"authentic").hexdigest())]}
            with self.assertRaisesRegex(ValueError, "current active freeze evidence unavailable"):
                inspect_freeze_evidence(root, ledger, 3071, _actual_verifier)

    def test_duplicate_active_hash_event_fails_closed(self):
        with TemporaryDirectory() as tmp:
            freeze = _freeze(3071, "same.json", "a" * 64)
            ledger = {"events": [freeze, dict(freeze)]}
            with self.assertRaisesRegex(ValueError, "exactly one"):
                inspect_freeze_evidence(Path(tmp), ledger, 3071, lambda *args: None, current_sha256="a" * 64)

    def test_clean_scoped_history_still_grants_no_scientific_authority(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "current.json").write_bytes(b"freeze")
            sha = hashlib.sha256(b"freeze").hexdigest()
            ledger = {"events": [_freeze(3071, "current.json", sha)]}
            result = inspect_freeze_evidence(root, ledger, 3071, _actual_verifier, current_sha256=sha)
            self.assertEqual(result["status"], "PASS_SCOPED_FREEZE_EVIDENCE")
            self.assertFalse(result["promotion_authority"])
            self.assertEqual(result["unverified_contests"], [])

    def test_existing_historical_wrong_hash_remains_unverified(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "older.json").write_bytes(b"different")
            (root / "current.json").write_bytes(b"freeze")
            current_sha = hashlib.sha256(b"freeze").hexdigest()
            ledger = {"events": [_freeze(3061, "older.json", "a" * 64),
                                 _adjudication(3061),
                                 _freeze(3071, "current.json", current_sha)]}
            result = inspect_freeze_evidence(root, ledger, 3071, _actual_verifier, current_sha256=current_sha)
            self.assertEqual(result["unverified_contests"], [3061])
            self.assertFalse(result["promotion_authority"])

    def test_engine_wires_degraded_audit_after_learning_and_before_history_advance(self):
        source = Path(__file__).resolve().with_name("smart_terminal_engine.py").read_text(encoding="utf-8")
        functions = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
        self.assertIn("_unverified_history_audit", functions)
        self.assertIn("_precheck_historical_freeze_evidence", functions)
        execute_source = ast.get_source_segment(source, functions["execute"])
        self.assertIn('allow_unverified_history=binding.get("mode")', execute_source)
        self.assertIn("_unverified_history_audit(root, scoped)", execute_source)
        self.assertIn("_ensure_learning_and_sequence(root, binding=binding)", execute_source)
        self.assertIn("history_advance.advance_completed_epoch", execute_source)
        self.assertLess(execute_source.index("_ensure_learning_and_sequence"),
                        execute_source.index("_unverified_history_audit"))
        self.assertLess(execute_source.index("_unverified_history_audit"),
                        execute_source.index("history_advance.advance_completed_epoch"))
        degraded_source = ast.get_source_segment(source, functions["_unverified_history_audit"])
        self.assertIn('"promotion_authority": False', degraded_source)
        self.assertIn('"independent_full_audit_completed": False', degraded_source)
        self.assertIn('"terminal_promotion_permitted": False', degraded_source)


if __name__ == "__main__":
    unittest.main()

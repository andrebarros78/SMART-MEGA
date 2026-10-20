"""Regression: incomplete scientific audit must not crash result settlement."""
from __future__ import annotations
import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


class TestTerminalIncompleteAuditExecution(unittest.TestCase):
    def check(self, pair_count):
        root = Path(self.tmp.name)
        frozen = {"frozen_before_result": True, "cutoff_contest": 3070,
                  "champion": {"top6": [1, 2, 3, 4, 5, 6]},
                  "champion_remains_active": True, "production_switch_performed": False}
        path = root / "frozen.json"
        path.write_text(json.dumps(frozen), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ledger = {"events": [
            {"event_type": "FREEZE", "target_contest": 3071,
             "freeze_file": "frozen.json", "freeze_sha256": digest,
             "frozen_before_result": True, "cutoff_contest": 3070},
            {"event_type": "ADJUDICATION", "target_contest": 3071,
             "freeze_sha256": digest, "actual_numbers": [1, 2, 3, 7, 8, 9],
             "champion_hits": 3, "retroactive_rewrite": False},
        ]}
        source = Path(__file__).resolve().with_name("smart_terminal_engine.py").read_text(encoding="utf-8")
        fn = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef)
                  and x.name == "evaluate_terminal_rule")
        variables = dict(Path=Path, Any=Any, TARGET=3071, CUTOFF=3070,
                         champion_challenger=SimpleNamespace(active_freeze=lambda _ledger, _target: ledger["events"][0]),
                         sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                         _read_json=lambda p: json.loads(Path(p).read_text(encoding="utf-8")),
                         _target_events=lambda obj, kind: [e for e in obj["events"] if e["event_type"] == kind])
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<real-terminal-evaluator>", "exec"), variables)
        return variables["evaluate_terminal_rule"](
            root, ledger,
            {"primary": {"validated": True, "numbers": [1, 2, 3, 7, 8, 9]},
             "terminal_source_corroboration_authorized": False},
            {"status": "DEGRADED_HISTORICAL_EVIDENCE_MISSING",
             "prospective_ledger": {"status": "NOT_PROVEN_HISTORICAL_EVIDENCE_MISSING",
                                   "pair_count": pair_count, "no_future_leakage": False}},
            {"valid": True, "proof_recorded": True},
            binding={"freeze_sha256": digest, "freeze": path, "mode": "ACTIVE_EPOCH"},
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_null_pair_count_must_be_nonpromoting_not_an_exception(self):
        evaluated = self.check(None)
        self.assertFalse(evaluated["checks"]["all_attempts_counted"])
        self.assertFalse(evaluated["eligible_for_mission_proven"])
        self.assertEqual(evaluated["recomputed_hits"], 3)

    def test_bool_pair_count_must_not_count_as_one(self):
        self.assertFalse(self.check(True)["checks"]["all_attempts_counted"])

    def test_numeric_string_pair_count_must_be_rejected(self):
        self.assertFalse(self.check("1")["checks"]["all_attempts_counted"])

    def test_integer_pair_count_matches_without_suppressing_other_science_gates(self):
        result = self.check(1)
        self.assertTrue(result["checks"]["all_attempts_counted"])
        self.assertFalse(result["eligible_for_mission_proven"])


if __name__ == "__main__":
    unittest.main()

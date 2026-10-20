"""Unit evidence for fail-closed restart of terminal commit before lifecycle transition."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from smart_frozen_terminal_recovery import verified_frozen_terminal_recovery


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class TestFrozenTerminalRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.joinpath("epoch").mkdir()
        (self.root / "freeze.json").write_bytes(b"frozen-before-draw")
        (self.root / "epoch" / "ledger.json").write_bytes(b"ledger")
        (self.root / "epoch" / "Mega-Sena_through_3071.xlsx").write_bytes(
            b"draw-3071-with-causal-prefix"
        )
        (self.root / "Mega-Sena.xlsx").write_bytes(b"draw-3071-with-causal-prefix")
        self.lifecycle = {"state": "FROZEN", "target_contest": 3071}
        self.active = {
            "status": "FROZEN",
            "target_contest": 3071,
            "cutoff_contest": 3070,
            "result_used": False,
            "freeze_authority": {
                "file": "freeze.json", "target_contest": 3071,
                "cutoff_contest": 3070, "sha256": sha(b"frozen-before-draw"),
            },
            "state_paths": {"ledger": "epoch/ledger.json"},
        }
        self.ledger = {
            "events": [{
                "event_type": "ADJUDICATION",
                "target_contest": 3071,
                "result_data_sha256": sha(b"draw-3071-with-causal-prefix"),
                "actual_numbers": [12, 22, 41, 45, 51, 52],
            }],
        }
        self.sequence = {
            "valid": True,
            "adjudicated": True,
            "proof_recorded": True,
            "active_freeze_sha256": sha(b"frozen-before-draw"),
            "sequence_sha256": sha(b"sequence"),
        }

    def check(self):
        return verified_frozen_terminal_recovery(
            self.root, self.lifecycle, self.active,
            load_ledger=lambda path: self.ledger,
            validate_sequence=lambda *args, **kw: self.sequence,
        )

    def test_verified_interrupted_commit_is_recoverable(self):
        self.assertTrue(self.check())

    def test_incomplete_history_not_recoverable(self):
        (self.root / "Mega-Sena.xlsx").write_bytes(b"cutoff-3070")
        self.assertFalse(self.check())

    def test_tampered_current_freeze_not_recoverable(self):
        (self.root / "freeze.json").write_bytes(b"after-the-fact")
        self.assertFalse(self.check())

    def test_missing_sequential_proof_not_recoverable(self):
        self.sequence["proof_recorded"] = False
        self.assertFalse(self.check())

    def test_wrong_result_data_sha_not_recoverable(self):
        self.ledger["events"][0]["result_data_sha256"] = sha(b"unrelated")
        self.assertFalse(self.check())

    def test_wrong_target_or_lifecycle_state_not_recoverable(self):
        self.lifecycle["target_contest"] = 3072
        self.assertFalse(self.check())
        self.lifecycle["target_contest"] = 3071
        self.lifecycle["state"] = "PREPARED"
        self.assertFalse(self.check())

    def test_signed_advance_receipt_is_checked(self):
        doc = {
            "schema": "SMART_CANONICAL_HISTORY_ADVANCE_1",
            "status": "PASS",
            "target_contest": 3071,
            "sequence_sha256": self.sequence["sequence_sha256"],
            "retroactive_rewrite": False,
            "ready_for_next_target": 3072,
            "canonical_sha256_after": sha(b"draw-3071-with-causal-prefix"),
            "through_sha256": sha(b"draw-3071-with-causal-prefix"),
        }
        doc["sha256"] = hashlib.sha256(json.dumps(
            doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        receipt = self.root / "SMART_CANONICAL_HISTORY_ADVANCE_3071.json"
        receipt.write_text(json.dumps(doc))
        self.assertTrue(self.check())
        doc["ready_for_next_target"] = 9999
        receipt.write_text(json.dumps(doc))
        self.assertFalse(self.check())

    def test_out_of_root_ledger_is_rejected(self):
        self.active["state_paths"]["ledger"] = "../../elsewhere.json"
        self.assertFalse(self.check())

    def test_startup_reconciler_invokes_proof_bound_recovery_only_for_frozen(self):
        import ast
        source = Path(__file__).resolve().with_name(
            "smart_startup_reconciler.py"
        ).read_text(encoding="utf-8")
        function = next(
            node for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "reconcile"
        )
        block = ast.get_source_segment(source, function)
        self.assertIn('elif state == "FROZEN":', block)
        self.assertIn(
            "verified_frozen_terminal_recovery(root, lifecycle, active)", block,
        )
        self.assertIn("dataset_max == int(life_target)", block)
        self.assertIn('"scientific_promotion_authorized": False', block)


if __name__ == "__main__":
    unittest.main()

"""Single-command result settlement: safe, restartable, no scientific promotion."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from typing import Any


def _operator_function():
    source = Path(__file__).resolve().with_name("smart_operator.py").read_text()
    node = next(
        item for item in ast.parse(source).body
        if isinstance(item, ast.FunctionDef) and item.name == "complete_result_operation"
    )
    namespace = {"Path": Path, "Any": Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(Path(__file__).resolve().with_name("smart_operator.py")), "exec"), namespace)
    return namespace["complete_result_operation"], namespace


class TestCompleteResultOperation(unittest.TestCase):
    def test_frozen_result_is_completed_without_scientific_promotion(self):
        operation, env = _operator_function()
        state = {"state": "FROZEN", "target_contest": 3071}
        calls = []

        def terminal(root, target, *, allow_terminal_write):
            calls.append(("terminal", target, allow_terminal_write))
            state["state"] = "ADJUDICATED"
            return {"adjudication_status": "ADJUDICATED", "sequence_valid": True}

        def report(root, target):
            calls.append(("report", target))
            return {"status": "POST_RESULT_SEQUENCE_COMPLETED", "target_contest": target}

        env.update(
            canonical_root=lambda root: root,
            load_lifecycle=lambda root: dict(state),
            terminal_operation=terminal,
            post_result_report_operation=report,
        )
        with tempfile.TemporaryDirectory() as root:
            result = operation(root, 3071)
        self.assertEqual(result["status"], "POST_RESULT_OPERATIONALLY_COMPLETED")
        self.assertEqual(result["next_target"], 3072)
        self.assertEqual(calls, [("terminal", 3071, False), ("report", 3071)])
        self.assertFalse(result["terminal_promotion_attempted"])

    def test_waiting_result_is_retryable(self):
        operation, env = _operator_function()
        env.update(
            canonical_root=lambda root: root,
            load_lifecycle=lambda root: {"state": "FROZEN", "target_contest": 3071},
            terminal_operation=lambda *a, **kw: {"status": "WAITING_OFFICIAL_RESULT"},
        )
        with tempfile.TemporaryDirectory() as root:
            outcome = operation(root, 3071)
        self.assertEqual(outcome["status"], "WAITING_FOR_RESULT")
        self.assertEqual(outcome["next_target"], 3072)

    def test_resuming_after_adjudication_skips_terminal(self):
        operation, env = _operator_function()
        env.update(
            canonical_root=lambda root: root,
            load_lifecycle=lambda root: {"state": "ADJUDICATED", "target_contest": 3071},
            terminal_operation=lambda *a, **kw: self.fail("terminal should not replay"),
            post_result_report_operation=lambda *a: {
                "status": "POST_RESULT_SEQUENCE_COMPLETED"
            },
        )
        with tempfile.TemporaryDirectory() as root:
            outcome = operation(root, 3071)
        self.assertEqual(outcome["status"], "POST_RESULT_OPERATIONALLY_COMPLETED")

    def test_wrong_target_is_rejected(self):
        operation, env = _operator_function()
        env.update(
            canonical_root=lambda root: root,
            load_lifecycle=lambda root: {"state": "FROZEN", "target_contest": 3070},
        )
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "target differs"):
                operation(root, 3071)

    def test_unready_lifecycle_is_rejected(self):
        operation, env = _operator_function()
        env.update(
            canonical_root=lambda root: root,
            load_lifecycle=lambda root: {"state": "PREPARED", "target_contest": 3071},
        )
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "requires FROZEN"):
                operation(root, 3071)


if __name__ == "__main__":
    unittest.main()

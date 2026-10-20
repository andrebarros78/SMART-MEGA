"""Terminal pending outcomes must not poison idempotent retries."""
from __future__ import annotations
import ast
import tempfile
import unittest
from pathlib import Path
from smart_idempotency import idempotent_operation


class TestTerminalPendingIdempotency(unittest.TestCase):
    def test_unavailable_result_does_not_cache(self):
        statuses = iter(["WAITING_OFFICIAL_RESULT", "ADJUDICATED"])
        calls = []

        @idempotent_operation(
            "TERMINAL", commit_if=lambda result: result.get("status") == "ADJUDICATED"
        )
        def run(root, target):
            calls.append(target)
            return {"status": next(statuses)}

        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(run(root, 3071)["status"], "WAITING_OFFICIAL_RESULT")
            self.assertEqual(run(root, 3071)["status"], "ADJUDICATED")
            self.assertEqual(run(root, 3071)["status"], "ADJUDICATED")
        self.assertEqual(calls, [3071, 3071])

    def test_regular_idempotent_operations_keep_their_existing_semantics(self):
        calls = []

        @idempotent_operation("REVIEW")
        def run(root, target):
            calls.append(target)
            return {"status": "REVIEWED"}

        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(run(root, 3071)["status"], "REVIEWED")
            self.assertEqual(run(root, 3071)["status"], "REVIEWED")
        self.assertEqual(calls, [3071])

    def test_terminal_handler_declares_commit_precondition(self):
        source = Path(__file__).resolve().with_name("smart_operator.py").read_text()
        node = next(
            item for item in ast.parse(source).body
            if isinstance(item, ast.FunctionDef) and item.name == "terminal_operation"
        )
        decorators = [ast.get_source_segment(source, item) for item in node.decorator_list]
        self.assertTrue(any(
            "idempotent_operation" in item and "commit_if" in item
            for item in decorators
        ))


if __name__ == "__main__":
    unittest.main()

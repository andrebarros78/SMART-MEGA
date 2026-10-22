"""Regression: native CLI dispatches one resumable product cycle, not fallback RNG."""
from __future__ import annotations
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class TestCycleWiring(unittest.TestCase):
    def test_real_operator_declares_recover_cycle(self):
        source = (ROOT / "smart_operator.py").read_text(encoding="utf-8")
        nodes = ast.parse(source).body
        methods = {n.name: n for n in nodes if isinstance(n, ast.FunctionDef)}
        self.assertIn("recover_cycle_operation", methods)
        body = ast.get_source_segment(source, methods["recover_cycle_operation"])
        self.assertIn("complete_to_model_card", body)
        self.assertIn("complete_result_operation", body)
        self.assertIn("catch_up_missed_operation", body)
        self.assertIn("generate_card_operation", body)
        self.assertIn("read_frozen_card", body)
        self.assertNotIn("generate_contingency_card", body)

    def test_cli_is_registered_without_automatic_network_fallback(self):
        source = (ROOT / "smart_operator.py").read_text(encoding="utf-8")
        self.assertIn('sub.add_parser("recover-cycle")', source)
        self.assertIn('args.action == "recover-cycle"', source)
        self.assertIn("recover_cycle_operation(root, args.target, args.payload_file)", source)

    def test_github_operator_routes_explicit_cycle_to_original_product(self):
        source = (ROOT / "smart_github_operator.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        handlers = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        self.assertIn("recover-cycle", source)
        self.assertIn('"recover-cycle": "--payload-file"', source)
        self.assertIn('    "recover-cycle": "--payload-file",', source)
        self.assertIn('"smart_operator.py", operation', ast.get_source_segment(source, handlers["command_args"]))
        self.assertIn('"recover-cycle"', source.split("TARGET_ACTIONS = {", 1)[1].split("}", 1)[0])
        self.assertNotIn('"recover-cycle"', ast.get_source_segment(source, handlers["execute"]).split('if operation in READ_ONLY:')[0])

if __name__ == "__main__":
    unittest.main()

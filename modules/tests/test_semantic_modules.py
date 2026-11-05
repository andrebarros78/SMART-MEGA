import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import semantic_modules as sm


class SemanticModulesContractTest(unittest.TestCase):
    def test_unknown_file_is_rejected(self):
        with self.assertRaises(ValueError):
            sm.classify_name("smart_new_undocumented_component.py")

    def test_registry_covers_each_source_exactly_once(self):
        registry = sm.load_registry()
        source_names = {
            p.name for p in sm.MAIN.glob("*.py") if not p.name.startswith("test_")
        }
        assigned = [
            item["source"]
            for module in registry["modules"]
            for item in module["sources"]
        ]
        self.assertEqual(set(assigned), source_names)
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_real_import_graph_is_bound(self):
        registry = sm.load_registry()
        edges = {(x["source"], x["target"]) for x in registry["imports"]}
        self.assertIn(("smart_operator.py", "smart_transaction_journal.py"), edges)
        self.assertIn(("smart_agent_skill_orchestration.py", "smart_mission_status.py"), edges)

    def test_runtime_source_resolution_and_hash(self):
        path = sm.resolve_source("smart_operator.py")
        self.assertEqual(path, sm.MAIN / "smart_operator.py")
        self.assertEqual(sm.validate_registry()["status"], "PASS")

    def test_contract_matches_registry_hash(self):
        registry = sm.load_registry()
        contract = json.loads(sm.CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["modules"], registry["module_count"])
        self.assertEqual(contract["sources"], registry["source_count"])
        self.assertEqual(contract["registry_sha256"], sm.file_hash(sm.REGISTRY))

    def test_registry_does_not_become_stale_after_own_git_commit(self):
        before = sm.build_registry()
        with patch.object(sm, "_git_head", return_value="f" * 40):
            after = sm.build_registry()
        self.assertEqual(before, after)
        self.assertNotIn("head", before)

    def test_source_paths_are_checkout_relative(self):
        registry = sm.load_registry()
        source = next(
            source for module in registry["modules"]
            for source in module["sources"]
            if source["source"] == "smart_operator.py"
        )
        self.assertEqual(source["relative_path"], "smart_operator.py")

    def test_tampering_is_detected_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text("print('test')", encoding="utf-8")
            with self.assertRaises(ValueError):
                sm.verify_file(path, "0" * 64)


if __name__ == "__main__":
    unittest.main()

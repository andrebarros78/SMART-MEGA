"""Non-regression of the non-certified, adjudication-independent card lane."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock
import sys

from smart_contingency_card import generate_contingency_card

SHA = "a" * 64
NOW = datetime(2026, 10, 20, 17, 54, tzinfo=timezone.utc)


class FixedChooser:
    def sample(self, population, k):
        assert k == 6
        return [43, 19, 30, 20, 13, 35]


class TestContingencyCard(unittest.TestCase):
    def test_generated_replay_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SMART_OPERATIONAL_LIFECYCLE.json").write_text("untouched")
            first = generate_contingency_card(root, 3072, preceding_target=3071,
                                              lifecycle_sha256=SHA, chooser=FixedChooser(), now=NOW)
            again = generate_contingency_card(root, 3072, preceding_target=3071,
                                              lifecycle_sha256=SHA, chooser=FixedChooser(), now=NOW)
            self.assertEqual(first["numbers"], [13, 19, 20, 30, 35, 43])
            self.assertEqual(first["status"], "CONTINGENCY_NOT_CERTIFIED")
            self.assertFalse(first["model_certified"])
            self.assertFalse(first["scientific_proof"])
            self.assertFalse(first["next_cycle_freeze_authority"])
            self.assertFalse(first["adjudication_required"])
            self.assertTrue(again["idempotent_replay"])
            self.assertEqual(first["sha256"], again["sha256"])
            self.assertEqual((root / "SMART_OPERATIONAL_LIFECYCLE.json").read_text(), "untouched")
            self.assertEqual(json.loads((root / first["receipt_file"]).read_text())["sha256"], first["sha256"])

    def test_reject_target_skip(self):
        with tempfile.TemporaryDirectory() as d:
            for target in (3070, 3071, 3073):
                with self.assertRaisesRegex(ValueError, "immediately next"):
                    generate_contingency_card(d, target, preceding_target=3071, lifecycle_sha256=SHA)

    def test_reject_invalid_authority(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "lifecycle SHA"):
                generate_contingency_card(d, 3072, preceding_target=3071, lifecycle_sha256="invalid")

    def test_fail_closed_tampered_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            receipt = generate_contingency_card(d, 3072, preceding_target=3071,
                                                lifecycle_sha256=SHA, chooser=FixedChooser())
            path = Path(d) / receipt["receipt_file"]
            data = json.loads(path.read_text())
            data["numbers"] = [1, 2, 3, 4, 5, 6]
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "integrity failure"):
                generate_contingency_card(d, 3072, preceding_target=3071, lifecycle_sha256=SHA)

    def test_fail_closed_other_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            generate_contingency_card(d, 3072, preceding_target=3071,
                                      lifecycle_sha256=SHA, chooser=FixedChooser())
            with self.assertRaisesRegex(ValueError, "authority mismatch"):
                generate_contingency_card(d, 3072, preceding_target=3071, lifecycle_sha256="b" * 64)

    def test_never_write_canonical_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            protected = ["Mega-Sena.xlsx", "SMART_ACTIVE_EPOCH.json", "SMART_SIGNAL_LEDGER.json"]
            for name in protected:
                (root / name).write_bytes(b"permanent")
            generate_contingency_card(d, 3072, preceding_target=3071,
                                      lifecycle_sha256=SHA, chooser=FixedChooser())
            for name in protected:
                self.assertEqual((root / name).read_bytes(), b"permanent")

    def test_cannot_masquerade_certification(self):
        with tempfile.TemporaryDirectory() as d:
            receipt = generate_contingency_card(d, 3072, preceding_target=3071,
                                                lifecycle_sha256=SHA, chooser=FixedChooser())
            path = Path(d) / receipt["receipt_file"]
            doc = json.loads(path.read_text())
            doc["scientific_proof"] = True
            path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "falsely claims"):
                generate_contingency_card(d, 3072, preceding_target=3071, lifecycle_sha256=SHA)


class TestOperatorDispatchWithoutThirdPartyRuntime(unittest.TestCase):
    @staticmethod
    def _operator_function(**environment):
        source = Path(__file__).resolve().with_name("smart_operator.py").read_text(encoding="utf-8")
        node = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "generate_card_operation")
        environment["Any"] = Any
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(Path(__file__).resolve().with_name("smart_operator.py")), "exec"), environment)
        return environment["generate_card_operation"]

    def test_unadjudicated_previous_cycle_routes_to_contingency(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"Path": Path, "canonical_root": lambda r: r,
                   "load_lifecycle": lambda r: {"state": "FROZEN",
                                                 "target_contest": 3071, "sha256": SHA}}
            operation = self._operator_function(**env)
            output = operation(d, 3072)
            self.assertEqual(output["status"], "CONTINGENCY_NOT_CERTIFIED")
            self.assertEqual(output["target_contest"], 3072)
            self.assertFalse(output["changes_productive_epoch"])

    def test_skip_not_permitted(self):
        env = {"Path": Path, "canonical_root": lambda r: r,
               "load_lifecycle": lambda r: {"state": "FROZEN",
                                             "target_contest": 3071, "sha256": SHA}}
        with self.assertRaisesRegex(ValueError, "differs from lifecycle"):
            self._operator_function(**env)("/tmp", 3073)

    def test_official_frozen_same_target_remains_unchanged(self):
        env = {"Path": Path, "canonical_root": lambda r: r,
               "load_lifecycle": lambda r: {"state": "FROZEN", "target_contest": 3071,
                                             "sha256": SHA},
               "freeze_operation": lambda root, target: {"status": "FROZEN", "target_contest": target}}
        result = self._operator_function(**env)("/tmp", 3071)
        self.assertEqual(result, {"status": "FROZEN", "target_contest": 3071})



class TestContingencyReceiptAtomicity(unittest.TestCase):
    def test_interrupted_finalization_leaves_no_partial_card(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("smart_contingency_card.os.link", side_effect=OSError("simulated IO failure")):
                with self.assertRaisesRegex(OSError, "simulated IO failure"):
                    generate_contingency_card(d, 3072, preceding_target=3071,
                                              lifecycle_sha256=SHA, chooser=FixedChooser())
            folder = Path(d) / "runtime" / "contingency_cards"
            self.assertFalse((folder / "SMART_CONTINGENCY_CARD_3072.json").exists())
            self.assertEqual(list(folder.iterdir()), [])

    def test_symlinked_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.joinpath("runtime", "contingency_cards").mkdir(parents=True)
            target = root / "outside.json"
            target.write_text("{}")
            link = root / "runtime" / "contingency_cards" / "SMART_CONTINGENCY_CARD_3072.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                generate_contingency_card(d, 3072, preceding_target=3071,
                                          lifecycle_sha256=SHA, chooser=FixedChooser())
            self.assertEqual(target.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()

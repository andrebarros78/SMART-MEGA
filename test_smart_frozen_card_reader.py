"""Model-card consumption is read-only and independent of adjudication/pandas."""
from __future__ import annotations
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import smart_frozen_card_reader as reader

ROOT = Path(__file__).resolve().parent


class FrozenCardConsumer(unittest.TestCase):
    def test_real_3071_card_is_consumable_after_the_draw(self):
        before = reader.file_sha256(ROOT / "SMART_ACTIVE_EPOCH.json")
        result = reader.read_frozen_card(ROOT, 3071)
        self.assertEqual(result["status"], "FROZEN_MODEL_CARD_VERIFIED")
        self.assertEqual(result["numbers"], [10, 11, 27, 38, 43, 53])
        self.assertEqual(result["target_contest"], 3071)
        self.assertEqual(result["cutoff_contest"], 3070)
        self.assertFalse(result["result_used_in_generation"])
        self.assertFalse(result["certified_predictive_advantage"])
        self.assertTrue(result["readonly"])
        self.assertEqual(before, reader.file_sha256(ROOT / "SMART_ACTIVE_EPOCH.json"))
        self.assertTrue(reader.verify_result(result))

    def test_reading_future_card_from_old_freeze_is_forbidden(self):
        with self.assertRaisesRegex(ValueError, "not frozen"):
            reader.read_frozen_card(ROOT, 3072)

    def test_invalid_target_rejected(self):
        for target in (True, -1, 0, "3071", 3070):
            with self.subTest(target=target), self.assertRaises(ValueError):
                reader.read_frozen_card(ROOT, target)

    def test_tampered_primary_card_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            doc = self._card_doc(local)
            doc["numbers"] = [1, 2, 3, 4, 5, 6]
            self._card_file(local).write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "card.*(hash|SHA)"):
                reader.read_frozen_card(local, 3071)

    def test_tampered_freeze_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            frozen = local / json.loads((local / "SMART_ACTIVE_EPOCH.json").read_text())["freeze_authority"]["file"]
            frozen.write_bytes(b"altered freeze")
            with self.assertRaisesRegex(ValueError, "freeze.*SHA"):
                reader.read_frozen_card(local, 3071)

    def test_wrong_proof_target_fails_even_if_self_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            p = self._proof_file(local)
            proof = json.loads(p.read_text())
            proof["target_contest"] = 3072
            proof["sha256"] = reader.sha256_json({k: v for k, v in proof.items() if k != "sha256"})
            p.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, "proof.*target"):
                reader.read_frozen_card(local, 3071)

    def test_tampered_portfolio_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            pf = self._portfolio_file(local)
            pf.write_text("{}")
            with self.assertRaisesRegex(ValueError, "portfolio.*SHA"):
                reader.read_frozen_card(local, 3071)

    def test_symlinked_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            p = self._card_file(local)
            b = p.read_bytes()
            other = p.with_suffix(".other")
            other.write_bytes(b)
            p.unlink()
            p.symlink_to(other)
            with self.assertRaisesRegex(ValueError, "symbolic"):
                reader.read_frozen_card(local, 3071)

    def test_no_canonical_files_mutated(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            before = {p.relative_to(local): p.read_bytes() for p in local.rglob("*") if p.is_file()}
            reader.read_frozen_card(local, 3071)
            after = {p.relative_to(local): p.read_bytes() for p in local.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_github_operator_readonly_shows_actual_card_numbers(self):
        import subprocess
        import sys
        completed = subprocess.run(
            [sys.executable, "smart_github_operator.py", "--operation", "show-card",
             "--target", "3071"],
            cwd=ROOT, text=True, capture_output=True, timeout=25,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        doc = json.loads(completed.stdout)
        self.assertEqual(doc.get("operation"), "show-card")
        self.assertEqual(doc.get("model_card", {}).get("numbers"), [10, 11, 27, 38, 43, 53])
        self.assertEqual(doc.get("model_card", {}).get("status"), "FROZEN_MODEL_CARD_VERIFIED")
        self.assertIsNone(doc.get("commit"))

    def test_response_tampering_does_not_verify(self):
        doc = reader.read_frozen_card(ROOT, 3071)
        doc["numbers"][0] = 1
        self.assertFalse(reader.verify_result(doc))

    @staticmethod
    def _proof_file(root):
        active = json.loads((root / "SMART_ACTIVE_EPOCH.json").read_text())
        return (root / active["freeze_authority"]["file"]).parent / "FULL_PROCESS_PROOF.json"

    @classmethod
    def _card_file(cls, root):
        proof = json.loads(cls._proof_file(root).read_text())
        return root / proof["primary_card_file"]

    @classmethod
    def _portfolio_file(cls, root):
        proof = json.loads(cls._proof_file(root).read_text())
        return root / proof["portfolio_file"]

    @classmethod
    def _card_doc(cls, root):
        return json.loads(cls._card_file(root).read_text())

    @staticmethod
    def _copy_bundle(dest):
        from pathlib import Path
        a = json.loads((ROOT / "SMART_ACTIVE_EPOCH.json").read_text(encoding="utf-8-sig"))
        freeze = ROOT / a["freeze_authority"]["file"]
        proof = json.loads((freeze.parent / "FULL_PROCESS_PROOF.json").read_text())
        dest.joinpath("SMART_ACTIVE_EPOCH.json").write_bytes((ROOT / "SMART_ACTIVE_EPOCH.json").read_bytes())
        for raw in [a["freeze_authority"]["file"], proof["freeze_file"],
                    proof["primary_card_file"], proof["portfolio_file"]]:
            src = ROOT / raw
            dst = dest / raw
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        dst = dest / a["freeze_authority"]["file"]
        shutil.copyfile(freeze.parent / "FULL_PROCESS_PROOF.json", dst.parent / "FULL_PROCESS_PROOF.json")
        return dest


if __name__ == "__main__":
    unittest.main()

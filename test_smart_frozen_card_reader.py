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
        before = reader.file_sha256(self._pointer_file(ROOT))
        result = reader.read_frozen_card(ROOT, 3071)
        self.assertEqual(result["status"], "FROZEN_MODEL_CARD_VERIFIED")
        self.assertEqual(result["numbers"], [10, 11, 27, 38, 43, 53])
        self.assertEqual(result["target_contest"], 3071)
        self.assertEqual(result["cutoff_contest"], 3070)
        self.assertFalse(result["result_used_in_generation"])
        self.assertFalse(result["certified_predictive_advantage"])
        self.assertTrue(result["readonly"])
        self.assertEqual(before, reader.file_sha256(self._pointer_file(ROOT)))
        self.assertTrue(reader.verify_result(result))

    def test_reading_future_card_from_old_freeze_is_forbidden(self):
        with self.assertRaisesRegex(ValueError, "not frozen|unique immutable archive"):
            reader.read_frozen_card(ROOT, 3072)

    def test_invalid_target_rejected(self):
        for target in (True, -1, 0, "3071", 3072):
            with self.subTest(target=target), self.assertRaises(ValueError):
                reader.read_frozen_card(ROOT, target)

    def test_tampered_primary_card_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            doc = self._card_doc(local)
            doc["numbers"] = [1, 2, 3, 4, 5, 6]
            self._card_file(local).write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "(card|archive).*(hash|SHA)"):
                reader.read_frozen_card(local, 3071)

    def test_tampered_freeze_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            a = json.loads(self._pointer_file(local).read_text())
            frozen = self._archive_root(local) / "epoch" / Path(a["freeze_authority"]["file"]).name
            frozen.write_bytes(b"altered freeze")
            with self.assertRaisesRegex(ValueError, "freeze.*(SHA|hash)"):
                reader.read_frozen_card(local, 3071)

    def test_wrong_proof_target_fails_even_if_self_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            p = self._proof_file(local)
            proof = json.loads(p.read_text())
            proof["target_contest"] = 3072
            proof["sha256"] = reader.sha256_json({k: v for k, v in proof.items() if k != "sha256"})
            p.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, "proof.*(target|archive|SHA|hash)"):
                reader.read_frozen_card(local, 3071)

    def test_tampered_portfolio_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = self._copy_bundle(Path(tmp))
            pf = self._portfolio_file(local)
            pf.write_text("{}")
            with self.assertRaisesRegex(ValueError, "portfolio.*(SHA|hash)"):
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
        # A research branch must not impersonate canonical production main.
        # Test its fail-closed behavior without skipping any test.
        branch = subprocess.run(
            ["git", "branch", "--show-current"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if branch != "main":
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("external operator must use canonical main branch", completed.stderr)
            card = reader.read_frozen_card(ROOT, 3071)
            self.assertEqual(card["numbers"], [10, 11, 27, 38, 43, 53])
            self.assertTrue(reader.verify_result(card))
            return
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
    def _archive_root(root):
        matches = sorted((root / "SMART_STATE_ARCHIVE" / "adjudicated-epochs" / "3071").glob("*/ARCHIVE_MANIFEST.json"))
        if len(matches) != 1:
            raise ValueError("expected one immutable archived epoch 3071")
        return matches[0].parent

    @classmethod
    def _pointer_file(cls, root):
        live = root / "SMART_ACTIVE_EPOCH.json"
        return live if live.exists() else cls._archive_root(root) / "SMART_ACTIVE_EPOCH.json"

    @classmethod
    def _proof_file(cls, root):
        return cls._archive_root(root) / "epoch" / "FULL_PROCESS_PROOF.json"

    @classmethod
    def _card_file(cls, root):
        proof = json.loads(cls._proof_file(root).read_text())
        return cls._archive_root(root) / "epoch" / Path(proof["primary_card_file"]).name

    @classmethod
    def _portfolio_file(cls, root):
        proof = json.loads(cls._proof_file(root).read_text())
        return cls._archive_root(root) / "epoch" / Path(proof["portfolio_file"]).name

    @classmethod
    def _card_doc(cls, root):
        return json.loads(cls._card_file(root).read_text())

    @classmethod
    def _copy_bundle(cls, dest):
        archive = cls._archive_root(ROOT)
        target = dest / archive.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(archive, target)
        return dest


if __name__ == "__main__":
    unittest.main()

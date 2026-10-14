"""No-Actions native Git publication: sandbox bare remote, never production main."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from smart_native_card_publisher import publish_operator_card
from smart_operator_card_requests import _hash


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=True).stdout.strip()


class NativeCardGitPublisherTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.root = Path(self.workspace.name)
        self.remote = self.root / "private-test-remote.git"
        self.repo = self.root / "checkout"
        self.remote.mkdir()
        self.repo.mkdir()
        _git(self.remote, "init", "--bare")
        _git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "init", "-b", "main")
        _git(self.repo, "config", "user.name", "Sandbox Tester")
        _git(self.repo, "config", "user.email", "sandbox@example.invalid")
        _git(self.repo, "remote", "add", "origin", str(self.remote))
        (self.repo / "README.md").write_text("sandbox Git source\n")
        _git(self.repo, "add", "README.md")
        _git(self.repo, "commit", "-m", "original sandbox main")
        _git(self.repo, "push", "-u", "origin", "main")
        self.allowed = frozenset([str(self.remote)])
        self.calls = 0

    def tearDown(self):
        self.workspace.cleanup()

    def _check_window(self):
        self.calls += 1

    def _receipt(self, ordinal, key):
        values = [1,2,3,4,20+ordinal,30+ordinal]
        receipt = {
            "schema": "SMART_OPERATOR_CARD_REQUEST_1",
            "status": "ISSUED_FOR_EXPLICIT_OPERATOR_REQUEST",
            "target_contest": 3099,
            "cutoff_contest": 3098,
            "request_ordinal": ordinal,
            "operator_request_id": key,
            "cards_issued_for_this_request": 1,
            "explicit_operator_request": True,
            "freeze_sha256": "a"*64,
            "source_head": "champion",
            "numbers": values,
            "result_used": False,
            "model_weights_changed": False,
        }
        receipt["sha256"] = _hash(receipt)
        f = self.repo / f"runtime/operator_card_requests/3099/CARD-{ordinal:04d}-{key}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")
        return receipt,f

    def _publish(self, receipt):
        return publish_operator_card(self.repo, receipt,
                                     pre_draw_check=self._check_window,
                                     allowed_remotes=self.allowed)

    def test_git_main_publishes_two_successive_operator_receipts_idempotently(self):
        first,path=self._receipt(1,"operator-1")
        one=self._publish(first)
        self.assertEqual(one["status"],"CARD_RECEIPT_PUBLISHED_GITHUB_NATIVE")
        self.assertEqual(self.calls,2)
        self.assertEqual(one["commit"],_git(self.repo,"rev-parse","HEAD"))
        self.assertEqual(one["commit"],_git(self.repo,"ls-remote","origin","refs/heads/main").split()[0])
        self.assertEqual(_git(self.repo,"status","--porcelain=v1"),"")
        original_sha=one["commit"]
        replay=self._publish({**first,"idempotent_replay":True})
        self.assertEqual(replay["status"],"ALREADY_PUBLISHED")
        self.assertEqual(replay["commit"],original_sha)
        second,_=self._receipt(2,"operator-2")
        two=self._publish(second)
        self.assertNotEqual(two["commit"],original_sha)
        self.assertEqual(_git(self.repo,"status","--porcelain=v1"),"")
        files=_git(self.repo,"ls-tree","-r","--name-only","HEAD").splitlines()
        self.assertIn("runtime/operator_card_requests/3099/CARD-0001-operator-1.json",files)
        self.assertIn("runtime/operator_card_requests/3099/CARD-0002-operator-2.json",files)
        self.assertIn(".gitattributes",files)
        self.assertNotIn("workflow_dispatch",two["status"])

    def test_branch_other_than_main_is_not_authorized_to_publish(self):
        _git(self.repo,"checkout","-b","engineering")
        first,_=self._receipt(1,"operator-1")
        with self.assertRaisesRegex(PermissionError,"canonical main"):
            self._publish(first)

    def test_dirty_unrelated_file_blocks_publication(self):
        first,_=self._receipt(1,"operator-1")
        (self.repo/"README.md").write_text("tampered unrelated file\n")
        with self.assertRaisesRegex(RuntimeError,"other changes"):
            self._publish(first)

    def test_remote_origin_mismatch_is_rejected(self):
        first,_=self._receipt(1,"operator-1")
        with self.assertRaisesRegex(PermissionError,"not approved"):
            publish_operator_card(self.repo,first,pre_draw_check=self._check_window)

    def test_expired_draw_window_prevents_commit_and_push(self):
        first,_=self._receipt(1,"operator-1")
        original=_git(self.repo,"rev-parse","HEAD")
        with self.assertRaisesRegex(PermissionError,"outside draw window"):
            publish_operator_card(
                self.repo,first,
                pre_draw_check=lambda: (_ for _ in ()).throw(
                    PermissionError("outside draw window")
                ),
                allowed_remotes=self.allowed,
            )
        self.assertEqual(_git(self.repo,"rev-parse","HEAD"),original)
        self.assertEqual(_git(self.repo,"ls-remote","origin","refs/heads/main").split()[0],original)


    def test_recovers_crash_after_attribute_pin_before_git_add(self):
        from unittest.mock import patch
        from smart_github_operator import _pin_artifact_bytes
        receipt, _ = self._receipt(1, "recovery-pin")
        remote_before = _git(self.repo, "rev-parse", "HEAD")

        def simulated_crash(root, changes):
            _pin_artifact_bytes(root, changes)
            raise OSError("simulated interruption after attributes pin")

        with patch("smart_native_card_publisher._pin_artifact_bytes", side_effect=simulated_crash):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                self._publish(receipt)
        self.assertEqual(_git(self.repo, "ls-remote", "origin", "refs/heads/main").split()[0], remote_before)
        self.assertIn(".gitattributes", _git(self.repo, "status", "--porcelain=v1"))
        recovered = self._publish(receipt)
        self.assertEqual(recovered["status"], "CARD_RECEIPT_PUBLISHED_GITHUB_NATIVE")
        self.assertTrue(recovered["remote_main_verified"])
        self.assertEqual(_git(self.repo, "status", "--porcelain=v1"), "")

    def test_recovers_crash_after_staging_before_commit(self):
        from unittest.mock import patch
        from smart_native_card_publisher import _git as production_git
        receipt, _ = self._receipt(1, "recovery-stage")
        remote_before = _git(self.repo, "rev-parse", "HEAD")

        def interrupted_commit(root, *args):
            if "commit" in args:
                raise RuntimeError("simulated interruption before commit")
            return production_git(root, *args)

        with patch("smart_native_card_publisher._git", side_effect=interrupted_commit):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                self._publish(receipt)
        self.assertEqual(_git(self.repo, "ls-remote", "origin", "refs/heads/main").split()[0], remote_before)
        self.assertIn(".gitattributes", _git(self.repo, "diff", "--cached", "--name-only"))
        recovered = self._publish(receipt)
        self.assertTrue(recovered["remote_main_verified"])
        self.assertEqual(_git(self.repo, "status", "--porcelain=v1"), "")

    def test_recovery_rejects_unrelated_attribute_mutation(self):
        receipt, _ = self._receipt(1, "blocked-unrelated")
        before = _git(self.repo, "rev-parse", "HEAD")
        (self.repo / ".gitattributes").write_text(
            "/runtime/operator_card_requests/3099/CARD-0001-blocked-unrelated.json -text\n"
            "/unrelated-file -text\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "other changes|attributes"):
            self._publish(receipt)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD"), before)
        self.assertEqual(_git(self.repo, "ls-remote", "origin", "refs/heads/main").split()[0], before)

    def test_recovery_refuses_symlinked_attributes_without_writing_outside_checkout(self):
        receipt, _ = self._receipt(1, "unsafe-attributes")
        outside = self.root / "do-not-modify.txt"
        outside.write_text("external data untouched\n", encoding="utf-8")
        (self.repo / ".gitattributes").symlink_to(outside)
        head_before = _git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(RuntimeError, "attributes|other changes"):
            self._publish(receipt)
        self.assertEqual(outside.read_text(encoding="utf-8"), "external data untouched\n")
        self.assertEqual(_git(self.repo,"rev-parse","HEAD"), head_before)
        self.assertEqual(_git(self.repo,"ls-remote","origin","refs/heads/main").split()[0], head_before)

    def test_recovers_after_local_commit_but_failed_push(self):
        from unittest.mock import patch
        from smart_native_card_publisher import _git as production_git
        receipt, _ = self._receipt(1, "recovery-push")
        remote_before = _git(self.repo, "rev-parse", "HEAD")

        def interrupted_push(root, *args):
            if args and args[0] == "push":
                raise RuntimeError("simulated interrupted network push")
            return production_git(root, *args)

        with patch("smart_native_card_publisher._git", side_effect=interrupted_push):
            with self.assertRaisesRegex(RuntimeError, "interrupted network push"):
                self._publish(receipt)
        self.assertNotEqual(_git(self.repo, "rev-parse", "HEAD"), remote_before)
        self.assertEqual(_git(self.repo, "ls-remote", "origin", "refs/heads/main").split()[0], remote_before)
        recovered = self._publish(receipt)
        self.assertTrue(recovered["remote_main_verified"])
        self.assertEqual(_git(self.repo, "status", "--porcelain=v1"), "")


if __name__ == "__main__":
    unittest.main()

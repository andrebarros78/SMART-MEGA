"""Actual issuer -> byte-pinned Git publisher -> remote witness, sandbox only.

No operational lifecycle, real draw, canonical remote or historical archive
is mutated. The exact production consumer functions are exercised against an
isolated, operator-authorized synthetic frozen epoch and local bare Git main.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from smart_native_card_publisher import publish_operator_card
from smart_operator_card_requests import _file_sha, _hash, issue_from_frozen_epoch


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, text=True,
                          capture_output=True, check=True).stdout.strip()


class FullCardIssuancePublicationE2ETests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.work = Path(workspace.name)
        self.repo = self.work / "sandbox-checkout"
        self.remote = self.work / "isolated-remote.git"
        self.repo.mkdir()
        self.remote.mkdir()
        _git(self.remote, "init", "--bare")
        _git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "init", "-b", "main")
        _git(self.repo, "config", "user.name", "Synthetic Card Tester")
        _git(self.repo, "config", "user.email", "sandbox@example.invalid")
        _git(self.repo, "remote", "add", "origin", str(self.remote))
        self.target = 3099
        epoch = self.repo / "runtime/learning_epochs/fixture-3099"
        epoch.mkdir(parents=True)
        freeze = {
            "target_contest": 3099, "cutoff_contest": 3098,
            "frozen_before_result": True, "champion_remains_active": True,
            "champion": {"aggregate_scores": {str(n): float(61-n) for n in range(1,61)},
                         "top6": [1,2,3,4,5,6]},
        }
        freeze_path = epoch / "SMART_3099_CHAMPION_CHALLENGER_FREEZE.json"
        freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
        freeze_sha = _file_sha(freeze_path)
        primary = {
            "target_contest": 3099, "cutoff_contest": 3098,
            "freeze_sha256": freeze_sha, "source_head": "champion",
            "numbers": [1,2,3,4,21,22], "product_role": "FINAL_SINGLE_CARD_PRODUCT",
            "status": "FROZEN", "result_used": False,
            "selector": {"result_used": False},
        }
        primary["sha256"] = _hash(primary)
        (epoch / "SMART_3099_PRIMARY_CARD.json").write_text(json.dumps(primary), encoding="utf-8")
        ledger = epoch / "SMART_SIGNAL_LEDGER.json"
        ledger.write_text(json.dumps({"events": [
            {"target_contest": 3099, "event_type": "FREEZE", "freeze_sha256": freeze_sha}
        ]}), encoding="utf-8")
        self.freeze_path, self.ledger_path = freeze_path, ledger
        self.freeze_sha, self.ledger_sha = freeze_sha, _file_sha(ledger)
        self.active = {
            "status": "FROZEN", "target_contest": 3099,
            "cutoff_contest": 3098, "operator_selected_target": True,
            "freeze_authority": {"file": str(freeze_path.relative_to(self.repo)),
                                 "sha256": freeze_sha},
            "state_paths": {"ledger": str(ledger.relative_to(self.repo))},
        }
        _git(self.repo, "add", "runtime/learning_epochs")
        _git(self.repo, "commit", "-m", "synthetic pre-draw fixture")
        _git(self.repo, "push", "-u", "origin", "main")
        self.original_commit = _git(self.repo, "rev-parse", "HEAD")

    def _issue(self, request_id):
        return issue_from_frozen_epoch(
            self.repo, target=self.target, request_id=request_id,
            active=self.active, operator_requested=True)

    def _publish(self, receipt):
        return publish_operator_card(
            self.repo, receipt, pre_draw_check=lambda: None,
            allowed_remotes=frozenset({str(self.remote)}))

    def _assert_immutable_inputs(self):
        self.assertEqual(_file_sha(self.freeze_path), self.freeze_sha)
        self.assertEqual(_file_sha(self.ledger_path), self.ledger_sha)
        self.assertEqual(self.active["status"], "FROZEN")

    def test_issuer_to_remote_two_distinct_operator_cards_with_replay(self):
        first = self._issue("request-1")
        one = self._publish(first)
        self.assertTrue(one["remote_main_verified"])
        self.assertEqual(first["request_ordinal"], 1)
        replay = self._issue("request-1")
        self.assertTrue(replay["idempotent_replay"])
        already = self._publish(replay)
        self.assertEqual(already["status"], "ALREADY_PUBLISHED")
        self.assertEqual(already["commit"], one["commit"])
        second = self._issue("request-2")
        two = self._publish(second)
        self.assertTrue(two["remote_main_verified"])
        self.assertEqual(second["request_ordinal"], 2)
        self.assertNotEqual(first["numbers"], second["numbers"])
        self.assertEqual(len(first["numbers"]), 6)
        self.assertEqual(len(second["numbers"]), 6)
        self.assertEqual(_git(self.repo,"ls-remote","origin","refs/heads/main").split()[0], two["commit"])
        self.assertEqual(_git(self.repo,"status","--porcelain=v1"), "")
        self.assertEqual(len(list((self.repo / "runtime/operator_card_requests/3099").glob("CARD-*.json"))), 2)
        self.assertEqual(len([name for name in _git(self.repo,"diff","--name-only",self.original_commit,"HEAD").splitlines()
                              if name.startswith("runtime/operator_card_requests/")]), 2)
        self._assert_immutable_inputs()

    def test_local_receipt_crash_before_publication_replays_without_new_card(self):
        first = self._issue("interrupted-request")
        # The process stops here, before calling Git publisher.
        self.assertEqual(_git(self.repo,"rev-parse","HEAD"), self.original_commit)
        replay = self._issue("interrupted-request")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["sha256"], first["sha256"])
        published = self._publish(replay)
        self.assertTrue(published["remote_main_verified"])
        self.assertEqual(len(list((self.repo / "runtime/operator_card_requests/3099").glob("CARD-*.json"))), 1)
        self.assertEqual(_git(self.repo,"status","--porcelain=v1"), "")
        self._assert_immutable_inputs()


if __name__ == "__main__":
    unittest.main()

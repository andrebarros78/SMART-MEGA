"""Functional tests: operator controls how many six-number cards are issued."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from smart_operator_card_requests import (
    _hash, _file_sha, issue_from_frozen_epoch, SCHEMA,
)
from smart_primary_card_selector import select_primary_card


class OperatorCardRequestTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.root = Path(self.workspace.name)
        self.target = 3099
        epoch = self.root / "runtime" / "learning_epochs" / "operator-fixture"
        epoch.mkdir(parents=True)
        freeze = {
            "target_contest": 3099, "cutoff_contest": 3098,
            "frozen_before_result": True,
            "champion_remains_active": True,
            "champion": {
                "aggregate_scores": {str(n): float(61 - n) for n in range(1, 61)},
                "top6": [1, 2, 3, 4, 5, 6],
            },
        }
        freeze_path = epoch / "SMART_3099_CHAMPION_CHALLENGER_FREEZE.json"
        freeze_path.write_text(json.dumps(freeze))
        self.freeze_sha = _file_sha(freeze_path)
        primary = {
            "target_contest": 3099, "cutoff_contest": 3098,
            "freeze_sha256": self.freeze_sha, "source_head": "champion",
            "numbers": [1, 2, 3, 4, 21, 22],
            "product_role": "FINAL_SINGLE_CARD_PRODUCT",
            "status": "FROZEN", "result_used": False,
            "selector": {"result_used": False},
        }
        primary["sha256"] = _hash(primary)
        (epoch / "SMART_3099_PRIMARY_CARD.json").write_text(json.dumps(primary))
        self.ledger_path = epoch / "SMART_SIGNAL_LEDGER.json"
        self.ledger_path.write_text(json.dumps({"events": [
            {"target_contest": 3099, "event_type": "FREEZE",
             "freeze_sha256": self.freeze_sha}
        ]}))
        self.active = {
            "status": "FROZEN", "target_contest": 3099,
            "cutoff_contest": 3098, "operator_selected_target": True,
            "freeze_authority": {
                "file": str(freeze_path.relative_to(self.root)),
                "sha256": self.freeze_sha,
            },
            "state_paths": {"ledger": str(self.ledger_path.relative_to(self.root))},
        }

    def tearDown(self):
        self.workspace.cleanup()

    def issue(self, key, **kwargs):
        return issue_from_frozen_epoch(
            self.root, target=3099, request_id=key,
            active=self.active, operator_requested=True, **kwargs
        )

    def test_no_cards_without_explicit_request(self):
        with self.assertRaisesRegex(PermissionError, "explicit operator"):
            issue_from_frozen_epoch(self.root, target=3099, request_id="one",
                                    active=self.active)
        self.assertFalse((self.root / "runtime/operator_card_requests").exists())

    def test_first_second_third_separate_requests_issue_three_distinct_cards(self):
        first = self.issue("ask-1")
        second = self.issue("ask-2")
        third = self.issue("ask-3")
        self.assertEqual([first["request_ordinal"], second["request_ordinal"],
                          third["request_ordinal"]], [1, 2, 3])
        self.assertEqual(first["numbers"], [1, 2, 3, 4, 21, 22])
        self.assertEqual(len({tuple(row["numbers"]) for row in [first,second,third]}),3)
        for row in [first,second,third]:
            self.assertEqual(len(row["numbers"]),6)
            self.assertTrue(row["explicit_operator_request"])
            self.assertEqual(row["cards_issued_for_this_request"],1)
            self.assertTrue(row["no_fixed_per_contest_card_limit"])
            self.assertEqual(row["freeze_sha256"],self.freeze_sha)
            self.assertFalse(row["result_used"])
        self.assertEqual(len(list((self.root/"runtime/operator_card_requests/3099").glob("CARD-*.json"))),3)

    def test_same_request_replay_returns_original_without_issuing_another_card(self):
        initial=self.issue("same-id")
        again=self.issue("same-id")
        self.assertEqual(again["numbers"],initial["numbers"])
        self.assertEqual(again["sha256"],initial["sha256"])
        self.assertTrue(again["idempotent_replay"])
        self.assertEqual(len(list((self.root/"runtime/operator_card_requests/3099").glob("CARD-*.json"))),1)

    def test_racing_receipt_creation_cannot_overwrite_another_writer(self):
        from unittest.mock import patch
        original = b"other-process-did-not-authorize-overwrite"
        destination = (self.root / "runtime/operator_card_requests/3099"
                       / "CARD-0001-race.json")
        def emulate_racing_creation(tmp, final):
            final.write_bytes(original)
            raise FileExistsError("another writer created this filename")
        with patch("smart_operator_card_requests.os.link", side_effect=emulate_racing_creation):
            with self.assertRaisesRegex(FileExistsError, "already issued"):
                self.issue("race")
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(list(destination.parent.glob("card-request-*.tmp")), [])

    def test_prior_receipt_alteration_blocks_new_request(self):
        self.issue("first")
        stored=next((self.root/"runtime/operator_card_requests/3099").glob("CARD-*.json"))
        changed=json.loads(stored.read_text())
        changed["numbers"]=[1, 2, 3, 4, 5, 6]
        stored.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            self.issue("second")

    def test_target_already_adjudicated_rejects_additional_request(self):
        rows=json.loads(self.ledger_path.read_text())
        rows["events"].append({"event_type":"ADJUDICATION","target_contest":3099})
        self.ledger_path.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, "result already available"):
            self.issue("after-result")

    def test_missing_frozen_authority_fails_closed(self):
        self.active["freeze_authority"]["sha256"]="0"*64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.issue("not-authorized")

    def test_invalid_request_identifiers_fail_closed(self):
        for request_id in ("", "../move", "a/b", "x"*65):
            with self.subTest(request_id=request_id):
                with self.assertRaisesRegex(ValueError, "request id invalid"):
                    self.issue(request_id)

    def test_default_selector_unchanged_and_exclusion_creates_another_six(self):
        scores={str(n): float(61-n) for n in range(1,61)}
        first=select_primary_card(scores)
        second=select_primary_card(scores,excluded_cards=[first["selected_numbers"]])
        self.assertNotEqual(first["selected_numbers"],second["selected_numbers"])
        self.assertNotIn("operator_request_excluded_prior_cards",first)
        self.assertEqual(second["operator_request_excluded_prior_cards"],1)

    def test_no_extra_card_from_diagnostic_model_alone(self):
        self.assertEqual(SCHEMA,"SMART_OPERATOR_CARD_REQUEST_1")
        self.active["operator_selected_target"]=False
        with self.assertRaisesRegex(PermissionError,"operator-authorized"):
            self.issue("shadow-model-only")


if __name__ == "__main__":
    unittest.main()

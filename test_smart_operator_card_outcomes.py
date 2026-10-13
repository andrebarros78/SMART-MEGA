"""Post-result reconciliation and genuine archival lineage; never a new forecast."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import unittest

import test_smart_operator_card_requests as fixtures
from smart_operator_card_outcomes import reconcile_operator_card_outcomes
from smart_operator_card_requests import _hash


ROOT = Path(__file__).resolve().parent
ARCHIVE = (ROOT / "SMART_STATE_ARCHIVE" / "adjudicated-epochs" / "3068"
           / "operator-3068-acc6a34c9e27-20261008T222652499219Z" / "epoch")


class OperatorCardOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.OperatorCardRequestTests("test_no_cards_without_explicit_request")
        self.fixture.setUp()
        self.root = self.fixture.root
        self.freeze_sha = self.fixture.freeze_sha
        self.actual = [1, 7, 27, 39, 43, 57]
        self.after = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    def tearDown(self):
        self.fixture.tearDown()

    def evaluate(self):
        return reconcile_operator_card_outcomes(
            self.root, 3099, self.freeze_sha, self.actual, self.after,
        )

    def test_no_receipts_is_not_inferred_as_one_issued_card(self):
        self.assertIsNone(self.evaluate())

    def test_absent_optional_receipts_preserve_legacy_adjudication_without_timestamp(self):
        self.assertIsNone(reconcile_operator_card_outcomes(
            self.root, 3099, self.freeze_sha, self.actual, None,
        ))

    def test_three_authorized_requests_match_only_the_later_official_result(self):
        issued = [self.fixture.issue("one"), self.fixture.issue("two"), self.fixture.issue("three")]
        before = {row["operator_request_id"]: row["sha256"] for row in issued}
        result = self.evaluate()
        self.assertEqual(result["operator_requested_card_count"], 3)
        self.assertEqual([x["request_ordinal"] for x in result["results"]], [1, 2, 3])
        self.assertTrue(result["all_cards_have_six_distinct_numbers"])
        for outcome in result["results"]:
            key = outcome["operator_request_id"]
            self.assertEqual(outcome["receipt_sha256"], before[key])
            self.assertEqual(outcome["hits"], len(set(outcome["numbers"]) & set(self.actual)))
            self.assertEqual(len(outcome["matched_numbers"]), outcome["hits"])
            self.assertEqual(len(outcome["false_negative_numbers"]), 6-outcome["hits"])
            self.assertEqual(len(outcome["false_positive_numbers"]), 6-outcome["hits"])
        self.assertIs(result["model_weight_change_authorized"], False)
        self.assertIs(result["prospective_publication_independently_verified"], False)
        self.assertIs(result["prospective_superiority_proven"], False)

    def test_results_must_follow_cards(self):
        self.fixture.issue("one")
        with self.assertRaisesRegex(ValueError, "not issued before adjudication"):
            reconcile_operator_card_outcomes(
                self.root, 3099, self.freeze_sha, self.actual,
                "2020-01-01T00:00:00+00:00",
            )

    def test_invalid_receipt_or_repeat_combination_blocks_adjudication(self):
        first = self.fixture.issue("one")
        second = self.fixture.issue("two")
        folder = self.root / "runtime" / "operator_card_requests" / "3099"
        receipt = folder / "CARD-0002-two.json"
        forged = json.loads(receipt.read_text())
        forged["numbers"] = first["numbers"]
        forged.pop("sha256", None)
        forged["sha256"] = _hash(forged)
        receipt.write_text(json.dumps(forged))
        with self.assertRaisesRegex(ValueError, "duplicate combination"):
            self.evaluate()
        self.assertNotEqual(second["sha256"], forged["sha256"])

    def test_original_primary_source_tamper_blocks_result(self):
        self.fixture.issue("one")
        file = self.root / "runtime" / "learning_epochs" / "operator-fixture" / "SMART_3099_PRIMARY_CARD.json"
        file.write_bytes(file.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "lost original primary-card binding"):
            self.evaluate()

    def test_empty_receipt_directory_is_not_silent_success(self):
        directory = self.root / "runtime" / "operator_card_requests" / "3099"
        directory.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "no card receipts"):
            self.evaluate()


class AuthenticArchivedChainTests(unittest.TestCase):
    def test_3068_signals_weights_champion_challenger_card_result_learning(self):
        freeze_path = ARCHIVE / "SMART_3068_CHAMPION_CHALLENGER_FREEZE.json"
        freeze = json.loads(freeze_path.read_text())
        frozen_sha = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
        ledger = json.loads((ROOT / "SMART_SIGNAL_LEDGER.json").read_text(encoding="utf-8-sig"))
        events = [e for e in ledger["events"] if e.get("target_contest") == 3068]
        types = [e["event_type"] for e in events]
        self.assertEqual(types.count("FREEZE"), 1)
        self.assertEqual(types.count("ADJUDICATION"), 1)
        self.assertEqual(types.count("LEARNING_UPDATE"), 1)
        self.assertEqual(types.count("SEQUENTIAL_PROOF"), 1)
        self.assertLess(types.index("FREEZE"), types.index("ADJUDICATION"))
        self.assertLess(types.index("ADJUDICATION"), types.index("LEARNING_UPDATE"))
        self.assertLess(types.index("LEARNING_UPDATE"), types.index("SEQUENTIAL_PROOF"))
        archived_freeze_event = next(e for e in events if e["event_type"] == "FREEZE")
        adjudication = next(e for e in events if e["event_type"] == "ADJUDICATION")
        learning = next(e for e in events if e["event_type"] == "LEARNING_UPDATE")
        proof = next(e for e in events if e["event_type"] == "SEQUENTIAL_PROOF")
        self.assertEqual(frozen_sha, archived_freeze_event["freeze_sha256"])
        self.assertEqual(frozen_sha, adjudication["freeze_sha256"])
        self.assertTrue(proof["freeze_to_adjudication_to_learning_verified"])

        raw = freeze["challenger"]["raw_signals"]
        for head_name, weights_key in (("champion", "expert_weights"), ("challenger", "weights")):
            head = freeze[head_name]
            weights = head[weights_key]
            self.assertEqual(set(weights), set(raw))
            self.assertEqual(len(weights), 12)
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=10)
            for number in range(1, 61):
                reconstructed = sum(float(weights[k]) * float(raw[k]["values"][str(number)])
                                    for k in weights)
                self.assertAlmostEqual(reconstructed, float(head["aggregate_scores"][str(number)]), places=9)
            ranked = sorted(range(1, 61),
                            key=lambda n: (-float(head["aggregate_scores"][str(n)]), n))
            self.assertEqual(head["top6"], ranked[:6])
        card = json.loads((ARCHIVE / "SMART_3068_PRIMARY_CARD.json").read_text())
        self.assertEqual(card["freeze_sha256"], frozen_sha)
        self.assertEqual(card["result_used"], False)
        self.assertEqual(card["source_head"], "champion")
        report = json.loads((ROOT / "SMART_POST_RESULT_REPORT_3068.json").read_text())
        actual = set(adjudication["actual_numbers"])
        self.assertEqual(actual, set(report["official_result"]))
        self.assertEqual(set(card["numbers"]), set(report["generated_card"]))
        self.assertEqual(len(actual & set(card["numbers"])), report["hit_count"])
        self.assertEqual(report["hit_count"], 1)

        learned_path = ARCHIVE / "SMART_SIGNAL_STATE_3068_LEARNED.json"
        learned = json.loads(learned_path.read_text())
        self.assertEqual(learning["source_freeze_sha256"], frozen_sha)
        self.assertEqual(learned["source_freeze_sha256"], frozen_sha)
        self.assertEqual(learned["last_contest"], 3068)
        self.assertTrue(learned["learning_after_adjudication"])
        self.assertTrue(learning["uses_target_result_only_after_adjudication"])
        self.assertFalse(learning["retroactive_rewrite"])
        self.assertFalse(proof["retroactive_rewrite"])
        mission = json.loads((ROOT / "SMART_MISSION_STATUS.json").read_text())
        self.assertEqual(mission["scientific_predictive_status"], "UNPROVEN")
        self.assertIs(mission["terminal_6of6_proven"], False)


if __name__ == "__main__":
    unittest.main()

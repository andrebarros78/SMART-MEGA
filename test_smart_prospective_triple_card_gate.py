"""Tests for read-only preregistration of the three predictive decision heads."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from smart_prospective_triple_card_gate import (
    SCHEMA, candidate_from_frozen_event, evaluate_post_result_diagnostic, preflight, protocol,
)


ROOT = Path(__file__).resolve().parent


def fixture():
    ledger = json.loads((ROOT / "SMART_SIGNAL_LEDGER.json").read_text(encoding="utf-8-sig"))
    old = next(e for e in ledger["events"] if e.get("target_contest") == 3068
               and e.get("event_type") == "FREEZE")
    # Engineering-only synthetic template. Never insert in real ledger or
    # represent this as a 3070 prediction or real frozen card.
    event = deepcopy(old)
    event["target_contest"] = 3070
    event["cutoff_contest"] = 3069
    event["primary_card"]["target_contest"] = 3070
    event["primary_card"]["cutoff_contest"] = 3069
    return event, {"schema": "SMART_SIGNAL_LEDGER_1", "events": [event]}


class PreRegistrationGateTests(unittest.TestCase):
    def test_predeclared_protocol_file_is_byte_semantically_identical(self):
        recorded = json.loads(
            (ROOT / "SMART_PROSPECTIVE_TRIPLE_CARD_PROTOCOL_20261013.json")
            .read_text(encoding="utf-8-sig")
        )
        self.assertEqual(recorded, protocol())

    def test_synthetic_post_result_scores_all_three_heads_without_promotion(self):
        event, ledger = fixture()
        precommit = candidate_from_frozen_event(event, ledger, completed_contest=3069)
        fake_adjudication = {
            "event_type": "ADJUDICATION",
            "target_contest": 3070,
            "created_utc": "2026-10-20T00:00:00+00:00",
            "actual_numbers": [7, 10, 39, 40, 43, 57],
        }
        diagnostic = evaluate_post_result_diagnostic(precommit, fake_adjudication)
        self.assertEqual(diagnostic["status"], "HISTORICAL_DIAGNOSTIC_ONLY_NOT_PROSPECTIVE_PROOF")
        self.assertEqual(diagnostic["challenger_minus_champion_hits"],
                         diagnostic["challenger_hits"] - diagnostic["champion_hits"])
        self.assertEqual(diagnostic["primary_minus_champion_hits"],
                         diagnostic["primary_card_hits"] - diagnostic["champion_hits"])
        self.assertIs(diagnostic["promotion_authorized"], False)
        self.assertIs(diagnostic["independent_git_publication_verified"], False)

    def test_post_result_rejects_altered_commitment_and_forged_target(self):
        event, ledger = fixture()
        precommit = candidate_from_frozen_event(event, ledger, completed_contest=3069)
        fake_adjudication = {
            "event_type": "ADJUDICATION",
            "target_contest": 3070,
            "created_utc": "2026-10-20T00:00:00+00:00",
            "actual_numbers": [7, 10, 39, 40, 43, 57],
        }
        modified = deepcopy(precommit)
        modified["primary_card"] = [1, 2, 3, 4, 5, 6]
        with self.assertRaisesRegex(ValueError, "candidate commitment"):
            evaluate_post_result_diagnostic(modified, fake_adjudication)
        forged = deepcopy(fake_adjudication)
        forged["target_contest"] = 3071
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            evaluate_post_result_diagnostic(precommit, forged)
        forged = deepcopy(fake_adjudication)
        forged["created_utc"] = "2020-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "cannot predate"):
            evaluate_post_result_diagnostic(precommit, forged)

    def test_live_project_is_hold_not_an_authorized_experiment(self):
        status = preflight(ROOT)
        self.assertEqual(status["target_contest"], 3070)
        self.assertEqual(status["completed_contest"], 3069)
        self.assertEqual(status["status"], "BLOCKED_BY_OPERATOR_HOLD")
        self.assertEqual(status["active_target_freeze_events"], 0)
        self.assertIs(status["generation_authorized"], False)
        self.assertIs(status["pre_result_git_registration_exists"], False)
        self.assertIs(status["production_promotion_authorized"], False)

    def test_protocol_is_predeclared_and_fingerprint_is_deterministic(self):
        first, second = protocol(), protocol()
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], SCHEMA)
        self.assertEqual(first["comparison_units"],
                         ["champion_top6", "challenger_top6", "primary_card"])
        self.assertEqual(first["reference"]["expected_hits_per_card"], 0.6)
        self.assertEqual(first["minimum_prospective_contests_for_p13_gate"], 20)
        self.assertEqual(first["sequential_e_value_threshold_for_p13_gate"], 10.0)
        digest = first.pop("protocol_sha256")
        serialized = json.dumps(first, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode("utf-8")
        self.assertEqual(digest, hashlib.sha256(serialized).hexdigest())

    def test_synthetic_causal_freeze_creates_only_unpublished_candidate(self):
        event, ledger = fixture()
        candidate = candidate_from_frozen_event(event, ledger, completed_contest=3069)
        self.assertEqual(candidate["target_contest"], 3070)
        self.assertEqual(candidate["champion_top6"], event["champion_top6"])
        self.assertEqual(candidate["challenger_top6"], event["challenger_top6"])
        self.assertEqual(candidate["primary_card"], event["primary_card"]["numbers"])
        self.assertEqual(candidate["status"], "UNPUBLISHED_CANDIDATE_NOT_PROSPECTIVE_EVIDENCE")
        self.assertIs(candidate["promotion_authorized"], False)
        self.assertIs(candidate["result_used"], False)
        self.assertIs(candidate["independent_git_registration_required"], True)

    def test_finished_target_is_not_backfilled(self):
        event, ledger = fixture()
        with self.assertRaisesRegex(ValueError, "must follow"):
            candidate_from_frozen_event(event, ledger, completed_contest=3070)

    def test_result_seen_in_ledger_fails_closed(self):
        event, ledger = fixture()
        ledger["events"].append({"event_type": "ADJUDICATION", "target_contest": 3070})
        with self.assertRaisesRegex(ValueError, "result already observed"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)

    def test_duplicated_freeze_fails_closed(self):
        event, ledger = fixture()
        ledger["events"].append(deepcopy(event))
        with self.assertRaisesRegex(ValueError, "ambiguous freeze"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)

    def test_missing_or_changed_primary_card_fails_closed(self):
        event, ledger = fixture()
        event["primary_card"]["numbers"] = [1, 1, 2, 3, 4, 5]
        with self.assertRaisesRegex(ValueError, "primary card"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)

    def test_primary_result_leakage_is_rejected(self):
        event, ledger = fixture()
        event["primary_card"]["selector"]["result_used"] = True
        with self.assertRaisesRegex(ValueError, "causal freeze"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)

    def test_hash_and_timestamp_contracts_fail_closed(self):
        event, ledger = fixture()
        event["freeze_sha256"] = "not_sha"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)
        event, ledger = fixture()
        event["created_utc"] = "2026-10-13T10:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)

    def test_legacy_freeze_without_primary_is_not_silently_accepted(self):
        event, ledger = fixture()
        event.pop("primary_card")
        with self.assertRaisesRegex(ValueError, "primary card absent"):
            candidate_from_frozen_event(event, ledger, completed_contest=3069)


if __name__ == "__main__":
    unittest.main()

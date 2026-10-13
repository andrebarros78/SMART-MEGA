"""Integration regression: requested cards enter signed post-result reports.

This exercises the real emission path with only unrelated structural-skill
imports stubbed; no remote predictions and no real 3070 card are created.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
import types
import unittest
from unittest.mock import patch

import smart_post_result_report as post
import test_smart_operator_card_requests as fixtures


class OperatorRequestedReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.OperatorCardRequestTests("test_no_cards_without_explicit_request")
        self.fixture.setUp()
        self.root = self.fixture.root

    def tearDown(self):
        self.fixture.tearDown()

    def _report(self, requested):
        for idx in range(requested):
            self.fixture.issue(f"request-{idx + 1}")
        record = json.loads(self.fixture.ledger_path.read_text())
        first_card = self.fixture.root / "runtime" / "learning_epochs" / "operator-fixture" / "SMART_3099_PRIMARY_CARD.json"
        original = json.loads(first_card.read_text())
        record["events"][0]["primary_card"] = {"numbers": original["numbers"]}
        record["events"].append({
            "event_type": "ADJUDICATION", "target_contest": 3099,
            "freeze_sha256": self.fixture.freeze_sha,
            "actual_numbers": [1, 7, 27, 39, 43, 57],
            "created_utc": (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        })
        self.fixture.ledger_path.write_text(json.dumps(record))
        self.fixture.active["state_paths"]["freeze"] = self.fixture.active["freeze_authority"]["file"]
        self.fixture.active["freeze_authority"].update({"target_contest":3099, "cutoff_contest":3098})
        unrelated = types.ModuleType("smart_skill_reconciliation")
        unrelated.reconcile_remaining = lambda structural, root: {
            "status":"UNAVAILABLE_TEST_STUB", "predictive_weight_authorized":False
        }
        with patch.object(post, "_structural_capability_diagnostic",
                          return_value={"status":"UNAVAILABLE_TEST_STUB"}), patch.dict(
                              sys.modules, {"smart_skill_reconciliation":unrelated}):
            first = post.emit_post_result_report(self.root, self.fixture.active)
            repeated = post.emit_post_result_report(self.root, self.fixture.active)
        return first,repeated

    def test_three_operator_requested_cards_reconciled_in_signed_report(self):
        first,second = self._report(3)
        self.assertEqual(first["status"], "EMITTED")
        self.assertEqual(second["status"], "EXISTING_VALID")
        report=first["report"]
        source=report["operator_requested_card_outcomes"]
        self.assertEqual(source["status"],"POST_RESULT_DIAGNOSTIC_RECONCILED")
        self.assertEqual(source["operator_requested_card_count"],3)
        self.assertEqual([row["request_ordinal"] for row in source["results"]],[1,2,3])
        self.assertEqual([row["operator_request_id"] for row in source["results"]],
                         ["request-1","request-2","request-3"])
        self.assertEqual(source["results"][0]["numbers"],[1,2,3,4,21,22])
        self.assertIs(source["prospective_publication_independently_verified"],False)
        self.assertIs(source["model_weight_change_authorized"],False)
        self.assertEqual(first["report_sha256"],second["report_sha256"])
        self.assertEqual(first["report"]["source_fingerprint"],second["report"]["source_fingerprint"])
        actual=set(report["official_result"])
        for row in source["results"]:
            self.assertEqual(row["hits"],len(actual & set(row["numbers"])))
        self.assertEqual(report["generated_card"],[1,2,3,4,21,22])
        self.assertEqual(report["hit_count"],1)

    def test_legacy_report_without_requests_remains_without_optional_field(self):
        first,repeated = self._report(0)
        self.assertEqual(first["status"],"EMITTED")
        self.assertEqual(repeated["status"],"EXISTING_VALID")
        self.assertNotIn("operator_requested_card_outcomes",first["report"])
        self.assertEqual(first["report_sha256"],repeated["report_sha256"])


if __name__ == "__main__":
    unittest.main()

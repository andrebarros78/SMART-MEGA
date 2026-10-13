"""Fail-closed tests for scientific triage. Entirely synthetic fixtures."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from smart_scientific_eligibility_gate import audit, _hash


def fixture(root: Path):
    (root / "runtime").mkdir()
    frozen = {
        "target_contest": 42, "cutoff_contest": 41,
        "frozen_before_result": True, "causal_cutoff": True,
    }
    path = root / "runtime/freeze.json"
    path.write_text(json.dumps(frozen), encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    freeze = {
        "event_type": "FREEZE", "target_contest": 42, "cutoff_contest": 41,
        "created_utc": "2026-10-01T13:00:00+00:00", "freeze_file": "runtime/freeze.json",
        "freeze_sha256": sha, "frozen_before_result": True, "causal_cutoff": True,
    }
    adjudication = {
        "event_type": "ADJUDICATION", "target_contest": 42,
        "created_utc": "2026-10-02T13:00:00+00:00", "freeze_sha256": sha,
        "actual_numbers": [1, 2, 3, 4, 5, 6],
    }
    (root / "SMART_SIGNAL_LEDGER.json").write_text(
        json.dumps({"schema": "SMART_SIGNAL_LEDGER_1", "events": [freeze, adjudication]}),
        encoding="utf-8",
    )
    (root / "SMART_OPERATIONAL_LIFECYCLE.json").write_text(
        json.dumps({"target_contest": 44, "completed_contest": 43, "state": "HOLD"}),
        encoding="utf-8",
    )
    (root / "SMART_NEXT_CYCLE_HOLD.json").write_text(
        json.dumps({"next_target": 44, "completed_contest": 43, "generation_allowed": False}),
        encoding="utf-8",
    )
    (root / "SMART_MISSION_STATUS.json").write_text(
        json.dumps({"status": "MISSION_ACTIVE", "terminal_6of6_proven": False,
                    "scientific_predictive_status": "UNPROVEN"}), encoding="utf-8",
    )
    return freeze, adjudication, path


class ScientificEligibilityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.freeze, self.adjudication, self.path = fixture(self.root)

    def events(self, events):
        (self.root / "SMART_SIGNAL_LEDGER.json").write_text(
            json.dumps({"schema": "SMART_SIGNAL_LEDGER_1", "events": events}), encoding="utf-8",
        )

    def first(self):
        return audit(self.root)["historical_adjudications"][0]

    def test_exact_hash_is_preliminary_not_prospective_proof(self):
        result = audit(self.root)
        self.assertEqual(result["counts"]["freeze_hash_verified"], 1)
        self.assertEqual(self.first()["status"], "HASH_VERIFIED_PRELIMINARY")
        self.assertFalse(self.first()["scientifically_admissible"])
        self.assertFalse(result["scientific_promotion_authorized"])
        self.assertFalse(result["terminal_6of6_proven"])
        self.assertEqual(result["operational_preflight"]["status"], "BLOCKED_BY_OPERATOR_HOLD")
        self.assertFalse(result["operational_preflight"]["generation_authorized"])
        self.assertEqual(result["report_sha256"], _hash({k: v for k, v in result.items() if k != "report_sha256"}))

    def test_missing_and_tampered_original_excluded(self):
        self.path.unlink()
        self.assertEqual(self.first()["reason"], "ORIGINAL_FREEZE_NOT_AVAILABLE")
        self.path.write_text('{"reconstructed":true}', encoding="utf-8")
        self.assertEqual(self.first()["reason"], "ORIGINAL_FREEZE_SHA256_MISMATCH")
        self.assertEqual(audit(self.root)["counts"]["freeze_hash_verified"], 0)

    def test_timestamp_and_causal_cutoff_forgery_excluded(self):
        forged = deepcopy(self.freeze)
        forged["created_utc"] = "2026-10-02T13:00:00+00:00"
        self.events([forged, self.adjudication])
        self.assertEqual(self.first()["reason"], "FREEZE_TIMESTAMP_NOT_EARLIER")
        forged["created_utc"] = self.freeze["created_utc"]
        forged["cutoff_contest"] = 40
        self.events([forged, self.adjudication])
        self.assertEqual(self.first()["reason"], "INVALID_CAUSAL_OR_RESULT_METADATA")

    def test_duplicate_adjudication_cannot_be_double_counted_as_proof(self):
        self.events([self.freeze, self.adjudication, deepcopy(self.adjudication)])
        result = audit(self.root)
        self.assertEqual(result["counts"]["adjudications"], 2)
        self.assertTrue(all(row["reason"] == "DUPLICATE_ADJUDICATION"
                            for row in result["historical_adjudications"]))
        self.assertEqual(result["counts"]["freeze_hash_verified"], 0)
        self.assertEqual(result["counts"]["scientifically_admissible_by_this_gate"], 0)

    def test_path_traversal_and_symlink_escape_excluded(self):
        malicious = deepcopy(self.freeze)
        malicious["freeze_file"] = "../outside/freeze.json"
        self.events([malicious, self.adjudication])
        self.assertEqual(self.first()["reason"], "INVALID_FREEZE_PATH_OR_TIME")
        malicious["freeze_file"] = "runtime/freeze.json"
        self.events([malicious, self.adjudication])
        self.assertEqual(self.first()["status"], "HASH_VERIFIED_PRELIMINARY")

    def test_later_freeze_or_supersede_cannot_hide_history(self):
        later = {"event_type": "SUPERSEDE", "target_contest": 42,
                 "old_freeze_sha256": self.freeze["freeze_sha256"],
                 "new_freeze_sha256": "a" * 64}
        self.events([self.freeze, self.adjudication, later])
        self.assertEqual(self.first()["reason"], "FREEZE_OR_SUPERSEDE_AFTER_ADJUDICATION")

    def test_authority_mismatch_fails_closed(self):
        (self.root / "SMART_NEXT_CYCLE_HOLD.json").write_text(
            json.dumps({"next_target": 45, "completed_contest": 43, "generation_allowed": True}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            audit(self.root)

    def test_terminal_claim_fails_closed(self):
        (self.root / "SMART_MISSION_STATUS.json").write_text(
            json.dumps({"status": "MISSION_PROVEN", "terminal_6of6_proven": True,
                        "scientific_predictive_status": "PROVEN"}), encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "mission authority inconsistent"):
            audit(self.root)


if __name__ == "__main__":
    unittest.main()

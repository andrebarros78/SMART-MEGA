"""A result is ingested with one guarded invocation, not full product recertification."""
import json
import tempfile
import unittest
from pathlib import Path

from smart_fast_result_ingest import ingest_result


class TestFastResultIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.batch = self.root / "batch.json"
        self.batch.write_text("{}", encoding="utf-8")
        self.steps = []

    def handlers(self, state="HOLD", current=3073, completed=3072, fail_complete=False):
        lifecycle = {"state": state, "target_contest": current, "completed_contest": completed}
        def complete(root, target):
            self.steps.append(("complete", target))
            if fail_complete:
                return {"status": "WAITING_FOR_RESULT"}
            lifecycle["state"] = "ADJUDICATED"
            return {"status": "POST_RESULT_OPERATIONALLY_COMPLETED"}
        def catch_up(root, target, path):
            self.steps.append(("catch_up", target, Path(path).name))
            lifecycle.update(state="HOLD", target_contest=target+1, completed_contest=target)
            return {"status": "CAUGHT_UP_TO_HOLD", "through_target": target,
                    "prediction_authority_created": False, "generation_authority_created": False}
        def register(root, target, path):
            self.steps.append(("register", target, Path(path).name))
            return {"status": "OPERATOR_RESULT_REGISTERED"}
        return {
            "lifecycle": lambda root: dict(lifecycle),
            "batch": lambda path: ({3073: {"numero": 3073, "dataApuracao": "22/10/2026",
                    "listaDezenas": ["01", "02", "03", "04", "05", "06"]}},
                    {"raw_api_independently_verified": False}),
            "complete": complete, "catch_up": catch_up, "register": register,
        }

    def test_lazy_native_handlers_do_not_load_heavy_operator_in_readonly_plan(self):
        from smart_fast_result_ingest import _native_handlers
        handlers = _native_handlers()
        self.assertEqual(set(handlers), {"lifecycle", "batch", "register", "complete", "catch_up"})
        self.assertTrue(all(callable(fn) for fn in handlers.values()))

    def test_hold_single_command_catches_up_without_generation(self):
        result = ingest_result(self.root, 3073, self.batch, handlers=self.handlers())
        self.assertEqual(result["status"], "INGESTED_TO_HOLD")
        self.assertEqual(result["next_target"], 3074)
        self.assertFalse(result["prediction_authority_created"])
        self.assertEqual(self.steps, [("catch_up", 3073, "batch.json")])

    def test_frozen_current_registers_and_completes_before_catchup(self):
        result = ingest_result(self.root, 3073, self.batch,
                               handlers=self.handlers(state="FROZEN"))
        self.assertEqual(result["status"], "INGESTED_TO_HOLD")
        self.assertEqual([x[0] for x in self.steps], ["register", "complete", "catch_up"])
        self.assertEqual(json.loads((self.root / "SMART_OPERATOR_RESULT_INPUT_3073.json").read_text())["numbers"], [1,2,3,4,5,6])

    def test_dry_run_is_readonly(self):
        result = ingest_result(self.root, 3073, self.batch,
                               handlers=self.handlers(state="FROZEN"), dry_run=True)
        self.assertEqual(result["status"], "READY_TO_INGEST")
        self.assertEqual(self.steps, [])
        self.assertFalse((self.root / "SMART_OPERATOR_RESULT_INPUT_3073.json").exists())

    def test_waiting_previous_result_never_catches_up(self):
        handlers = self.handlers(state="FROZEN", current=3072, completed=3071, fail_complete=True)
        with self.assertRaisesRegex(ValueError, "previous result"):
            ingest_result(self.root, 3073, self.batch, handlers=handlers)
        self.assertEqual(self.steps, [("complete", 3072)])

    def test_rejects_wrong_target_before_mutation(self):
        with self.assertRaisesRegex(ValueError, "batch target"):
            ingest_result(self.root, 3074, self.batch, handlers=self.handlers())
        self.assertEqual(self.steps, [])

    def test_rejects_outside_and_symlink(self):
        with self.assertRaisesRegex(ValueError, "inside project"):
            ingest_result(self.root, 3073, "../outside.json", handlers=self.handlers())
        outside = self.root / "link.json"
        try:
            outside.symlink_to(self.batch)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        with self.assertRaisesRegex(ValueError, "symlink"):
            ingest_result(self.root, 3073, outside, handlers=self.handlers())

    def test_prior_frozen_is_closed_before_ingesting_new_target(self):
        result = ingest_result(self.root, 3073, self.batch,
                               handlers=self.handlers(state="FROZEN", current=3072, completed=3071))
        self.assertEqual(result["status"], "INGESTED_TO_HOLD")
        self.assertEqual(self.steps, [
            ("complete", 3072), ("catch_up", 3073, "batch.json")
        ])

    def test_batch_missing_requested_target_blocks_before_mutating(self):
        handlers = self.handlers()
        handlers["batch"] = lambda path: ({3072: {"numero": 3072}}, {})
        with self.assertRaisesRegex(ValueError, "batch target"):
            ingest_result(self.root, 3073, self.batch, handlers=handlers)
        self.assertEqual(self.steps, [])

    def test_conflicting_operator_input_fails_before_registration(self):
        source = self.root / "SMART_OPERATOR_RESULT_INPUT_3073.json"
        source.write_text('{"numbers":[10,11,12,13,14,15]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            ingest_result(self.root, 3073, self.batch,
                          handlers=self.handlers(state="FROZEN"))
        self.assertEqual(self.steps, [])

    def test_already_ingested_is_proven_and_does_not_rewrite(self):
        import hashlib
        from smart_fast_result_ingest import _hash_body
        canonical = self.root / "Mega-Sena.xlsx"
        canonical.write_bytes(b"verified-history-for-test")
        proof = {"schema": "SMART_MISSED_TARGET_CATCHUP_1",
                 "target_contest": 3073, "official_result": [1,2,3,4,5,6],
                 "result_used_for_prediction": False}
        hold = {"schema": "SMART_NEXT_CYCLE_HOLD_1", "next_target": 3074,
                "completed_contest": 3073, "canonical_sha256_at_review":
                hashlib.sha256(canonical.read_bytes()).hexdigest()}
        for name, body in [
            ("SMART_MISSED_TARGET_RECOVERY_3073.json", proof),
            ("SMART_NEXT_CYCLE_HOLD.json", hold),
        ]:
            body["sha256"] = _hash_body(body)
            (self.root / name).write_text(json.dumps(body), encoding="utf-8")
        outcome = ingest_result(self.root, 3073, self.batch,
            handlers=self.handlers(state="HOLD", current=3074, completed=3073))
        self.assertEqual(outcome["status"], "ALREADY_INGESTED")
        self.assertEqual(self.steps, [])
        proof["official_result"] = [7,8,9,10,11,12]
        proof["sha256"] = _hash_body({k:v for k,v in proof.items() if k!="sha256"})
        (self.root / "SMART_MISSED_TARGET_RECOVERY_3073.json").write_text(json.dumps(proof), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            ingest_result(self.root, 3073, self.batch,
                handlers=self.handlers(state="HOLD", current=3074, completed=3073))

    def test_no_implicit_generation_when_unready(self):
        with self.assertRaisesRegex(ValueError, "unsupported lifecycle"):
            ingest_result(self.root, 3073, self.batch,
                          handlers=self.handlers(state="PREPARED"))
        self.assertEqual(self.steps, [])


if __name__ == "__main__":
    unittest.main()

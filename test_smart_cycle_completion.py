"""Product regression: resolve frozen result -> contiguous catch-up -> MODEL card."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import smart_cycle_completion as cycle


class TestCycleCompletion(unittest.TestCase):
    def context(self, state="FROZEN", previous=3071):
        state_record = {"state": state, "target_contest": previous,
                        "completed_contest": previous - 1}
        calls = []
        selected_card = {"status": "FROZEN_MODEL_CARD_VERIFIED",
                         "target_contest": 3073, "numbers": [2, 11, 20, 34, 43, 60],
                         "result_used_in_generation": False}
        batch = ({3072: {"numero": 3072, "listaDezenas": ["02", "06", "09", "16", "31", "40"]}},
                 {"authority": "CAIXA_API_BATCH_CLAIM_UNVERIFIED_TRANSPORT",
                  "raw_api_independently_verified": False, "targets": [3072]})

        def lifecycle(root):
            return dict(state_record)

        def previously_registered(root, contest):
            calls.append(("result-check", contest))
            return {"target_contest": contest, "actual_numbers": [12, 22, 41, 45, 51, 52]}

        def validate_batch(path):
            calls.append(("batch-check", path))
            return batch

        def finish(root, contest):
            calls.append(("complete-result", contest))
            state_record.update(state="ADJUDICATED", target_contest=contest)
            return {"status": "POST_RESULT_OPERATIONALLY_COMPLETED", "next_target": contest + 1}

        def catchup(root, contest, file):
            calls.append(("catch-up", contest, file))
            state_record.update(state="HOLD", target_contest=contest + 1,
                                completed_contest=contest)
            return {"status": "CAUGHT_UP_TO_HOLD", "next_target": contest + 1}

        def generate(root, contest):
            calls.append(("generate", contest))
            state_record.update(state="FROZEN", target_contest=contest)
            return {"status": "FROZEN"}

        def show(root, contest):
            calls.append(("read-model", contest))
            return dict(selected_card, target_contest=contest)

        handlers = cycle.CycleHandlers(
            lifecycle=lifecycle, previous_result=previously_registered,
            read_batch=validate_batch, complete_result=finish,
            catch_up=catchup, generate=generate, read_card=show,
        )
        return handlers, calls, state_record, batch

    def test_3071_frozen_to_3073_model_generation_is_one_command(self):
        with TemporaryDirectory() as root:
            handlers, calls, state, _ = self.context()
            result = cycle.complete_to_model_card(Path(root), 3073, "official-batch.json", handlers)
        self.assertEqual(result["status"], "MODEL_CARD_GENERATED")
        self.assertEqual(result["card"]["target_contest"], 3073)
        self.assertEqual(calls, [
            ("result-check", 3071), ("batch-check", "official-batch.json"),
            ("complete-result", 3071), ("catch-up", 3072, "official-batch.json"),
            ("generate", 3073), ("read-model", 3073),
        ])
        self.assertEqual(state["state"], "FROZEN")

    def test_missing_result_does_not_mutate_anything(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.previous_result = lambda *_: (_ for _ in ()).throw(FileNotFoundError("3071"))
            result = cycle.complete_to_model_card(Path(root), 3073, "official-batch.json", handlers)
        self.assertEqual(result["status"], "WAITING_PREVIOUS_RESULT")
        self.assertEqual(calls, [])

    def test_missing_batch_blocks_before_mutation(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            with self.assertRaisesRegex(ValueError, "batch"):
                cycle.complete_to_model_card(Path(root), 3073, None, handlers)
        self.assertEqual(calls, [])

    def test_incomplete_batch_blocks_before_mutation(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda p: ({}, {"authority": "CAIXA_LOTERIAS_OFFICIAL_API", "targets": []})
            with self.assertRaisesRegex(ValueError, "missing"):
                cycle.complete_to_model_card(Path(root), 3073, "official-batch.json", handlers)
        self.assertEqual(calls, [("result-check", 3071)])

    def test_resume_from_adjudicated_stage(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context("ADJUDICATED")
            result = cycle.complete_to_model_card(Path(root), 3073, "official-batch.json", handlers)
        self.assertEqual(result["status"], "MODEL_CARD_GENERATED")
        self.assertNotIn(("result-check", 3071), calls)

    def test_resume_from_hold_without_repeating_consumed_result(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context("HOLD", previous=3073)
            result = cycle.complete_to_model_card(Path(root), 3073, None, handlers)
        self.assertEqual(result["status"], "MODEL_CARD_GENERATED")
        self.assertEqual(calls, [("generate", 3073), ("read-model", 3073)])

    def test_existing_frozen_current_card_replayed_without_mutation(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context("FROZEN", previous=3073)
            result = cycle.complete_to_model_card(Path(root), 3073, None, handlers)
        self.assertEqual(result["status"], "MODEL_CARD_ALREADY_FROZEN")
        self.assertEqual(calls, [("read-model", 3073)])

    def test_prevent_target_skip_with_unverified_batch(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda p: ({
                3072: {"numero": 3072},
                3074: {"numero": 3074}}, {"authority": "CAIXA_LOTERIAS_OFFICIAL_API"})
            with self.assertRaisesRegex(ValueError, "contiguous"):
                cycle.complete_to_model_card(Path(root), 3075, "batch.json", handlers)
        self.assertNotIn(("complete-result", 3071), calls)

    def test_does_not_accept_existing_old_card_as_new_target(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_card = lambda root, t: {"status": "FROZEN_MODEL_CARD_VERIFIED",
                                                  "target_contest": 3071, "numbers": [1, 2, 3, 4, 5, 6]}
            with self.assertRaisesRegex(RuntimeError, "wrong target"):
                cycle.complete_to_model_card(Path(root), 3073, "batch.json", handlers)
        self.assertEqual(calls[-1], ("generate", 3073))

    def test_lower_authority_public_portal_is_operational_not_api_certified(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda path: (
                {3072: {"numero": 3072, "source": "CAIXA_PORTAL_TRANSCRIPTION"}},
                {"authority": "CAIXA_PUBLIC_PORTAL_TRANSCRIPTION_NOT_API_VERIFIED",
                 "raw_api_independently_verified": False, "targets": [3072]})
            result = cycle.complete_to_model_card(Path(root), 3073, "portal.json", handlers)
        self.assertEqual(result["status"], "MODEL_CARD_GENERATED")
        self.assertIn(("complete-result", 3071), calls)

    def test_public_crosscheck_accepted_operationally_without_api_certification(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda path: (
                {3072: {"numero": 3072, "source": "PUBLIC_CROSSCHECK_UNVERIFIED_OFFICIAL"}},
                {"authority": "TWO_PUBLIC_SOURCES_NOT_CAIXA_API_VERIFIED",
                 "raw_api_independently_verified": False, "targets": [3072]})
            result = cycle.complete_to_model_card(Path(root), 3073, "public.json", handlers)
        self.assertEqual(result["status"], "MODEL_CARD_GENERATED")
        self.assertIn(("catch-up", 3072, "public.json"), calls)

    def test_public_crosscheck_falsely_api_verified_is_rejected(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda path: (
                {3072: {"numero": 3072, "source": "PUBLIC_CROSSCHECK_UNVERIFIED_OFFICIAL"}},
                {"authority": "TWO_PUBLIC_SOURCES_NOT_CAIXA_API_VERIFIED",
                 "raw_api_independently_verified": True, "targets": [3072]})
            with self.assertRaisesRegex(ValueError, "non-API-verified"):
                cycle.complete_to_model_card(Path(root), 3073, "public.json", handlers)
        self.assertNotIn(("complete-result", 3071), calls)

    def test_portal_impostor_cannot_claim_api_verification(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda path: (
                {3072: {"numero": 3072, "source": "CAIXA_PORTAL_TRANSCRIPTION"}},
                {"authority": "CAIXA_PUBLIC_PORTAL_TRANSCRIPTION_NOT_API_VERIFIED",
                 "raw_api_independently_verified": True, "targets": [3072]})
            with self.assertRaisesRegex(ValueError, "non-API-verified"):
                cycle.complete_to_model_card(Path(root), 3073, "portal.json", handlers)
        self.assertNotIn(("complete-result", 3071), calls)

    def test_local_api_claim_is_operational_but_not_independently_verified(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda path: (
                {3072: {"numero": 3072, "source": "CAIXA_CONTEST_API"}},
                {"authority": "CAIXA_API_BATCH_CLAIM_UNVERIFIED_TRANSPORT",
                 "declared_authority": "CAIXA_LOTERIAS_OFFICIAL_API",
                 "raw_api_independently_verified": False,
                 "official_transport_attested": False, "targets": [3072]})
            result = cycle.complete_to_model_card(
                Path(root), 3073, "local-claim.json", handlers
            )
        self.assertEqual(result["status"], "MODEL_CARD_GENERATED")
        self.assertIn(("catch-up", 3072, "local-claim.json"), calls)

    def test_self_declared_caixa_api_authority_cannot_bypass_provenance(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda _: (
                {3072: {"numero": 3072, "source": "CAIXA_CONTEST_API"}},
                {"authority": "CAIXA_LOTERIAS_OFFICIAL_API",
                 "raw_api_independently_verified": True, "targets": [3072]})
            with self.assertRaisesRegex(ValueError, "self-declared|transport"):
                cycle.complete_to_model_card(
                    Path(root), 3073, "untrusted-batch.json", handlers
                )
        self.assertNotIn(("complete-result", 3071), calls)

    def test_downgraded_batch_rejects_fabricated_verified_flag(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.read_batch = lambda _: (
                {3072: {"numero": 3072, "source": "CAIXA_CONTEST_API"}},
                {"authority": "CAIXA_API_BATCH_CLAIM_UNVERIFIED_TRANSPORT",
                 "raw_api_independently_verified": True, "targets": [3072]})
            with self.assertRaisesRegex(ValueError, "non-API-verified"):
                cycle.complete_to_model_card(
                    Path(root), 3073, "forged-batch.json", handlers
                )
        self.assertNotIn(("complete-result", 3071), calls)

    def test_unconfirmed_complete_result_stops_without_catchup(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            handlers.complete_result = lambda root, contest: {"status": "WAITING_FOR_RESULT"}
            result = cycle.complete_to_model_card(Path(root), 3073, "batch.json", handlers)
        self.assertEqual(result["status"], "WAITING_FOR_RESULT")
        self.assertNotIn(("catch-up", 3072, "batch.json"), calls)

    def test_retroactive_target_is_rejected(self):
        with TemporaryDirectory() as root:
            handlers, calls, _, _ = self.context()
            with self.assertRaisesRegex(ValueError, "retrospective"):
                cycle.complete_to_model_card(Path(root), 3070, None, handlers)
        self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()

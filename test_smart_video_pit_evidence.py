"""TDD for cryptographic content binding, not proof of physical lottery prediction."""
import base64
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from smart_video_pit_evidence import audit_pit_frame_witness


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


class PitFrameWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.frame = self.root / "frame_0001.png"
        # Valid byte identity, not necessarily an independently decoded video frame.
        self.frame.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture-content" * 5)
        self.private = Ed25519PrivateKey.generate()
        pub = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.trusted = {"trusted-observer-1": {
            "ed25519_public_key_hex": pub.hex(),
            "role": "INDEPENDENT_TIMESTAMP_WITNESS",
            "source": "OPERATOR_PINNED_TRUST_ANCHOR",
        }}
        self.checkpoint_digest = hashlib.sha256(b"checkpoint_fixture").hexdigest()
        self.assertion = {
            "checkpoint_sha256": self.checkpoint_digest,
            "schema": "SMART_VIDEO_PIT_FRAME_WITNESS_V1",
            "issuer_id": "trusted-observer-1",
            "target_contest": "3073",
            "source_contest": "3072",
            "observed_utc": "2026-10-21T16:00:00Z",
            "frame_sha256": hashlib.sha256(self.frame.read_bytes()).hexdigest(),
            "frame_basename": self.frame.name,
            "frame_size_bytes": self.frame.stat().st_size,
            "media_sha256": "a" * 64,
            "video_id": "ZP3mCk4_ku0",
            "source_authority": "UNVERIFIED",
            "synthetic": False,
        }

    def signed(self, overrides=None, *, signer=None):
        doc = dict(self.assertion)
        doc.update(overrides or {})
        doc["signature_b64"] = base64.b64encode(
            (signer or self.private).sign(canon(doc))).decode("ascii")
        return doc

    def audit(self, evidence=None, *, frame=None, trust=None):
        return audit_pit_frame_witness(
            frame or self.frame, evidence or self.signed(), trust or self.trusted,
            target_contest="3073",
            cutoff_utc="2026-10-22T12:00:00Z",
            checkpoint_sha256=self.checkpoint_digest,
        )

    def test_valid_trusted_signature_proves_frame_byte_commitment_not_lottery_signal(self):
        result = self.audit()
        self.assertEqual(result["status"], "SIGNED_FRAME_WITNESS_ONLY")
        self.assertTrue(result["frame_hash_verified"])
        self.assertTrue(result["witness_signature_verified"])
        self.assertFalse(result["independent_historical_timestamp_verified"])
        self.assertFalse(result["media_source_authorized"])
        self.assertFalse(result["pit_independently_attested"])
        self.assertEqual(result["predictive_weight"], 0.0)

    def test_modified_frame_is_rejected(self):
        self.frame.write_bytes(self.frame.read_bytes() + b"extra")
        self.assertEqual(self.audit()["status"], "FRAME_CONTENT_MISMATCH")

    def test_forged_backdated_timestamp_is_rejected_by_signature(self):
        forged = self.signed()
        forged["observed_utc"] = "2025-01-01T00:00:00Z"
        self.assertEqual(self.audit(forged)["status"], "WITNESS_SIGNATURE_INVALID")

    def test_another_private_key_cannot_impersonate_trusted_witness(self):
        alt = Ed25519PrivateKey.generate()
        self.assertEqual(self.audit(self.signed(signer=alt))["status"], "WITNESS_SIGNATURE_INVALID")

    def test_post_cutoff_witness_is_rejected_even_when_validly_signed(self):
        late = self.signed({"observed_utc": "2026-10-23T00:00:00Z"})
        self.assertEqual(self.audit(late)["status"], "WITNESS_AFTER_CUTOFF")

    def test_source_contest_cannot_equal_target(self):
        same = self.signed({"source_contest": "3073"})
        self.assertEqual(self.audit(same)["status"], "FUTURE_OR_TARGET_CONTEST")

    def test_checkpoint_digest_mismatch_rejected(self):
        result = audit_pit_frame_witness(
            self.frame, self.signed(), self.trusted,
            target_contest="3073", cutoff_utc="2026-10-22T12:00:00Z",
            checkpoint_sha256="b" * 64,
        )
        self.assertEqual(result["status"], "CHECKPOINT_BINDING_MISMATCH")
        self.assertFalse(result["pit_independently_attested"])

    def test_missing_trusted_issuer_fails_closed(self):
        untrusted = self.signed({"issuer_id": "someone-else"})
        self.assertEqual(self.audit(untrusted)["status"], "WITNESS_NOT_TRUSTED")

    def test_synthetic_path_rejected_before_read(self):
        path = self.root / "SYNTHETIC_ONLY_13"
        path.mkdir()
        copied = path / self.frame.name
        copied.write_bytes(self.frame.read_bytes())
        self.assertEqual(self.audit(frame=copied)["status"], "SYNTHETIC_SOURCE_QUARANTINED")

    def test_result_contamination_rejected(self):
        contaminated = self.signed({"winning_numbers": [1, 2, 3, 4, 5, 6]})
        self.assertEqual(self.audit(contaminated)["status"], "RESULT_CONTAMINATION_REJECTED")

    def test_observed_timestamp_needs_timezone(self):
        naive = self.signed({"observed_utc": "2026-10-21T16:00:00"})
        self.assertEqual(self.audit(naive)["status"], "UNTRUSTED_TIME_FORMAT")

    def test_unknown_new_signal_field_is_not_silently_accepted(self):
        record = self.signed({"future_result_payload": {"winning_numbers": [1, 2, 3]}})
        self.assertEqual(self.audit(record)["status"], "RESULT_CONTAMINATION_REJECTED")

    def test_unexpected_unsigned_metadata_field_is_rejected(self):
        record = self.signed({"model_weight_override": 1.0})
        self.assertEqual(self.audit(record)["status"], "WITNESS_SCHEMA_REJECTED")

    def test_revoked_trust_anchor_rejects_even_correct_signature(self):
        revoked = {"trusted-observer-1": dict(self.trusted["trusted-observer-1"], revoked=True)}
        outcome = audit_pit_frame_witness(
            self.frame, self.signed(), revoked,
            target_contest="3073", cutoff_utc="2026-10-22T12:00:00Z",
            checkpoint_sha256=self.checkpoint_digest,
        )
        self.assertEqual(outcome["status"], "WITNESS_NOT_TRUSTED")

    def test_missing_frame_read_fails_closed(self):
        self.assertEqual(self.audit(frame=self.root / "missing.png")["status"], "FRAME_UNAVAILABLE")

    def test_false_source_permission_claim_rejected(self):
        claim = self.signed({"source_authority": "AUTHORIZED"})
        self.assertEqual(self.audit(claim)["status"], "SOURCE_AUTHORITY_UNPROVEN")


if __name__ == "__main__":
    unittest.main()

"""TDD: official media identity is never equivalent to accessible video frames."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from smart_video_official_media_admission import (
    audit_official_media_admission,
    OFFICIAL_CHANNEL_ID,
)


def canonical_sha(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def write_pointer(path, body):
    document = dict(body, sha256=canonical_sha(body))
    path.write_text(json.dumps(document, sort_keys=True, ensure_ascii=False,
                               indent=2) + "\n", encoding="utf-8")
    return document


class OfficialMediaAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name) / "official"
        self.root.mkdir()
        self.video = "ZP3mCk4_ku0"
        self.queue_body = {
            "schema": "SMART_CAIXA_VISUAL_QUEUE_V1",
            "official_channel_id": OFFICIAL_CHANNEL_ID,
            "checkpoint_dir": str(Path(self.work.name, "actual_source")),
            "records": {"3013": {
                "contest_id": "3013", "video_id": self.video,
                "source_url": f"https://www.youtube.com/watch?v={self.video}",
                "state": "PENDING", "checkpoint_sha256": None,
            }},
            "predictive_weight": 0.0,
            "predictive_evidence": "NOT_ESTABLISHED",
        }
        write_pointer(self.root / "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json",
                      self.queue_body)
        self.gate_body = {
            "schema": "SMART_CAIXA_MEDIA_SOURCE_GATE_V1",
            "official_channel_id": OFFICIAL_CHANNEL_ID,
            "state": "BLOCKED", "reason": "YOUTUBE_SIGN_IN_REQUIRED",
            "evidence_command_id": "netcmd_" + "a" * 32,
            "release_policy": "REQUIRES_AUTHORIZED_SOURCE_ACCESS_PROOF",
            "predictive_weight": 0.0,
        }
        self.gate = write_pointer(
            self.root / "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json", self.gate_body
        )
        history = self.root / "source_gate_history"
        history.mkdir()
        (history / (self.gate["sha256"] + ".json")).write_bytes(
            (self.root / "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json").read_bytes()
        )
        self.probe = {
            "video_id": self.video,
            "watch_http_status": 429,
            "oembed_http_status": 200,
            "watch_command_id": "netcmd_" + "c" * 32,
            "oembed_sha256": "e" * 64,
            "oembed_author_name": "CAIXA",
            "oembed_author_url": "https://www.youtube.com/@caixa",
            "probe_utc": "2026-10-21T18:38:10Z",
            "command_id": "netcmd_" + "b" * 32,
        }

    def test_blocked_gate_overrides_successful_public_metadata_and_claimed_frames(self):
        probe = dict(self.probe, decoded_frames=999, ready=True)
        output = audit_official_media_admission(self.root, "3013", probe=probe)
        self.assertEqual(output["status"], "OFFICIAL_MEDIA_SOURCE_BLOCKED")
        self.assertEqual(output["public_metadata"]["status"], "VERIFIED_METADATA_ONLY")
        self.assertEqual(output["public_metadata"]["watch_http_status"], 429)
        self.assertEqual(output["source_gate_reason"], "YOUTUBE_SIGN_IN_REQUIRED")
        self.assertFalse(output["media_capture_authorized"])
        self.assertFalse(output["checkpoint_generation_authorized"])
        self.assertIsNone(output["physical_frames_verified"])
        self.assertIsNone(output["real_observational_utility"])
        self.assertFalse(output["pit_independently_attested"])
        self.assertEqual(output["predictive_weight"], 0.0)

    def test_missing_block_pointer_fails_closed_not_implicit_authorization(self):
        (self.root / "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json").unlink()
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "SOURCE_AUTHORIZATION_NOT_ATTESTED")
        self.assertFalse(output["checkpoint_generation_authorized"])

    def test_mismatched_video_id_cannot_be_relabelled(self):
        output = audit_official_media_admission(
            self.root, "3013", probe=dict(self.probe, video_id="WRONG_video")
        )
        self.assertEqual(output["status"], "PUBLIC_PROBE_ID_MISMATCH")
        self.assertFalse(output["media_capture_authorized"])

    def test_wrong_channel_rejected_even_if_source_gate_claims_unblocked(self):
        self.queue_body["official_channel_id"] = "U" + "a" * 23
        write_pointer(self.root / "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json",
                      self.queue_body)
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "OFFICIAL_QUEUE_REJECTED")
        self.assertFalse(output["media_capture_authorized"])

    def test_corrupt_source_gate_or_history_fails_closed(self):
        (self.root / "source_gate_history" / (self.gate["sha256"] + ".json")).write_text("tampered")
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "SOURCE_GATE_INTEGRITY_REJECTED")

    def test_corrupt_queue_hash_fails_closed(self):
        pointer = self.root / "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json"
        obj = json.loads(pointer.read_text())
        obj["records"]["3013"]["video_id"] = "fake_fake_1"
        pointer.write_text(json.dumps(obj))
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "OFFICIAL_QUEUE_REJECTED")

    def test_oembed_success_does_not_mask_video_page_rate_limit(self):
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["public_metadata"]["status"], "VERIFIED_METADATA_ONLY")
        self.assertEqual(output["video_access_status"], "HTTP_429_RESTRICTED")
        self.assertIsNone(output["capture_manifest_sha256"])

    def test_public_author_url_impostor_rejected_as_metadata(self):
        probe = dict(self.probe, oembed_author_url="https://www.youtube.com/@impostor")
        output = audit_official_media_admission(self.root, "3013", probe=probe)
        self.assertEqual(output["public_metadata"]["status"], "UNVERIFIED_METADATA")
        self.assertFalse(output["media_capture_authorized"])

    def test_watch_status_requires_its_own_governed_receipt(self):
        probe = dict(self.probe)
        probe.pop("watch_command_id")
        output = audit_official_media_admission(self.root, "3013", probe=probe)
        self.assertEqual(
            output["video_access_status"], "WATCH_RESPONSE_RECEIPT_UNATTESTED"
        )
        self.assertFalse(output["media_capture_authorized"])

    def test_unrecognized_or_future_probe_refused(self):
        probe = dict(self.probe, command_id="unaudited", probe_utc="2099-01-01T00:00:00Z")
        output = audit_official_media_admission(self.root, "3013", probe=probe)
        self.assertEqual(output["public_metadata"]["status"], "UNVERIFIED_METADATA")
        self.assertFalse(output["checkpoint_generation_authorized"])

    def test_synthetic_directory_explicitly_quarantined(self):
        destination = self.root.parent / "SYNTHETIC_ONLY_OFFICIAL_QUEUE_13"
        destination.mkdir()
        output = audit_official_media_admission(
            destination, "3013", probe=self.probe
        )
        self.assertEqual(output["status"], "SYNTHETIC_SOURCE_QUARANTINED")

    def test_cli_blocked_is_nonzero_not_false_green(self):
        import subprocess
        import sys
        run = subprocess.run(
            [sys.executable, "smart_video_official_media_admission.py",
             "--queue-dir", str(self.root), "--contest", "3013"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(
            json.loads(run.stdout)["status"], "OFFICIAL_MEDIA_SOURCE_BLOCKED"
        )

    def test_physical_consumer_official_mode_must_stop_before_copying_checkpoints(self):
        from smart_b2_physical_learning_gate import audit_b2_physical_learning
        physical = Path(self.work.name) / "real_checkpoints"
        physical.mkdir()
        result = audit_b2_physical_learning(
            physical, "3013", "2026-10-21T18:00:00Z",
            expected_count=13, official_queue_dir=self.root, official_probe=self.probe,
        )
        self.assertEqual(result["status"], "OFFICIAL_MEDIA_SOURCE_BLOCKED")
        self.assertEqual(result["physical_files_read"], 0)
        self.assertIsNone(result["observational_utility"])
        self.assertEqual(result["official_media_admission"]["video_access_status"],
                         "HTTP_429_RESTRICTED")
        self.assertEqual(result["predictive_weight"], 0.0)

    def test_html_200_metadata_200_still_never_grants_frame_access(self):
        probe = dict(self.probe, watch_http_status=200)
        output = audit_official_media_admission(self.root, "3013", probe=probe)
        self.assertEqual(
            output["video_access_status"], "HTML_ONLY_NO_FRAME_EVIDENCE"
        )
        self.assertIsNone(output["physical_frames_verified"])
        self.assertFalse(output["media_capture_authorized"])
        self.assertFalse(output["checkpoint_generation_authorized"])

    def test_symlinked_source_gate_pointer_is_rejected(self):
        pointer = self.root / "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json"
        original = self.root / "original-gate.json"
        pointer.rename(original)
        pointer.symlink_to(original)
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "SOURCE_GATE_INTEGRITY_REJECTED")

    def test_source_gate_block_record_cannot_be_relabelled_allowed(self):
        gate = dict(self.gate_body, state="ALLOWED")
        write_pointer(self.root / "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json", gate)
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "SOURCE_GATE_INTEGRITY_REJECTED")

    def test_disagreement_between_queue_id_and_contest_fails_closed(self):
        body = dict(self.queue_body)
        body["records"] = dict(body["records"])
        body["records"]["3013"] = dict(body["records"]["3013"], contest_id="3014")
        write_pointer(self.root / "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json", body)
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "OFFICIAL_QUEUE_REJECTED")

    def test_queue_record_with_result_labels_fails_closed(self):
        self.queue_body["records"]["3013"]["winning_numbers"] = [1, 2, 3, 4, 5, 6]
        write_pointer(self.root / "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json",
                      self.queue_body)
        output = audit_official_media_admission(self.root, "3013", probe=self.probe)
        self.assertEqual(output["status"], "OFFICIAL_QUEUE_REJECTED")


if __name__ == "__main__":
    unittest.main()

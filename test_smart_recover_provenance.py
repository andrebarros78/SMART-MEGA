from pathlib import Path
import gzip
import hashlib
import json

from smart_recover_provenance import recover
from smart_false_negative_rescue import build_profile_from_reports


def test_two_historical_ledgers_recovered_without_promoting_incomplete_feedback():
    root = Path(__file__).resolve().parent
    before = (root / "SMART_OPERATIONAL_LIFECYCLE.json").read_bytes()
    for contest in (3062, 3068):
        proof = recover(root, contest)
        assert proof["status"] == "EXISTING_IDENTICAL"
        archive = root / proof["archive_file"]
        report = json.loads((root / f"SMART_POST_RESULT_REPORT_{contest}.json").read_text(encoding="utf-8-sig"))
        assert hashlib.sha256(gzip.decompress(archive.read_bytes())).hexdigest() == report["process_audit"]["ledger_sha256"]
        assert proof["predictive_promotion_authorized"] is False
    profile = build_profile_from_reports(root, through_contest=3072)
    assert profile["quarantined_reports"] == [
        "SMART_POST_RESULT_REPORT_3060.json",
        "SMART_POST_RESULT_REPORT_3061.json",
    ]
    assert profile["observations"] == 5
    assert profile["quarantined_count"] == 2
    assert (root / "SMART_OPERATIONAL_LIFECYCLE.json").read_bytes() == before

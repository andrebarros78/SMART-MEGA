"""Restore two historic post-adjudication ledgers only when SHA-256 exactly matches.

The original report digests are the authority. No synthetic events or results.
"""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path

RECOVERY_FORMATS = {3062: "CRLF", 3068: "LF"}
TAIL_EVENT_TYPES = ("LEARNING_UPDATE", "SEQUENTIAL_PROOF")


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def recover(root: Path, contest: int) -> dict:
    root = root.resolve()
    if contest not in RECOVERY_FORMATS:
        raise ValueError("unsupported historical recovery contest")
    report = json.loads((root / f"SMART_POST_RESULT_REPORT_{contest}.json").read_text(encoding="utf-8-sig"))
    body = dict(report)
    asserted_report_sha = body.pop("sha256")
    if asserted_report_sha != _sha(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")):
        raise ValueError("report self-hash mismatch")
    audit = report["process_audit"]
    expected = audit["ledger_sha256"]
    ledger_path = (root / audit["ledger"]).resolve()
    if not ledger_path.is_relative_to(root) or ledger_path.is_symlink():
        raise ValueError("unsafe ledger path")
    live = ledger_path.read_bytes()
    document = json.loads(live.decode("utf-8-sig"))
    events = document["events"]
    if [(e["event_type"], e["target_contest"]) for e in events[-2:]] != [
        (name, contest) for name in TAIL_EVENT_TYPES
    ]:
        raise ValueError("ledger lacks the expected two post-report events")
    historical = dict(document)
    historical["events"] = events[:-2]
    recovered_bytes = json.dumps(historical, ensure_ascii=False, indent=2).encode("utf-8")
    if RECOVERY_FORMATS[contest] == "CRLF":
        recovered_bytes = recovered_bytes.replace(b"\n", b"\r\n")
    actual = _sha(recovered_bytes)
    if actual != expected:
        raise ValueError(f"recovered source digest differs from signed report: {contest}")
    destination = root / "SMART_STATE_ARCHIVE" / "hash-bound-learning" / str(contest) / f"SMART_SIGNAL_LEDGER.{expected}.json.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob = gzip.compress(recovered_bytes, compresslevel=9, mtime=0)
    if destination.exists():
        if destination.is_symlink() or gzip.decompress(destination.read_bytes()) != recovered_bytes:
            raise FileExistsError("historical witness already exists with different bytes")
        status = "EXISTING_IDENTICAL"
    else:
        with destination.open("xb") as output:
            output.write(blob)
        status = "RECOVERED_SHA256_EXACT"
    if _sha(gzip.decompress(destination.read_bytes())) != expected:
        raise RuntimeError("persisted archive SHA-256 verification failed")
    return {
        "contest": contest,
        "status": status,
        "source_ledger_sha256": _sha(live),
        "original_report_sha256": asserted_report_sha,
        "original_ledger_sha256_recovered": actual,
        "events_preserved": len(historical["events"]),
        "later_events_not_in_recovered_snapshot": list(TAIL_EVENT_TYPES),
        "encoding": RECOVERY_FORMATS[contest],
        "archive_file": str(destination.relative_to(root)).replace("\\", "/"),
        "archive_sha256": _sha(destination.read_bytes()),
        "predictive_promotion_authorized": False,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    for contest in sorted(RECOVERY_FORMATS):
        print(json.dumps(recover(root, contest), ensure_ascii=False, sort_keys=True), flush=True)

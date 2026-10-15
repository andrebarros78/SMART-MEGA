"""Failure/recovery guards for a real, hash-chained rollover journal."""
from __future__ import annotations

import hashlib
import json

import pytest

import smart_rollover
from smart_transaction_journal import (
    TransactionJournalError,
    begin,
    committed,
    committing,
    prepared,
    read_entries,
)


def _hashed(root, *, complete: bool):
    review = root / "SMART_POST_RESULT_REVIEW_120.json"
    review.write_text('{"reviewed":true}\n', encoding="utf-8")
    data = root / "Mega-Sena.xlsx"
    data.write_bytes(b"validated-history-through-120")
    doc = {
        "schema": "SMART_NEXT_CYCLE_HOLD_1",
        "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
        "completed_contest": 120 if complete else 119,
        "next_target": 121 if complete else 120,
        "automatic_prepare_forbidden": True,
        "prepare_allowed": False,
        "review_file": review.name,
        "review_file_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "canonical_sha256_at_review": hashlib.sha256(data.read_bytes()).hexdigest(),
    }
    doc["sha256"] = hashlib.sha256(
        json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (root / "SMART_NEXT_CYCLE_HOLD.json").write_text(json.dumps(doc), encoding="utf-8")


def _isolate(monkeypatch):
    monkeypatch.setattr(smart_rollover, "assert_reconciled", lambda *args, **kwargs: {})
    monkeypatch.setattr(smart_rollover, "assert_state", lambda *args, **kwargs: {"sha256": "f" * 64})
    monkeypatch.setattr(smart_rollover, "update_current_process_lock", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        smart_rollover, "archive_completed_epoch",
        lambda *args: {"status": "ARCHIVED", "archive_manifest": "archive.json",
                       "archive_manifest_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        smart_rollover, "transition",
        lambda *args, **kwargs: {"state": "HOLD", "target_contest": 121, "sha256": "b" * 64},
    )


def _run(root):
    # The decorator enforces a canonical production root/lock. Only the
    # deterministic transaction body runs in this isolated unit test.
    return smart_rollover.canonical_rollover.__wrapped__(root, 120)


def test_rollover_recovers_after_bad_hold_with_distinct_retry_transaction(tmp_path, monkeypatch):
    _isolate(monkeypatch)
    _hashed(tmp_path, complete=False)
    with pytest.raises(smart_rollover.RolloverError, match="target sequence mismatch"):
        _run(tmp_path)
    initial = read_entries(tmp_path)
    assert [e["phase"] for e in initial] == ["BEGIN", "ROLLED_BACK"]
    assert {e["transaction_id"] for e in initial} == {"ROLLOVER:120:121"}

    _hashed(tmp_path, complete=True)
    committed_result = _run(tmp_path)
    assert committed_result["status"] == "ROLLOVER_COMMITTED"
    entries = read_entries(tmp_path)  # validates every chain link
    assert [e["phase"] for e in entries[2:]] == [
        "BEGIN", "PREPARED", "COMMITTING", "COMMITTED"
    ]
    assert {e["transaction_id"] for e in entries[2:]} == {"ROLLOVER:120:121:retry:2"}
    assert committed_result["transaction_id"] == "ROLLOVER:120:121:retry:2"


def test_repeated_rollback_requires_explicit_new_attempt_each_time(tmp_path, monkeypatch):
    _isolate(monkeypatch)
    _hashed(tmp_path, complete=False)
    for _ in range(2):
        with pytest.raises(smart_rollover.RolloverError, match="target sequence mismatch"):
            _run(tmp_path)
    _hashed(tmp_path, complete=True)
    assert _run(tmp_path)["transaction_id"] == "ROLLOVER:120:121:retry:3"
    entries = read_entries(tmp_path)
    assert [e["phase"] for e in entries if e["transaction_id"].endswith("retry:2")] == ["BEGIN", "ROLLED_BACK"]


@pytest.mark.parametrize("phase", ["BEGIN", "PREPARED", "COMMITTING", "COMMITTED"])
def test_rollover_never_replays_live_or_committed_transactions(tmp_path, monkeypatch, phase):
    _isolate(monkeypatch)
    _hashed(tmp_path, complete=True)
    tx = "ROLLOVER:120:121"
    begin(tmp_path, tx, "ROLLOVER", target_contest=120)
    if phase != "BEGIN":
        prepared(tmp_path, tx, "ROLLOVER", target_contest=120)
    if phase in {"COMMITTING", "COMMITTED"}:
        committing(tmp_path, tx, "ROLLOVER", target_contest=120)
    if phase == "COMMITTED":
        committed(tmp_path, tx, "ROLLOVER", target_contest=120)
    before = read_entries(tmp_path)
    with pytest.raises((smart_rollover.RolloverError, TransactionJournalError)):
        _run(tmp_path)
    assert read_entries(tmp_path) == before

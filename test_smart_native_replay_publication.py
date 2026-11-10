"""Crash-safe publication of native research replay snapshots and reports."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest

import smart_native_replay_runner as runner
from smart_native_signal_research import strict_json_loads


def test_interruption_before_publication_can_be_retried(tmp_path, monkeypatch):
    report = {"schema": "CONTROLLED_RESEARCH", "state": "PRE_RESULT", "value": 19}
    path = tmp_path / "RESEARCH_FREEZE.json"
    original_link = runner.os.link

    def failed_link(src, dst):
        raise OSError("injected failure immediately before atomic publication")

    monkeypatch.setattr(runner.os, "link", failed_link)
    with pytest.raises(OSError, match="injected failure"):
        runner._save(path, report)
    assert not path.exists(), "incomplete research freeze became visible"
    monkeypatch.setattr(runner.os, "link", original_link)

    runner._save(path, report)
    runner._save(path, report)
    assert strict_json_loads(path.read_text(encoding="utf-8")) == report
    assert len(list(tmp_path.glob("RESEARCH_FREEZE.json"))) == 1


def test_concurrent_conflicting_snapshot_never_overwrites(tmp_path):
    path = tmp_path / "REPLAY_PRE_RESULT.json"
    barrier = threading.Barrier(2)

    def contender(number):
        doc = {"schema": "FROZEN_EXPERIMENT", "epoch": number}
        barrier.wait(timeout=15)
        try:
            runner._save(path, doc)
            return "success", doc
        except (ValueError, FileExistsError) as exc:
            return "conflict", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcome = list(pool.map(contender, (1, 2)))
    assert sorted(item[0] for item in outcome) == ["conflict", "success"]
    assert strict_json_loads(path.read_text(encoding="utf-8")) == next(
        value for state, value in outcome if state == "success"
    )

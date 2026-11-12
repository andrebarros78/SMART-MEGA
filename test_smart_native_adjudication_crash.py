"""T16: real child termination at the atomic publication boundary, then recovery by the real writer."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from smart_native_signal_research import (
    adjudicate_replay, build_research_challenger, make_contribution,
    strict_json_loads,
)


@pytest.mark.parametrize("step,expected_exit,initial_count", [
    ("before_link", 41, 0),
    ("after_link", 42, 1),
])
def test_forced_process_crash_recovers_without_overwriting(
    tmp_path: Path, step: str, expected_exit: int, initial_count: int,
):
    cutoff = tmp_path / "history-n-minus-one.bin"
    cutoff.write_bytes(b"causally frozen controlled history")
    producer = make_contribution(
        "frontier_gap_hazard",
        {str(n): float(n / 60) for n in range(1, 61)},
        data_path=cutoff, target_contest=505, epoch_id="CRASH-505",
    )
    frozen = build_research_challenger([producer], {"frontier_gap_hazard": 0.05})
    result = {
        "contest": 505, "numbers": [1,2,3,4,5,6],
        "source_sha256": "a" * 64, "source_kind": "HISTORICAL_REPLAY",
    }
    # Compute the receipt with the *real* writer in a separate, isolated
    # folder. A lightweight process then exercises the exact fsync/link crash
    # boundary, avoiding a second pandas/numpy import under host saturation.
    expected = adjudicate_replay(frozen, result, tmp_path / "reference_receipt")
    directory = tmp_path / "receipts"
    directory.mkdir()
    destination = directory / f"REPLAY_505_{frozen['sha256']}.json"
    child_code = """
import json, os, sys
from pathlib import Path
folder=Path(sys.argv[1])
target=Path(sys.argv[2])
receipt=Path(sys.argv[3])
mode=sys.argv[4]
temp=folder / ('.' + target.name + '.' + str(os.getpid()) + '.tmp')
with temp.open('x',encoding='utf-8') as stream:
    stream.write(receipt.read_text(encoding='utf-8'))
    stream.flush()
    os.fsync(stream.fileno())
if mode == 'before_link':
    os._exit(41)
os.link(temp,target)
os._exit(42)
"""
    receipt_path = next((tmp_path / "reference_receipt").glob("REPLAY_*.json"))
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMP"] = str(tmp_path)
    env["TEMP"] = str(tmp_path)
    stdout_log = tmp_path / "child_stdout.log"
    stderr_log = tmp_path / "child_stderr.log"
    with stdout_log.open("wb") as stdout_stream, stderr_log.open("wb") as stderr_stream:
        completed = subprocess.run(
            [sys.executable, "-B", "-c", child_code,
             str(directory), str(destination), str(receipt_path), step],
            cwd=Path(__file__).resolve().parent, env=env,
            stdout=stdout_stream, stderr=stderr_stream,
            timeout=180, check=False,
        )
    assert completed.returncode == expected_exit, stderr_log.read_text(encoding="utf-8")
    assert len(list(directory.glob("REPLAY_*.json"))) == initial_count
    assert len(list(directory.glob(".*.tmp"))) >= 1
    # Parent is a separate process and must recover without re-adjudicating twice.
    once = adjudicate_replay(frozen, result, directory)
    twice = adjudicate_replay(frozen, result, directory)
    assert once == twice == expected
    receipts = list(directory.glob("REPLAY_*.json"))
    assert len(receipts) == 1
    assert strict_json_loads(receipts[0].read_text(encoding="utf-8")) == once
    conflicting = dict(result, numbers=[7,8,9,10,11,12])
    with pytest.raises(ValueError, match="conflict"):
        adjudicate_replay(frozen, conflicting, directory)

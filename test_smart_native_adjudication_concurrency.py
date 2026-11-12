"""Concurrent research receipts must be atomic, idempotent, non-overwriting."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import threading

import smart_native_signal_research as native


def _case(tmp_path):
    data = tmp_path / "cutoff.bin"
    data.write_bytes(b"historical training snapshot")
    signal = native.make_contribution(
        "frontier_gap_hazard",
        {str(n): float(n / 60) for n in range(1, 61)},
        data_path=data, target_contest=201, epoch_id="RACE-201",
    )
    freeze = native.build_research_challenger(
        [signal], {"frontier_gap_hazard": 0.05},
    )
    base = {
        "contest": 201,
        "source_sha256": hashlib.sha256(b"controlled synthetic replay").hexdigest(),
        "source_kind": "HISTORICAL_REPLAY",
    }
    first = {**base, "numbers": [1, 2, 3, 4, 5, 6]}
    second = {**base, "numbers": [7, 8, 9, 10, 11, 12]}
    return freeze, first, second


def test_concurrent_conflicting_adjudications_never_overwrite(tmp_path):
    freeze, first, second = _case(tmp_path)
    start = threading.Barrier(2)
    folder = tmp_path / "receipts"

    def attempt(result):
        start.wait(timeout=20)
        try:
            receipt = native.adjudicate_replay(freeze, result, folder)
            return ("written", receipt)
        except (ValueError, FileExistsError) as exc:
            return ("rejected", str(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (first, second)))

    assert sorted(kind for kind, _ in outcomes) == ["rejected", "written"]
    files = list(folder.glob("REPLAY_*.json"))
    assert len(files) == 1
    stored = native.strict_json_loads(files[0].read_text(encoding="utf-8"))
    assert stored == next(value for status, value in outcomes if status == "written")
    assert stored["result_sha256"] in {
        native.canonical_hash(first), native.canonical_hash(second)
    }


def test_same_result_is_idempotent_after_orphan_temporary_file(tmp_path):
    freeze, first, _ = _case(tmp_path)
    folder = tmp_path / "receipts"
    folder.mkdir()
    orphan = folder / ".interrupted_previous_process.tmp"
    orphan.write_bytes(b"unpublished and deliberately incomplete")
    initial = native.adjudicate_replay(freeze, first, folder)
    repeat = native.adjudicate_replay(freeze, first, folder)
    assert initial == repeat
    assert len(list(folder.glob("REPLAY_*.json"))) == 1
    assert orphan.read_bytes() == b"unpublished and deliberately incomplete"
    # The crash artifact cannot become authority or silently replace the receipt.

"""Read-only replay producer for the 3075 historical paired holdout.

Separate from operative card generation; neither rewrites a frozen card nor
creates predictive authority. Load only the committed F11 baseline engine and
the current candidate engine and freeze the dataset to contest 3074.

The per-draw forecast at contest t uses score[t] computed from X[:t], before
the observed numbers for t. The actual result is used *only* for scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

from smart_paired_trace_guard import paired_sign_test, validate_trace

TARGET = 3075
CUTOFF = TARGET - 1
HOLDOUT_START = 2851
ORIGINAL_ENGINE_SHA256 = "edf434aabe1a140a6b3fdb16aaa332cbc46077545abebd1612b109a6839a074a"
FROZEN_HISTORY_SHA256 = "c87bde2b81af2a4c24800236b323711e7a96184ea7122b8cd958e7b78985caa6"
ORIGINAL_ENGINE_GIT_BLOB = "e5b3c1829158d163cd82785b83421c370e1c93d0"
CANDIDATE_ENGINE_GIT_BLOB = "3b0340fee746a699cf0ea57f265760ebbbd861f0"


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_engine(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ValueError("engine cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def assemble_trace(
    contests, draws, baseline_rows, candidate_rows, *,
    target: int, holdout_start: int,
    baseline_engine_git_blob: str, candidate_engine_git_blob: str,
    snapshot_sha256: str,
) -> dict[str, Any]:
    """Construct only a closed historical PIT trace; verify EVERY forecast."""
    if type(target) is not int or type(holdout_start) is not int or target != 3075:
        raise ValueError("this evidence producer is scoped to historical contest 3075")
    contests = [int(c) for c in contests]
    if (not contests or contests[-1] != target - 1
        or contests[0] > holdout_start - 1
        or len(contests) != len(draws)
        or any(b != a + 1 for a, b in zip(contests, contests[1:]))):
        raise ValueError("PIT history cutoff or chronological continuity invalid")

    before = {int(r["contest"]): r for r in baseline_rows}
    after = {int(r["contest"]): r for r in candidate_rows}
    if len(before) != len(baseline_rows) or len(after) != len(candidate_rows):
        raise ValueError("duplicate or malformed replay contests")
    outcomes = {int(c): [int(v) for v in vals] for c, vals in zip(contests, draws)}
    trace = []
    wins = losses = ties = b_hits = c_hits = 0
    for contest in range(holdout_start, target):
        if contest not in before or contest not in after or contest not in outcomes:
            raise ValueError(f"missing replay: {contest}")
        b_row, c_row = before[contest], after[contest]
        b_top = [int(n) for n in b_row["top6"]]
        c_top = [int(n) for n in c_row["top6"]]
        if (len(b_top) != 6 or len(set(b_top)) != 6 or min(b_top) < 1 or max(b_top) > 60
            or len(c_top) != 6 or len(set(c_top)) != 6 or min(c_top) < 1 or max(c_top) > 60):
            raise ValueError("malformed prediction")
        known = set(outcomes[contest])
        bh = len(set(b_top) & known)
        ch = len(set(c_top) & known)
        if b_row["hits"] != bh or c_row["hits"] != ch:
            raise ValueError("original replay hit counts conflict with the frozen historical outcomes")
        trace.append({
            "contest": contest, "prediction_cutoff": contest - 1,
            "baseline_top6": b_top, "candidate_top6": c_top,
            "baseline_hits": bh, "candidate_hits": ch,
        })
        b_hits += bh
        c_hits += ch
        if ch > bh:
            wins += 1
        elif ch < bh:
            losses += 1
        else:
            ties += 1

    result = {
        "schema": "SMART_PAIRED_HOLDOUT_TRACE_1",
        "target_contest": target,
        "cutoff_contest": target - 1,
        "holdout_start": holdout_start,
        "holdout_end": target - 1,
        "baseline_engine_git_blob": baseline_engine_git_blob,
        "candidate_engine_git_blob": candidate_engine_git_blob,
        "snapshot_sha256": snapshot_sha256,
        "future_result_used": False,
        "promotion_authorized": False,
        "rows": trace,
        "summary": {
            "baseline_hits": b_hits,
            "candidate_hits": c_hits,
            "candidate_wins": wins,
            "baseline_wins": losses,
            "ties": ties,
            "one_sided_p": paired_sign_test(wins, losses),
        },
    }
    verified = validate_trace(
        result, outcomes,
        replay_predictions=[(b["top6"], c["top6"]) for b, c in zip(
            (before[t] for t in range(holdout_start, target)),
            (after[t] for t in range(holdout_start, target)))],
    )
    if verified["status"] != "PASS":
        raise ValueError(f"invalid generated trace: {verified['errors']}")
    return result


def _partition_counts(rows, begin: int, end: int) -> dict[str, int]:
    sample = [r for r in rows if begin <= int(r["contest"]) <= end]
    if len(sample) != end - begin + 1:
        raise ValueError("partition mismatch")
    return {"n": len(sample), "hits": sum(int(r["hits"]) for r in sample)}


def produce(snapshot: Path, baseline_engine: Path, source_root: Path) -> dict[str, Any]:
    """Recompute 3075 shadow history from verified original/candidate sources."""
    snapshot = snapshot.resolve()
    baseline_engine = baseline_engine.resolve()
    source_root = source_root.resolve()
    candidate_engine = source_root / "smart_v2_engine.py"
    if _digest(snapshot) != FROZEN_HISTORY_SHA256:
        raise ValueError("cutoff snapshot changed or may contain future draw")
    if _digest(baseline_engine) != ORIGINAL_ENGINE_SHA256:
        raise ValueError("baseline engine is not the immutable F11 model")
    # The candidate must exactly match its committed Git object.
    blob = subprocess.run(
        ["git", "rev-parse", "HEAD:smart_v2_engine.py"],
        cwd=source_root, text=True, capture_output=True, check=True,
    ).stdout.strip()
    if blob != CANDIDATE_ENGINE_GIT_BLOB:
        raise ValueError("candidate engine commit is not the evaluated PR92 candidate")
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", "smart_v2_engine.py"],
        cwd=source_root, check=True,
    )
    base = _load_engine(baseline_engine, "smart_3075_baseline_v2_read_only")
    candidate = _load_engine(candidate_engine, "smart_3075_candidate_v2_read_only")
    draws, contests = base.load_draws(snapshot)
    if int(contests[-1]) != CUTOFF or len(draws) != CUTOFF:
        raise ValueError("snapshot must include only concursos 1..3074")
    if not all(int(x) == i + 1 for i, x in enumerate(contests)):
        raise ValueError("invalid historical sequence")
    pre_base = base.precompute_scores(base.onehot(draws))
    # Ensure the signal-precomputation implementation has not drifted.
    pre_next = candidate.precompute_scores(candidate.onehot(draws))
    if pre_base.keys() != pre_next.keys():
        raise ValueError("candidate introduces unapproved signal differences")
    import numpy as np
    if not all(np.array_equal(pre_base[k], pre_next[k]) for k in pre_base):
        raise ValueError("score preparation changed: this is not a cap-only comparison")
    orig = base.walk_forward(draws, contests, start=1000, pre=pre_base)
    next_ = candidate.walk_forward(draws, contests, start=1000, pre=pre_next)
    trace = assemble_trace(
        contests, draws, orig.rows, next_.rows,
        target=TARGET, holdout_start=HOLDOUT_START,
        baseline_engine_git_blob=ORIGINAL_ENGINE_GIT_BLOB,
        candidate_engine_git_blob=CANDIDATE_ENGINE_GIT_BLOB,
        snapshot_sha256=FROZEN_HISTORY_SHA256,
    )
    expected = json.loads((source_root/"evidence/3075/SMART_3075_CAP_RETROSPECTIVE_COMPARISON.json").read_text(encoding="utf-8"))
    for name, (first, last) in {
        "calibration": (1500, 2499), "validation": (2500, 2850),
        "holdout": (2851, 3074), "global": (1001, 3074),
    }.items():
        if (_partition_counts(orig.rows, first, last) != expected["baseline"][name]
            or _partition_counts(next_.rows, first, last) != expected["candidate"][name]):
            raise ValueError(f"replayed {name} does not match historical comparison")
    if any(trace["summary"][k] != expected["paired_holdout"][k]
           for k in ("candidate_wins", "baseline_wins", "ties")):
        raise ValueError("signed historical paired summary does not match replay")
    if not math.isclose(trace["summary"]["one_sided_p"],
                        expected["paired_holdout"]["one_sided_sign_test_p"], abs_tol=1e-12):
        raise ValueError("paired significance reported inaccurately")
    trace["metadata"] = {
        "source_baseline_sha256": ORIGINAL_ENGINE_SHA256,
        "frozen_data_sha256": FROZEN_HISTORY_SHA256,
        "window": "2851..3074",
        "algorithmic_lineage": "engines re-executed from pinned original + candidate sources",
        "model_selection_authorized": False,
        "scientific_status": "RETROSPECTIVE_REPLAY_VERIFIED_NOT_PROSPECTIVE",
        "source_head_scoped_to_pr92": CANDIDATE_ENGINE_GIT_BLOB,
    }
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description="PIT 3075 paired replay evidence, SHADOW ONLY")
    parser.add_argument("--frozen-snapshot", type=Path, required=True)
    parser.add_argument("--baseline-engine", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    opts = parser.parse_args()
    doc = produce(opts.frozen_snapshot, opts.baseline_engine, Path(__file__).resolve().parent)
    opts.out.parent.mkdir(parents=True, exist_ok=True)
    opts.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "REPLAY_VERIFIED_SHADOW_ONLY",
        "n": len(doc["rows"]), "counts": doc["summary"],
        "output": str(opts.out), "promotion_authorized": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

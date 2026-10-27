"""Producer is a read-only replay of stored forecasts and frozen outcomes."""
from __future__ import annotations

import pytest
import numpy as np

from smart_paired_trace_replay import assemble_trace
from smart_paired_trace_guard import validate_trace


def fixture():
    contests=np.array([3072,3073,3074])
    draws=np.array([
      [1,2,3,4,5,6],
      [2,3,20,25,39,57],
      [7,10,14,27,36,55],
    ])
    before=[
      {"contest":3073,"top6":[2,3,11,12,30,40],"hits":2},
      {"contest":3074,"top6":[1,7,12,40,50,59],"hits":1},
    ]
    after=[
      {"contest":3073,"top6":[1,3,11,12,30,40],"hits":1},
      {"contest":3074,"top6":[7,10,12,40,50,59],"hits":2},
    ]
    return contests,draws,before,after


def test_assemble_prospectively_scoped_replay_from_independent_predictions():
    contests,draws,before,after=fixture()
    result=assemble_trace(
        contests,draws,before,after,
        target=3075,holdout_start=3073,
        baseline_engine_git_blob="a"*40,
        candidate_engine_git_blob="b"*40,
        snapshot_sha256="f"*64,
    )
    assert result["cutoff_contest"] == 3074
    assert len(result["rows"]) == 2
    assert [r["prediction_cutoff"] for r in result["rows"]] == [3072,3073]
    assert result["summary"]["baseline_hits"] == 3
    assert result["summary"]["candidate_hits"] == 3
    assert result["summary"]["one_sided_p"] == 0.75
    # Validate with an independent replay lineage provided by the caller.
    audit=validate_trace(result,{int(t):list(map(int,d)) for t,d in zip(contests,draws)},
                         replay_predictions=[(x["top6"],y["top6"]) for x,y in zip(before,after)])
    assert audit["status"] == "PASS"
    assert audit["promotion_authorized"] is False


def test_reject_future_contest_before_creating_trace():
    contests,draws,before,after=fixture()
    contests[-1]=3075
    with pytest.raises(ValueError):
        assemble_trace(contests,draws,before,after,target=3075,holdout_start=3073,
            baseline_engine_git_blob="a"*40,candidate_engine_git_blob="b"*40,
            snapshot_sha256="f"*64)


def test_reject_row_order_or_forged_hits():
    contests,draws,before,after=fixture()
    before[0]["hits"]=6
    with pytest.raises(ValueError):
        assemble_trace(contests,draws,before,after,target=3075,holdout_start=3073,
            baseline_engine_git_blob="a"*40,candidate_engine_git_blob="b"*40,
            snapshot_sha256="f"*64)

"""Regressions for the real 3074 operator failure and freeze-bound feedback.

The tests deliberately exercise production entrypoints without creating a live
operational epoch. All artifacts are restricted to pytest's temporary directory.
"""
import json
from pathlib import Path

import smart_champion_challenger as cc
import smart_portfolio_pipeline as spp
from smart_portfolio_optimizer import PortfolioConfig


def test_generation_gate_uses_repository_root_not_callers_cwd(tmp_path, monkeypatch):
    """On 3074 the existing gate was marked 'missing' after the shell used a foreign cwd."""
    import smart_continuous_red_team as rt
    import smart_global_integrity as gi

    calls = []
    monkeypatch.setattr(rt, "verify_latest_report", lambda **kw: calls.append(("red", kw)) or {"status": "PASS"})
    monkeypatch.setattr(gi, "verify_global_integrity", lambda **kw: calls.append(("integrity", kw)) or {"status": "PASS"})
    monkeypatch.chdir(tmp_path)

    result = cc.require_pre_3052_gate(3074)

    assert result["freeze_allowed"] is True
    assert len(result["items"]) == 15
    assert [name for name, _ in calls] == ["red", "integrity"]
    repository_root = Path(cc.__file__).resolve().parent
    assert all(call["root"] == repository_root for _, call in calls)


def test_feedback_profile_is_bound_to_freeze_root_not_import_location(tmp_path, monkeypatch):
    """A sandboxed freeze must never consume unrelated historical feedback."""
    top6 = [1, 2, 21, 22, 41, 42]
    scores = {
        str(number): (float(100 - top6.index(number)) if number in top6 else float(number) / 10000)
        for number in range(1, 61)
    }
    frozen = tmp_path / "freeze.json"
    frozen.write_text(json.dumps({
        "target_contest": 10,
        "cutoff_contest": 9,
        "frozen_before_result": True,
        "champion": {"top6": top6, "aggregate_scores": scores},
    }), encoding="utf-8")

    observed = {}
    def capture(root, config=None, through_contest=None):
        observed["root"] = Path(root).resolve()
        observed["through_contest"] = through_contest
        return None

    monkeypatch.setattr(spp, "build_profile_from_reports", capture)
    result = spp.build_portfolio_package(
        frozen, config=PortfolioConfig(game_count=1, candidate_pool_size=6, time_limit_seconds=5)
    )
    assert result["status"] == "PASS"
    assert observed["root"] == tmp_path.resolve()
    assert observed["through_contest"] == 9

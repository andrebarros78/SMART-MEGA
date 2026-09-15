from pathlib import Path

import pandas as pd
import pytest

import smart_canonical_result_store_reconcile as cr
from smart_v2_engine import load_draws

ROOT = Path(__file__).resolve().parent
FREEZE_SHA = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def _frame(end: int) -> pd.DataFrame:
    rows = []
    columns = ["Concurso", "Data do Sorteio", *[f"Bola{i}" for i in range(1, 7)]]
    for contest in range(1, end + 1):
        numbers = [1, 2, 3, 4, 5, 6] if contest % 2 else [7, 8, 9, 10, 11, 12]
        rows.append([contest, f"{contest:02d}/01/2026", *numbers])
    return pd.DataFrame(rows, columns=columns)


def test_plan_accepts_exact_prefix_and_only_contiguous_suffix(tmp_path: Path):
    canonical = tmp_path / "canonical.xlsx"
    source = tmp_path / "source.xlsx"
    _frame(3).to_excel(canonical, index=False)
    _frame(5).to_excel(source, index=False)
    plan = cr.build_plan(canonical, source, cutoff=5)
    assert plan["prefix_draw_mismatch_count"] == 0
    assert plan["missing_contests"] == [4, 5]
    assert plan["append_count"] == 2
    assert plan["status"] == "READY"


def test_plan_rejects_changed_historical_draw(tmp_path: Path):
    canonical = tmp_path / "canonical.xlsx"
    source = tmp_path / "source.xlsx"
    a = _frame(3)
    b = _frame(5)
    b.loc[b["Concurso"] == 2, "Bola6"] = 13
    a.to_excel(canonical, index=False)
    b.to_excel(source, index=False)
    with pytest.raises(ValueError, match="prefix mismatch"):
        cr.build_plan(canonical, source, cutoff=5)


def test_real_canonical_store_tracks_latest_completed_epoch_and_preserves_prior_freeze():
    import json

    _, contests = load_draws(ROOT / "Mega-Sena.xlsx")
    values = [int(x) for x in contests]
    active = json.loads((ROOT / "SMART_ACTIVE_EPOCH.json").read_text(encoding="utf-8-sig"))
    cutoff = int(active["cutoff_contest"])
    target = int(active["target_contest"])
    snapshot_path = ROOT / active["data_file"]
    _, snapshot_contests = load_draws(snapshot_path)
    snapshot_values = [int(x) for x in snapshot_contests]
    assert target == cutoff + 1
    assert snapshot_values[-1] == cutoff
    assert snapshot_values == list(range(snapshot_values[0], cutoff + 1))
    assert cr.sha256_file(snapshot_path) == active["data_sha256"]
    assert values[: len(snapshot_values)] == snapshot_values
    assert values[-1] in {cutoff, target}
    assert cr.sha256_file(ROOT / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json") == FREEZE_SHA

    prior = json.loads((ROOT / "SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json").read_text(encoding="utf-8"))
    assert prior["final_status"] == "PASS"
    assert prior["result_store_ready_for_next_contest"] is True
    assert prior["freeze_3054_unchanged"] is True

    latest = json.loads((ROOT / "SMART_CANONICAL_HISTORY_ADVANCE_3055.json").read_text(encoding="utf-8"))
    assert latest["status"] == "PASS"
    assert latest["target_contest"] == 3055
    assert latest["canonical_max_after"] == 3055
    assert latest["ready_for_next_target"] == 3056
    assert latest["canonical_prefix_preserved"] is True
    assert latest["future_information_used"] is False
    assert latest["retroactive_rewrite"] is False

    recovery = json.loads((ROOT / "SMART_MISSED_TARGET_RECOVERY_3056.json").read_text(encoding="utf-8-sig"))
    assert recovery["status"] == "RECOVERED_NO_VALID_FREEZE"
    assert recovery["target_contest"] == 3056
    assert recovery["ready_for_next_target"] == 3057
    assert recovery["canonical_sha256_after"] == active["canonical_source_sha256_at_prepare"]
    assert recovery["canonical_sha256_after"] == active["data_sha256"]
    assert recovery["prediction_authority_created"] is False
    assert recovery["prospective_attempt_counted"] is False
    assert recovery["result_used_for_prediction"] is False

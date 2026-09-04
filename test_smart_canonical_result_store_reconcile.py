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


def test_real_canonical_store_is_contiguous_through_3053_and_freeze_unchanged():
    _, contests = load_draws(ROOT / "Mega-Sena.xlsx")
    values = [int(x) for x in contests]
    assert values[-1] == 3053
    assert values == list(range(values[0], 3054))
    assert cr.sha256_file(ROOT / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json") == FREEZE_SHA
    proof = __import__("json").loads((ROOT / "SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json").read_text(encoding="utf-8"))
    assert proof["final_status"] == "PASS"
    assert proof["result_store_ready_for_next_contest"] is True
    assert proof["freeze_3054_unchanged"] is True

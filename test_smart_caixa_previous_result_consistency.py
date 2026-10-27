import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from smart_target_schedule import resolve_target_schedule


def _prepare(root, *, receipt_balls=(7, 10, 14, 27, 36, 55)):
    import shutil
    shutil.copyfile(Path(__file__).parent / "SMART_MEGA_SENA_DRAW_TIME_POLICY.json",
                    root / "SMART_MEGA_SENA_DRAW_TIME_POLICY.json")
    base = root / "Mega-Sena.xlsx"
    pd.DataFrame([{"Concurso": 3075, "Data do Sorteio": datetime(2026, 10, 26),
                   **{f"Bola{i}": n for i, n in enumerate((7, 10, 14, 27, 36, 55), 1)}}]).to_excel(base, index=False)
    source = root / "runtime" / "procedural_sources" / "caixa_api_previous" / "3075.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"numero":3075, "numeroConcursoProximo":3076,
        "dataApuracao":"26/10/2026", "dataProximoConcurso":"27/10/2026",
        "listaDezenas":[str(n).zfill(2) for n in receipt_balls]}), encoding="utf-8")
    return source


def test_caixa_receipt_balls_match_canonical_history(tmp_path):
    _prepare(tmp_path)
    value = resolve_target_schedule(tmp_path, 3076)
    assert value["target_date"] == "27/10/2026"
    assert value["result_used"] is False


def test_caixa_receipt_balls_conflict_with_canonical_history_fails_closed(tmp_path):
    _prepare(tmp_path, receipt_balls=(7, 10, 14, 27, 36, 56))
    with pytest.raises(ValueError, match="CAIXA previous contest balls contradict canonical history"):
        resolve_target_schedule(tmp_path, 3076)

from pathlib import Path

import pandas as pd
import pytest

from smart_rag_excel import SmartExcelRAG, build_preparation_proof

def _frame():
    return pd.DataFrame([
        {"Concurso": 1, "Data do Sorteio": "01/01/2020", "Bola1": 1, "Bola2": 2, "Bola3": 3, "Bola4": 4, "Bola5": 5, "Bola6": 6},
        {"Concurso": 2, "Data do Sorteio": "02/01/2020", "Bola1": 7, "Bola2": 8, "Bola3": 9, "Bola4": 10, "Bola5": 11, "Bola6": 12},
        {"Concurso": 3, "Data do Sorteio": "03/01/2020", "Bola1": 13, "Bola2": 14, "Bola3": 15, "Bola4": 16, "Bola5": 17, "Bola6": 18},
    ])

def test_excel_rag_indexes_only_rows_at_or_before_cutoff(tmp_path: Path):
    p = tmp_path / "mega.xlsx"
    _frame().to_excel(p, index=False)
    rag = SmartExcelRAG(p, as_of_contest=2)
    assert rag.document_count == 2
    assert any(k.endswith(":1") for k in rag.rag.docs)
    assert any(k.endswith(":2") for k in rag.rag.docs)
    assert not any(k.endswith(":3") for k in rag.rag.docs)

def test_excel_rag_retrieves_exact_contest_with_provenance(tmp_path: Path):
    p = tmp_path / "mega.xlsx"
    _frame().to_excel(p, index=False)
    rag = SmartExcelRAG(p, as_of_contest=3)
    hits = rag.retrieve("concurso 3 dezenas 13 14 15 16 17 18", k=2)
    assert hits
    assert hits[0].evidence_id.endswith(":3")
    assert hits[0].source.startswith("excel://mega.xlsx#sha256=")
    assert hits[0].evidence_id in rag.rag.context_block(hits)

def test_excel_rag_fails_closed_on_future_cutoff(tmp_path: Path):
    p = tmp_path / "mega.xlsx"
    _frame().to_excel(p, index=False)
    with pytest.raises(ValueError, match="beyond_dataset"):
        SmartExcelRAG(p, as_of_contest=4)

def test_manifest_denies_predictive_and_freeze_authority(tmp_path: Path):
    p = tmp_path / "mega.xlsx"
    _frame().to_excel(p, index=False)
    m = SmartExcelRAG(p, as_of_contest=2).manifest()
    assert m["temporal_cutoff_enforced"] is True
    assert m["predictive_weight_authority"] is False
    assert m["freeze_mutation_authority"] is False
    assert m["signal_state_mutation_authority"] is False
    assert m["ledger_mutation_authority"] is False

def test_preparation_proof_is_non_mutating(tmp_path: Path):
    p = tmp_path / "mega.xlsx"
    _frame().to_excel(p, index=False)
    root = tmp_path / "root"
    root.mkdir()
    target = root / "Mega-Sena.xlsx"
    target.write_bytes(p.read_bytes())
    proof = build_preparation_proof(root, "Mega-Sena.xlsx", as_of_contest=3)
    assert proof["status"] == "PASS"
    assert all(proof["checks"].values())
    assert proof["critical_hashes_before"] == proof["critical_hashes_after"]

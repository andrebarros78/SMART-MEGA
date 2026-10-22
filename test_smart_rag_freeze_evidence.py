import json
import pytest

from smart_rag_freeze_evidence import prepare_rag_freeze_evidence


def _proof(cutoff):
    doc = {
        "status": "PASS",
        "manifest": {
            "as_of_contest": cutoff,
            "source_contest_max": cutoff,
            "temporal_cutoff_enforced": True,
            "predictive_weight_authority": False,
            "freeze_mutation_authority": False,
            "signal_state_mutation_authority": False,
            "ledger_mutation_authority": False,
        },
        "checks": {
            "critical_canonical_state_unchanged": True,
            "no_predictive_or_freeze_authority": True,
            "latest_allowed_contest_retrievable": True,
        },
    }
    import hashlib
    doc["sha256"] = hashlib.sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return doc


def test_rag_freeze_receipt_has_no_predictive_authority(tmp_path, monkeypatch):
    import smart_rag_freeze_evidence as rag
    monkeypatch.setattr(rag, "build_preparation_proof", lambda root, excel, as_of_contest: _proof(as_of_contest))
    epoch = tmp_path / "runtime" / "epoch"
    epoch.mkdir(parents=True)
    receipt = prepare_rag_freeze_evidence(tmp_path, tmp_path / "immutable.xlsx", 9, epoch, 10)
    assert receipt["status"] == "PASS"
    assert receipt["predictive_weight_authority"] is False
    assert receipt["freeze_mutation_authority"] is False
    output = json.loads((epoch / "SMART_RAG_EXCEL_PREPARATION_PROOF.json").read_text(encoding="utf-8"))
    assert output["manifest"]["as_of_contest"] == 9


def test_rag_freeze_receipt_rejects_future_cutoff_without_writing(tmp_path, monkeypatch):
    import smart_rag_freeze_evidence as rag
    monkeypatch.setattr(rag, "build_preparation_proof", lambda root, excel, as_of_contest: _proof(as_of_contest + 1))
    epoch = tmp_path / "runtime" / "epoch"
    epoch.mkdir(parents=True)
    with pytest.raises(ValueError, match="cutoff"):
        prepare_rag_freeze_evidence(tmp_path, tmp_path / "immutable.xlsx", 9, epoch, 10)
    assert list(epoch.iterdir()) == []

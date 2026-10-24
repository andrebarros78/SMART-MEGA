import json
import hashlib
import pytest

from smart_rag_freeze_evidence import prepare_rag_freeze_evidence


def _proof(cutoff):
    doc = {
        "status": "PASS",
        "manifest": {
            "as_of_contest": cutoff,
            "source_sha256": hashlib.sha256(b"immutable snapshot").hexdigest(),
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
    doc["sha256"] = hashlib.sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return doc


def test_rag_freeze_receipt_has_no_predictive_authority(tmp_path, monkeypatch):
    import smart_rag_freeze_evidence as rag
    monkeypatch.setattr(rag, "build_preparation_proof", lambda root, excel, as_of_contest: _proof(as_of_contest))
    (tmp_path / "immutable.xlsx").write_bytes(b"immutable snapshot")
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
    (tmp_path / "immutable.xlsx").write_bytes(b"immutable snapshot")
    epoch = tmp_path / "runtime" / "epoch"
    epoch.mkdir(parents=True)
    with pytest.raises(ValueError, match="cutoff"):
        prepare_rag_freeze_evidence(tmp_path, tmp_path / "immutable.xlsx", 9, epoch, 10)
    assert list(epoch.iterdir()) == []


def test_rag_read_only_integration_with_canonical_historical_excel():
    """A real 3072-row RAG receipt cannot modify canon or see future contests."""
    from pathlib import Path
    from tempfile import TemporaryDirectory
    import hashlib
    root = Path(__file__).resolve().parent
    history = root / "Mega-Sena.xlsx"
    if not history.is_file():
        pytest.skip("historical Excel fixture unavailable")
    state = root / "SMART_OPERATIONAL_LIFECYCLE.json"
    before = hashlib.sha256(state.read_bytes()).hexdigest()
    with TemporaryDirectory(prefix="rag-freeze-evidence-", dir=root / "runtime") as folder:
        receipt = prepare_rag_freeze_evidence(root, history, 3072, folder, 3073)
        proof = json.loads((Path(folder) / "SMART_RAG_EXCEL_PREPARATION_PROOF.json").read_text(encoding="utf-8"))
        assert receipt["cutoff_contest"] == 3072
        assert receipt["target_contest"] == 3073
        assert receipt["predictive_weight_authority"] is False
        assert receipt["freeze_mutation_authority"] is False
        assert receipt["result_used"] is False
        assert proof["manifest"]["source_contest_max"] == 3072
        assert proof["manifest"]["as_of_contest"] == 3072
        assert proof["manifest"]["indexed_documents"] == 3072
        assert proof["checks"]["no_predictive_or_freeze_authority"] is True
    assert hashlib.sha256(state.read_bytes()).hexdigest() == before

def test_rag_rejects_validly_signed_proof_from_a_different_snapshot(tmp_path, monkeypatch):
    import hashlib
    import smart_rag_freeze_evidence as rag
    data = tmp_path / "immutable.xlsx"
    data.write_bytes(b"immutable snapshot")
    def forged(root, excel, as_of_contest):
        doc = _proof(as_of_contest)
        doc["manifest"]["source_sha256"] = "0" * 64
        doc.pop("sha256")
        doc["sha256"] = hashlib.sha256(json.dumps(
            doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        return doc
    monkeypatch.setattr(rag, "build_preparation_proof", forged)
    epoch = tmp_path / "runtime" / "epoch"
    epoch.mkdir(parents=True)
    with pytest.raises(ValueError, match="source"):
        prepare_rag_freeze_evidence(tmp_path, data, 9, epoch, 10)
    assert list(epoch.iterdir()) == []

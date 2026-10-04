from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

import smart_missed_catchup as catchup
import smart_operational_lifecycle as lifecycle
import smart_operator as operator
from smart_current_epoch_contract import resolve as resolve_current_epoch


def _lifecycle_hold(root, completed: int) -> dict:
    target = completed + 1
    doc = {
        "schema": lifecycle.SCHEMA,
        "state": "HOLD",
        "revision": 1,
        "project": "SMART-MEGA",
        "effective_version": "6.3.2",
        "target_contest": target,
        "completed_contest": completed,
        "previous_state": "REVIEWED",
        "transition": "REVIEWED_TO_HOLD",
        "transition_actor": "test",
        "transition_utc": "2026-09-01T00:00:00+00:00",
        "previous_lifecycle_sha256": None,
        "authority": "SINGLE_OPERATIONAL_LIFECYCLE",
        "legacy_documents_are_evidence_not_authority": True,
        "migration_mode": "TEST",
        "evidence": {},
    }
    return lifecycle._atomic_write(lifecycle.lifecycle_path(root), doc, create_only=True)


def _payload(target: int, date: str, numbers: list[int]) -> dict:
    return {
        "numero": target,
        "listaDezenas": [f"{n:02d}" for n in numbers],
        "dataApuracao": date,
        "acumulado": False,
    }


def test_catchup_chains_multiple_missed_results_and_returns_to_hold(tmp_path, monkeypatch):
    root = tmp_path
    pd.DataFrame([
        {"Concurso": 1, "Data do Sorteio": "01/09/2026", "Bola1": 1, "Bola2": 2, "Bola3": 3, "Bola4": 4, "Bola5": 5, "Bola6": 6},
        {"Concurso": 2, "Data do Sorteio": "03/09/2026", "Bola1": 7, "Bola2": 8, "Bola3": 9, "Bola4": 10, "Bola5": 11, "Bola6": 12},
    ]).to_excel(root / "Mega-Sena.xlsx", index=False)
    _lifecycle_hold(root, 2)
    monkeypatch.setattr(catchup, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})

    out = catchup.catch_up_missed_results(
        root,
        4,
        payloads={
            3: _payload(3, "05/09/2026", [13, 14, 15, 16, 17, 18]),
            4: _payload(4, "08/09/2026", [19, 20, 21, 22, 23, 24]),
        },
        now_utc=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
    )

    assert out["status"] == "CAUGHT_UP_TO_HOLD"
    assert out["start_target"] == 3
    assert out["through_target"] == 4
    assert out["next_target"] == 5
    assert out["recovery_count"] == 2
    assert out["prediction_authority_created"] is False
    assert out["generation_authority_created"] is False
    assert out["retroactive_generation_performed"] is False

    frame = pd.read_excel(root / "Mega-Sena.xlsx")
    assert frame["Concurso"].astype(int).tolist() == [1, 2, 3, 4]
    assert not (root / "SMART_ACTIVE_EPOCH.json").exists()
    assert not any((root / "runtime" / "learning_epochs").glob("operator-3-*"))
    assert not any((root / "runtime" / "learning_epochs").glob("operator-4-*"))

    p3 = json.loads((root / "SMART_MISSED_TARGET_RECOVERY_3.json").read_text(encoding="utf-8"))
    p4 = json.loads((root / "SMART_MISSED_TARGET_RECOVERY_4.json").read_text(encoding="utf-8"))
    assert p3["previous_recovery_sha256"] is None
    assert p4["previous_recovery_sha256"] == p3["sha256"]
    assert all(p3[k] is False for k in ["prediction_authority_created", "generation_authority_created", "freeze_authority_created", "prospective_attempt_counted", "result_used_for_prediction"])
    assert all(p4[k] is False for k in ["prediction_authority_created", "generation_authority_created", "freeze_authority_created", "prospective_attempt_counted", "result_used_for_prediction"])

    life = lifecycle.load_lifecycle(root)
    assert life["state"] == "HOLD"
    assert life["completed_contest"] == 4
    assert life["target_contest"] == 5
    current = resolve_current_epoch(root)
    assert current["status"] == "POST_RESULT_HOLD"
    assert current["cutoff_contest"] == 4
    assert current["target_contest"] == 5
    assert current["generation_allowed"] is False


def test_catchup_hold_hands_back_to_normal_authorize_next_cycle(tmp_path, monkeypatch):
    root = tmp_path
    pd.DataFrame([
        {"Concurso": 1, "Data do Sorteio": "01/09/2026", "Bola1": 1, "Bola2": 2, "Bola3": 3, "Bola4": 4, "Bola5": 5, "Bola6": 6},
        {"Concurso": 2, "Data do Sorteio": "03/09/2026", "Bola1": 7, "Bola2": 8, "Bola3": 9, "Bola4": 10, "Bola5": 11, "Bola6": 12},
    ]).to_excel(root / "Mega-Sena.xlsx", index=False)
    _lifecycle_hold(root, 2)
    monkeypatch.setattr(catchup, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    catchup.catch_up_missed_results(
        root,
        3,
        payloads={3: _payload(3, "05/09/2026", [13, 14, 15, 16, 17, 18])},
        now_utc=datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc),
    )

    authority = operator.authorize_next_cycle_operation(root, 4)
    assert authority["status"] == "AUTHORIZED"
    assert authority["target_contest"] == 4
    assert authority["completed_contest"] == 3
    assert authority["consumed"] is False
    assert lifecycle.load_lifecycle(root)["state"] == "AUTHORIZED"


def test_recover_to_hold_refuses_backward_transition(tmp_path):
    _lifecycle_hold(tmp_path, 10)
    try:
        lifecycle.recover_to_hold(tmp_path, completed_contest=9)
    except lifecycle.LifecycleError as exc:
        assert "backward" in str(exc) or "regress" in str(exc)
    else:
        raise AssertionError("backward recovery transition must fail closed")


def test_official_payload_batch_is_self_hashed_contiguous_and_endpoint_bound(tmp_path):
    import hashlib
    batch = {
        "schema": "SMART_OFFICIAL_RESULT_BATCH_1",
        "authority": "CAIXA_LOTERIAS_OFFICIAL_API",
        "retrieved_at_utc": "2026-09-09T12:00:00Z",
        "capture_transport": "TEST",
        "results": [
            {**_payload(3, "05/09/2026", [13, 14, 15, 16, 17, 18]), "endpoint": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3"},
            {**_payload(4, "08/09/2026", [19, 20, 21, 22, 23, 24]), "endpoint": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/4"},
        ],
    }
    batch["sha256"] = hashlib.sha256(json.dumps(batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(batch), encoding="utf-8")
    payloads, evidence = catchup.load_official_payload_batch(path)
    assert sorted(payloads) == [3, 4]
    assert evidence["document_sha256"] == batch["sha256"]
    assert evidence["targets"] == [3, 4]


def test_catchup_completes_prior_learning_before_history_advance(monkeypatch, tmp_path):
    calls=[]
    monkeypatch.setattr(catchup, 'complete_post_result_learning', lambda root, active: calls.append('learn') or {'status':'POST_RESULT_LEARNING_COMPLETE'})
    monkeypatch.setattr(catchup, 'advance_completed_epoch', lambda root, active: calls.append('advance') or {'status':'PASS'})
    monkeypatch.setattr(catchup, 'verify_product_certification', lambda *a, **k: {'sha256':'c'*64})
    monkeypatch.setattr(catchup, 'load_lifecycle', lambda root: {'state':'ADJUDICATED','target_contest':2})
    monkeypatch.setattr(catchup, 'verify_active_epoch', lambda path: {'project':'SMART-MEGA','target_contest':2,'state_paths':{'ledger':'ledger.json'}})
    monkeypatch.setattr(catchup, '_assert_completed_active', lambda root, active, lifecycle: 2)
    (tmp_path/'SMART_PRODUCT_CERTIFICATION.json').write_text('{}')
    (tmp_path/'SMART_ACTIVE_EPOCH.json').write_text('{}')
    (tmp_path/'SMART_OPERATIONAL_LIFECYCLE.json').write_text('{}')
    (tmp_path/'Mega-Sena.xlsx').write_bytes(b'x')
    (tmp_path/'ledger.json').write_text('{"schema":"SMART_SIGNAL_LEDGER_1","events":[]}')
    monkeypatch.setattr(catchup, '_history', lambda root: {'max':2,'rows':2,'sha256':'h'*64})
    monkeypatch.setattr(catchup, 'canonical_root', lambda root: Path(root))
    monkeypatch.setattr(catchup, '_replace_hashed', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('stop-after-prior-advance')))
    import pytest
    with pytest.raises(RuntimeError, match='stop-after-prior-advance'):
        catchup.catch_up_missed_results(tmp_path,2)
    assert calls[:2]==['learn','advance']

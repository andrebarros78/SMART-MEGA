from __future__ import annotations

import json
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
    assert evidence["authority"] == "CAIXA_API_BATCH_CLAIM_UNVERIFIED_TRANSPORT"
    assert evidence["declared_authority"] == "CAIXA_LOTERIAS_OFFICIAL_API"
    assert evidence["raw_api_independently_verified"] is False
    assert evidence["scientific_certification_authorized"] is False
    assert evidence["predictive_weight_change_authorized"] is False


def test_catchup_finishes_adjudicated_learning_before_history_advance(tmp_path, monkeypatch):
    """A frozen, adjudicated epoch must have its learning proof before rollover."""
    import pytest

    (tmp_path / "Mega-Sena.xlsx").write_bytes(b"unchanged")
    (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text("{}", encoding="utf-8")
    (tmp_path / "SMART_OPERATIONAL_LIFECYCLE.json").write_text("{}", encoding="utf-8")
    active = {"target_contest": 3, "state_paths": {"ledger": "ledger.json"}}
    monkeypatch.setattr(catchup, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    monkeypatch.setattr(catchup, "load_lifecycle", lambda root: {"state": "ADJUDICATED", "target_contest": 3})
    monkeypatch.setattr(catchup, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(catchup, "load_ledger", lambda path: {
        "events": [{"event_type": "ADJUDICATION", "target_contest": 3}]
    })
    sequence = []
    monkeypatch.setattr(catchup, "complete_adjudicated_sequence", lambda root, target: sequence.append(target))

    def checked_advance(root, epoch):
        assert sequence == [3]
        assert epoch is active
        raise RuntimeError("advance reached after learning")

    monkeypatch.setattr(catchup, "advance_completed_epoch", checked_advance)
    with pytest.raises(RuntimeError, match="advance reached after learning"):
        catchup.catch_up_missed_results(tmp_path, 3)
    assert (tmp_path / "Mega-Sena.xlsx").read_bytes() == b"unchanged"


def test_catchup_never_advances_when_adjudicated_learning_fails(tmp_path, monkeypatch):
    import pytest

    (tmp_path / "Mega-Sena.xlsx").write_bytes(b"unchanged")
    (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text("{}", encoding="utf-8")
    (tmp_path / "SMART_OPERATIONAL_LIFECYCLE.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(catchup, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    monkeypatch.setattr(catchup, "load_lifecycle", lambda root: {"state": "ADJUDICATED", "target_contest": 3})
    monkeypatch.setattr(catchup, "verify_active_epoch", lambda path: {
        "target_contest": 3, "state_paths": {"ledger": "ledger.json"}
    })
    monkeypatch.setattr(catchup, "load_ledger", lambda path: {
        "events": [{"event_type": "ADJUDICATION", "target_contest": 3}]
    })

    def invalid_sequence(root, target):
        raise ValueError("official sequence invalid")

    monkeypatch.setattr(catchup, "complete_adjudicated_sequence", invalid_sequence)
    monkeypatch.setattr(catchup, "advance_completed_epoch", lambda *a: pytest.fail("advanced without a sequence proof"))
    with pytest.raises(ValueError, match="official sequence invalid"):
        catchup.catch_up_missed_results(tmp_path, 3)
    assert (tmp_path / "Mega-Sena.xlsx").read_bytes() == b"unchanged"



def test_backward_hold_rejected_before_history_io_or_authority_mutation(tmp_path, monkeypatch):
    """Reject an obsolete target without opening the workbook or rewriting HOLD."""
    import pytest

    originals = {
        "Mega-Sena.xlsx": b"historical canonical bytes",
        "SMART_OPERATIONAL_LIFECYCLE.json": b"historical lifecycle bytes",
        "SMART_NEXT_CYCLE_HOLD.json": b"historical HOLD bytes",
    }
    for filename, original in originals.items():
        (tmp_path / filename).write_bytes(original)
    monkeypatch.setattr(
        catchup, "verify_product_certification",
        lambda *a, **k: {"sha256": "c" * 64},
    )
    monkeypatch.setattr(
        catchup, "load_lifecycle",
        lambda root: {"state": "HOLD", "target_contest": 11, "completed_contest": 10},
    )
    monkeypatch.setattr(
        catchup, "_history",
        lambda *_: pytest.fail("outdated request must be rejected before workbook read"),
    )
    with pytest.raises(ValueError, match="backward"):
        catchup.catch_up_missed_results(tmp_path, through_target=9)
    for filename, original in originals.items():
        assert (tmp_path / filename).read_bytes() == original


def test_backward_adjudicated_rejected_before_learning_or_history_advance(tmp_path, monkeypatch):
    """An already-adjudicated draw cannot be skipped by a recovery for its predecessor."""
    import pytest

    originals = {
        "Mega-Sena.xlsx": b"historical canonical bytes",
        "SMART_ACTIVE_EPOCH.json": b"historical epoch bytes",
        "SMART_OPERATIONAL_LIFECYCLE.json": b"historical lifecycle bytes",
    }
    for filename, original in originals.items():
        (tmp_path / filename).write_bytes(original)
    monkeypatch.setattr(
        catchup, "verify_product_certification",
        lambda *a, **k: {"sha256": "c" * 64},
    )
    monkeypatch.setattr(
        catchup, "load_lifecycle",
        lambda root: {"state": "ADJUDICATED", "target_contest": 11, "completed_contest": 10},
    )
    monkeypatch.setattr(
        catchup, "verify_active_epoch",
        lambda _: {"target_contest": 11, "state_paths": {"ledger": "ledger.json"}},
    )
    monkeypatch.setattr(catchup, "_assert_completed_active", lambda *a: 11)
    monkeypatch.setattr(
        catchup, "complete_adjudicated_sequence",
        lambda *a: pytest.fail("invalid request must not update model learning"),
    )
    monkeypatch.setattr(
        catchup, "advance_completed_epoch",
        lambda *a: pytest.fail("invalid request must not advance canonical history"),
    )
    with pytest.raises(ValueError, match="backward"):
        catchup.catch_up_missed_results(tmp_path, through_target=10)
    for filename, original in originals.items():
        assert (tmp_path / filename).read_bytes() == original


def test_catchup_rejects_incoherent_hold_before_history_read(tmp_path, monkeypatch):
    """Protect against a mismatched HOLD target/completed pair."""
    import pytest

    monkeypatch.setattr(
        catchup, "verify_product_certification",
        lambda *a, **k: {"sha256": "c" * 64},
    )
    monkeypatch.setattr(
        catchup, "load_lifecycle",
        lambda root: {"state": "HOLD", "target_contest": 12, "completed_contest": 10},
    )
    monkeypatch.setattr(
        catchup, "_history",
        lambda *_: pytest.fail("inconsistent lifecycle must fail before history read"),
    )
    with pytest.raises(ValueError, match="HOLD lifecycle"):
        catchup.catch_up_missed_results(tmp_path, through_target=11)


def test_locally_self_hashed_caixa_batch_cannot_claim_independent_transport(tmp_path):
    import hashlib
    import pytest

    batch = {
        "schema": "SMART_OFFICIAL_RESULT_BATCH_1",
        "authority": "CAIXA_LOTERIAS_OFFICIAL_API",
        "capture_transport": "OPERATOR_TYPED_CLAIM_NOT_HTTP_PROOF",
        "raw_api_independently_verified": True,
        "results": [
            {**_payload(3, "05/09/2026", [13, 14, 15, 16, 17, 18]),
             "source": "CAIXA_CONTEST_API",
             "endpoint": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3"},
        ],
    }
    batch["sha256"] = hashlib.sha256(json.dumps(
        batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    file = tmp_path / "forged-selfhash.json"
    file.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError, match="self-declared|transport"):
        catchup.load_official_payload_batch(file)


def test_caixa_api_url_and_claimed_capture_alone_cannot_promote_authority(tmp_path):
    import hashlib

    batch = {
        "schema": "SMART_OFFICIAL_RESULT_BATCH_1",
        "authority": "CAIXA_LOTERIAS_OFFICIAL_API",
        "capture_transport": "FAKE_CAIXA_HTTP_200",
        "capture_status_http": 200,
        "retrieved_at_utc": "2026-09-09T12:00:00Z",
        "results": [
            {**_payload(3, "05/09/2026", [13, 14, 15, 16, 17, 18]),
             "source": "CAIXA_CONTEST_API",
             "endpoint": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3"},
        ],
    }
    batch["sha256"] = hashlib.sha256(json.dumps(
        batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    file = tmp_path / "claim.json"
    file.write_text(json.dumps(batch), encoding="utf-8")
    rows, evidence = catchup.load_official_payload_batch(file)
    assert rows[3]["source"] == "CAIXA_CONTEST_API"
    assert evidence["authority"] == "CAIXA_API_BATCH_CLAIM_UNVERIFIED_TRANSPORT"
    assert evidence["raw_api_independently_verified"] is False
    assert evidence["capture_transport"] == "FAKE_CAIXA_HTTP_200"
    assert evidence["official_transport_attested"] is False


def test_caixa_api_batch_rejects_unsupported_source_label(tmp_path):
    import hashlib
    import pytest

    batch = {
        "schema": "SMART_OFFICIAL_RESULT_BATCH_1",
        "authority": "CAIXA_LOTERIAS_OFFICIAL_API",
        "results": [
            {**_payload(3, "05/09/2026", [13, 14, 15, 16, 17, 18]),
             "source": "FAKE_CAIXA_API_VERIFIED",
             "endpoint": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3"},
        ],
    }
    batch["sha256"] = hashlib.sha256(json.dumps(
        batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    file = tmp_path / "unknown-source.json"
    file.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError, match="API result batch source"):
        catchup.load_official_payload_batch(file)


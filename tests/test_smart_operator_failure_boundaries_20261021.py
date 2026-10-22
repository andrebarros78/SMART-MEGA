"""Protect authority, compare-and-swap and recovery boundaries from partial writes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import smart_operator as op


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("payload", [[], {"schema": "OTHER"}, {"schema": "TEST", "sha256": 42}, {"schema": "TEST", "sha256": "0" * 64}])
def test_hashed_document_rejects_invalid_structure_or_digest_without_rewriting(tmp_path, payload):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        op._load_operator_hashed_doc(path, "TEST")
    assert path.read_bytes() == before


@pytest.mark.parametrize("conflict", ["missing_expected", "wrong_expected", "absent_original", "concurrent_update", "concurrent_create"])
def test_operator_cas_refuses_conflicts_and_preserves_latest_document(tmp_path, monkeypatch, conflict):
    path = tmp_path / "doc.json"
    payload = {"schema": "TEST", "value": "first"}
    initial = None if conflict in {"absent_original", "concurrent_create"} else op._write_operator_hashed_doc(path, payload)
    expected = initial["sha256"] if initial else None
    if conflict == "missing_expected":
        expected = None
    elif conflict in {"wrong_expected", "absent_original"}:
        expected = "0" * 64
    original_write = op.atomic_write_text
    concurrent = {}

    def write_then_race(temp, content):
        original_write(temp, content)
        if conflict.startswith("concurrent_"):
            other = {"schema": "TEST", "revision": 7, "value": "concurrent"}
            other["sha256"] = op._operator_sha256_json(other)
            path.write_text(json.dumps(other))
            concurrent["bytes"] = path.read_bytes()

    monkeypatch.setattr(op, "atomic_write_text", write_then_race)
    before = snapshot(tmp_path)
    with pytest.raises(RuntimeError, match="CAS"):
        op._write_operator_hashed_doc(path, {"schema": "TEST", "value": "replacement"}, expected_sha256=expected)
    if concurrent:
        assert path.read_bytes() == concurrent["bytes"]
        assert not path.with_suffix(".json.tmp").exists()
    else:
        assert snapshot(tmp_path) == before


def authority_fixture(root, monkeypatch, *, reserved=False):
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "AUTHORIZED"})
    (root / "review.json").write_bytes(b"verified review")
    (root / "Mega-Sena.xlsx").write_bytes(b"canonical history")
    hold = {"schema": op.NEXT_CYCLE_HOLD_SCHEMA, "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE", "next_target": 4, "completed_contest": 3}
    authority = {"schema": op.NEXT_CYCLE_AUTHORITY_SCHEMA, "status": "RESERVED" if reserved else "AUTHORIZED", "consumed": False,
                 "target_contest": 4, "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE", "review_file": "review.json",
                 "review_file_sha256": op.sha256_file(root / "review.json"), "canonical_sha256": op.sha256_file(root / "Mega-Sena.xlsx"),
                 "reservation_transaction_id": "tx", "prepared_epoch_id": "epoch"}
    op._write_operator_hashed_doc(root / op.POST_RESULT_HOLD_PATH, hold)
    op._write_operator_hashed_doc(root / op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    return hold, authority


def rewrite(root, name, payload):
    path = root / name
    prior = json.loads(path.read_text())
    return op._write_operator_hashed_doc(path, payload, expected_sha256=prior["sha256"])


@pytest.mark.parametrize("change", ["hold_status", "hold_target", "authority_status", "consumed", "authority_target", "authorized_by", "missing_review", "review_changed", "missing_canonical", "canonical_changed"])
def test_prepare_authority_rejects_stale_or_unbound_evidence_before_writes(tmp_path, monkeypatch, change):
    hold, authority = authority_fixture(tmp_path, monkeypatch)
    if change.startswith("hold_"):
        hold["status" if change == "hold_status" else "next_target"] = "INACTIVE" if change == "hold_status" else 5
        rewrite(tmp_path, op.POST_RESULT_HOLD_PATH, hold)
    elif change in {"missing_review", "missing_canonical"}:
        (tmp_path / ("review.json" if change == "missing_review" else "Mega-Sena.xlsx")).unlink()
    elif change in {"review_changed", "canonical_changed"}:
        (tmp_path / ("review.json" if change == "review_changed" else "Mega-Sena.xlsx")).write_bytes(b"changed")
    else:
        field, value = {"authority_status": ("status", "CONSUMED"), "consumed": ("consumed", True),
                        "authority_target": ("target_contest", 5), "authorized_by": ("authorized_by", "AUTOMATIC")}[change]
        authority[field] = value
        rewrite(tmp_path, op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    before = snapshot(tmp_path)
    with pytest.raises((ValueError, PermissionError)):
        op._require_next_cycle_authority(tmp_path, 4)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("action", ["release", "consume"])
@pytest.mark.parametrize("change", ["status", "consumed", "target_contest", "reservation_transaction_id"])
def test_reservation_cannot_be_released_or_consumed_by_another_operation(tmp_path, monkeypatch, action, change):
    _, authority = authority_fixture(tmp_path, monkeypatch, reserved=True)
    authority[change] = {"status": "AUTHORIZED", "consumed": True, "target_contest": 5, "reservation_transaction_id": "other"}[change]
    rewrite(tmp_path, op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    before = snapshot(tmp_path)
    with pytest.raises(PermissionError):
        if action == "release":
            op._release_next_cycle_authority_reservation(tmp_path, 4, "tx", reason="rolled back")
        else:
            op._consume_reserved_next_cycle_authority(tmp_path, 4, "tx", "epoch", {"target_contest": 4, "epoch_id": "epoch"})
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["reserved_epoch", "active_target", "active_epoch", "active_hash"])
def test_consumption_requires_exact_materialized_epoch(tmp_path, monkeypatch, change):
    _, authority = authority_fixture(tmp_path, monkeypatch, reserved=True)
    active = {"target_contest": 4, "epoch_id": "epoch", "sha256": "a" * 64}
    if change == "reserved_epoch":
        authority["prepared_epoch_id"] = "other"
        rewrite(tmp_path, op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    elif change == "active_target":
        active["target_contest"] = 5
    elif change == "active_epoch":
        active["epoch_id"] = "other"
    else:
        monkeypatch.setattr(op._test_identity, "_authorized_pytest_sandbox", lambda root: False)
        monkeypatch.setattr(op, "verify_active_epoch", lambda path: {**active, "sha256": "b" * 64})
    before = snapshot(tmp_path)
    with pytest.raises(PermissionError):
        op._consume_reserved_next_cycle_authority(tmp_path, 4, "tx", "epoch", active)
    assert snapshot(tmp_path) == before


def test_released_reservation_can_be_used_by_a_new_transaction(tmp_path, monkeypatch):
    authority_fixture(tmp_path, monkeypatch, reserved=True)
    released = op._release_next_cycle_authority_reservation(tmp_path, 4, "tx", reason="rollback verified")
    assert released["status"] == "AUTHORIZED" and released["consumed"] is False
    assert released["prepared_epoch_id"] is None and released["reservation_transaction_id"] is None
    reserved = op._reserve_next_cycle_authority(tmp_path, 4, "next-tx", "next-epoch")
    assert reserved["status"] == "RESERVED" and reserved["reservation_transaction_id"] == "next-tx"
    assert reserved["previous_document_sha256"] == released["sha256"]


@pytest.mark.parametrize("kind", ["absolute", "traversal", "symlink", "missing", "oversize"])
def test_recovery_batch_rejects_unsafe_input_without_calling_completion(tmp_path, monkeypatch, kind):
    import smart_cycle_completion as completion
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(completion, "complete_to_model_card", lambda *a, **k: pytest.fail("unsafe batch reached completion"))
    incoming = "batch.json"
    if kind == "absolute":
        incoming = str(tmp_path / incoming)
    elif kind == "traversal":
        incoming = "../batch.json"
    elif kind == "symlink":
        (tmp_path / incoming).symlink_to(tmp_path.parent / "outside.json")
    elif kind == "oversize":
        (tmp_path / incoming).write_bytes(b" " * (2 * 1024 * 1024 + 1))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="recovery official batch"):
        op.recover_cycle_operation(tmp_path, 4, incoming)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("with_batch", [False, True])
def test_recovery_passes_verified_local_batch_and_real_handlers(tmp_path, monkeypatch, with_batch):
    import smart_cycle_completion as completion
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    path = tmp_path / "batch.json"
    path.write_text("{}")
    calls = []

    def complete(root, target, batch, handlers):
        calls.append((root, target, batch, handlers))
        return {"status": "VALIDATED_DISPATCH"}

    monkeypatch.setattr(completion, "complete_to_model_card", complete)
    before = snapshot(tmp_path)
    assert op.recover_cycle_operation(tmp_path, 4, "batch.json" if with_batch else None)["status"] == "VALIDATED_DISPATCH"
    root, target, batch, handlers = calls.pop()
    assert (root, target, batch) == (tmp_path, 4, path if with_batch else None)
    assert handlers.complete_result is op.complete_result_operation and handlers.generate is op.generate_card_operation
    assert snapshot(tmp_path) == before


CLI_CASES = [
    ("status", "status", [], {}),
    ("preflight", "preflight_operation", [], {}),
    ("result-preflight", "result_preflight_operation", [], {}),
    ("prepare", "prepare_operation", ["--supersede"], {"supersede_existing": True}),
    ("withdraw", "withdraw_pre_freeze_operation", [], {}),
    ("recover-missed", "recover_missed_unfrozen_operation", [], {}),
    ("catch-up", "catch_up_missed_operation", ["--payload-file", "batch.json"], {}),
    ("authorize-next-cycle", "authorize_next_cycle_operation", [], {}),
    ("authorize-generation", "authorize_generation_operation", [], {}),
    ("freeze", "freeze_operation", [], {}),
    ("adjudicate", "adjudicate_operation", ["--result-data", "result.xlsx"], {}),
    ("register-result", "register_result_operation", ["--result-file", "result.json"], {}),
    ("generate-card", "generate_card_operation", [], {}),
    ("show-card", "show_card_operation", [], {}),
    ("post-result-report", "post_result_report_operation", [], {}),
    ("review", "review_operation", ["--review-file", "review.json"], {}),
    ("hold", "hold_operation", ["--hold-file", "hold.json"], {}),
    ("complete-result", "complete_result_operation", [], {}),
    ("recover-cycle", "recover_cycle_operation", ["--payload-file", "batch.json"], {}),
    ("terminal", "terminal_operation", ["--probe-only", "--no-terminal-write"], {"probe_only": True, "allow_terminal_write": False}),
]


@pytest.mark.parametrize("action,handler,extra,expected_kwargs", CLI_CASES)
def test_operator_cli_preserves_explicit_arguments_and_readonly_flags(tmp_path, monkeypatch, capsys, action, handler, extra, expected_kwargs):
    monkeypatch.setattr(op, "canonical_root", lambda: tmp_path)
    calls = []

    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "DISPATCHED", "action": action}

    monkeypatch.setattr(op, handler, capture)
    argv = [action] + ([] if action == "status" else ["--through" if action == "catch-up" else "--target", "4"]) + extra
    op.main(argv)
    assert json.loads(capsys.readouterr().out) == {"status": "DISPATCHED", "action": action}
    args, kwargs = calls.pop()
    assert args[0] == tmp_path and kwargs == expected_kwargs
    assert args[1:] == (() if action == "status" else (4, *([extra[-1]] if action in {"catch-up", "adjudicate", "register-result", "review", "hold", "recover-cycle"} else [])))
    assert snapshot(tmp_path) == {}


def test_preflight_reconciliation_failure_is_structured_and_readonly(tmp_path, monkeypatch):
    from test_smart_operator_preflight import _allow_isolated_root
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr(op, "reconcile_startup", lambda *a, **k: {"status": "RECOVERY_REQUIRED"})
    result = op.preflight_operation(tmp_path, 4)
    assert result["status"] == "RECOVERY_REQUIRED" and result["phase"] == "STARTUP_RECONCILIATION"
    assert result["mutated_state"] is False and snapshot(tmp_path) == {}


def original(function):
    while hasattr(function, "__wrapped__"):
        function = function.__wrapped__
    return function


@pytest.mark.parametrize("state", ["UNREADABLE", "FREEZING", "OTHER"])
def test_preflight_authority_failure_exposes_required_recovery_without_mutating(tmp_path, monkeypatch, state):
    from test_smart_operator_preflight import _allow_isolated_root
    import smart_product_certification as cert
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr(cert, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})

    def denied(*args):
        raise PermissionError("authority unavailable")

    def lifecycle(root):
        if state == "UNREADABLE":
            raise ValueError("invalid lifecycle")
        return {"state": state, "target_contest": 4}

    monkeypatch.setattr(op, "_require_next_cycle_authority", denied)
    monkeypatch.setattr("smart_operational_lifecycle.load_lifecycle", lifecycle)
    result = op.preflight_operation(tmp_path, 4)
    assert result["status"] == ("RECOVERY_REQUIRED" if state == "FREEZING" else "BLOCKED_LIFECYCLE")
    assert result["mutated_state"] is False and snapshot(tmp_path) == {}


@pytest.mark.parametrize("change", ["hold_status", "hold_target", "automatic_allowed", "prepare_allowed", "review_changed", "canonical_changed", "existing_incompatible"])
def test_next_cycle_authorization_does_not_accept_an_invalid_hold(tmp_path, monkeypatch, change):
    hold, authority = authority_fixture(tmp_path, monkeypatch)
    hold.update({"automatic_prepare_forbidden": True, "prepare_allowed": False, "review_file": "review.json",
                 "review_file_sha256": op.sha256_file(tmp_path / "review.json"),
                 "canonical_sha256_at_review": op.sha256_file(tmp_path / "Mega-Sena.xlsx")})
    if change == "hold_status":
        hold["status"] = "INACTIVE"
    elif change == "hold_target":
        hold["next_target"] = 5
    elif change == "automatic_allowed":
        hold["automatic_prepare_forbidden"] = False
    elif change == "prepare_allowed":
        hold["prepare_allowed"] = True
    elif change == "review_changed":
        (tmp_path / "review.json").write_bytes(b"changed")
    elif change == "canonical_changed":
        (tmp_path / "Mega-Sena.xlsx").write_bytes(b"changed")
    else:
        authority["target_contest"] = 8
        rewrite(tmp_path, op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    rewrite(tmp_path, op.POST_RESULT_HOLD_PATH, hold)
    before = snapshot(tmp_path)
    with pytest.raises((ValueError, FileExistsError)):
        original(op.authorize_next_cycle_operation)(tmp_path, 4)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["missing_ledger", "duplicate_adjudication", "missing_path", "bad_hash", "changed_source", "changed_destination", "copy_corrupted", "concurrent_destination"])
def test_result_materialization_rejects_invalid_lineage_or_copy_races(tmp_path, monkeypatch, change):
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    source = tmp_path / "result.xlsx"
    source.write_bytes(b"independently adjudicated result")
    destination = epoch / "Mega-Sena_through_4.xlsx"
    active = {"state_paths": {"ledger": "epoch/ledger.json"}}
    event = {"event_type": "ADJUDICATION", "target_contest": 4, "result_data_file": source.name, "result_data_sha256": op.sha256_file(source)}
    events = [event]
    if change == "missing_ledger":
        active = {}
    elif change == "duplicate_adjudication":
        events.append(dict(event))
    elif change == "missing_path":
        event.pop("result_data_file")
    elif change == "bad_hash":
        event["result_data_sha256"] = "bad"
    elif change == "changed_source":
        source.write_bytes(b"changed after adjudication")
    elif change == "changed_destination":
        destination.write_bytes(b"untrusted prior result")
    copy = op.shutil.copyfile

    def interrupted_copy(src, dst, *args, **kwargs):
        result = copy(src, dst, *args, **kwargs)
        if change == "copy_corrupted":
            Path(dst).write_bytes(b"corrupt transfer")
        elif change == "concurrent_destination":
            destination.write_bytes(b"concurrent result")
        return result

    monkeypatch.setattr(op, "load_ledger", lambda path: {"events": events})
    monkeypatch.setattr(op.shutil, "copyfile", interrupted_copy)
    original_source = source.read_bytes()
    with pytest.raises(ValueError):
        op._materialize_adjudicated_result_dataset(tmp_path, active, 4)
    assert source.read_bytes() == original_source
    assert not list(epoch.glob(".result-*.xlsx"))
    if change == "concurrent_destination":
        assert destination.read_bytes() == b"concurrent result"


@pytest.mark.parametrize("change", ["status", "target", "next_target", "history_hash", "history_max", None])
def test_review_requires_complete_bound_history_before_transition(tmp_path, monkeypatch, change):
    canonical = tmp_path / "Mega-Sena.xlsx"
    canonical.write_bytes(b"canonical-through-four")
    review = {"schema": "SMART_POST_RESULT_REVIEW_1", "status": "POST_RESULT_REVIEW_COMPLETE", "target_contest": 4,
              "next_target": 5, "canonical_history": {"sha256": op.sha256_file(canonical), "history_max": 4}}
    if change in {"status", "target", "next_target"}:
        review[{"status": "status", "target": "target_contest", "next_target": "next_target"}[change]] = "INCOMPLETE" if change == "status" else 9
    elif change:
        review["canonical_history"]["sha256" if change == "history_hash" else "history_max"] = "0" * 64 if change == "history_hash" else 3
    op._write_operator_hashed_doc(tmp_path / "review.json", review)
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "ADJUDICATED"})
    transitions = []
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: transitions.append((a, k)) or {"state": "REVIEWED"})
    before = snapshot(tmp_path)
    if change:
        with pytest.raises(ValueError):
            original(op.review_operation)(tmp_path, 4, "review.json")
        assert transitions == []
    else:
        assert original(op.review_operation)(tmp_path, 4, "review.json")["status"] == "REVIEWED"
        assert len(transitions) == 1 and transitions[0][0][1:3] == ("ADJUDICATED", "REVIEWED")
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["active_status", "schedule_missing", "probe_exception", "recovery_exception"])
def test_result_preflight_failure_does_not_consume_or_rewrite_result(tmp_path, monkeypatch, change):
    from test_smart_result_consumption_readiness import _setup, _observation
    _setup(monkeypatch, tmp_path)
    if change in {"active_status", "schedule_missing"}:
        active = {"status": "FROZEN", "target_contest": 3068, "target_schedule": {"target_contest": 3068, "target_date": "08/10/2026"}}
        if change == "active_status":
            active["status"] = "RESET_READY"
        else:
            active.pop("target_schedule")
        monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    elif change == "probe_exception":
        def probe(*args):
            raise ValueError("evidence invalid")
        monkeypatch.setattr(op.terminal_executor, "probe", probe)
    else:
        monkeypatch.setattr(op.terminal_executor, "probe", lambda *a: _observation(preflight_status="POST_RESULT_SEQUENCE_IN_PROGRESS_OR_COMPLETE"))
        def recovery(*args):
            raise ValueError("recovery ledger invalid")
        monkeypatch.setattr(op, "_verified_adjudication_recovery", recovery)
    before = snapshot(tmp_path)
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == ("BLOCKED_OFFICIAL_EVIDENCE" if change == "probe_exception" else "BLOCKED_INTEGRITY")
    assert result["canonical_writes_performed"] is False and result["result_used_for_learning"] is False
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ["missing", "invalid_json", "not_object", "schema", "hash", "status", "target", "pointer", "checks", "valid"])
def test_withdrawal_discovery_ignores_invalid_archive_artifacts(tmp_path, kind):
    if kind == "missing":
        assert op._find_valid_pre_freeze_withdrawal(tmp_path, 4, "epoch") is None
        return
    archive = tmp_path / "SMART_STATE_ARCHIVE"
    archive.mkdir()
    path = archive / "operator_pre_freeze_withdrawal_candidate.json"
    proof = {"schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1", "status": "WITHDRAWN_PRE_FREEZE", "target_contest": 4,
             "epoch_id": "epoch", "active_pointer_removed": True, "reason": "PRE_FREEZE_TECHNICAL_CORRECTION", "checks": {"verified": True}}
    if kind in {"schema", "status", "target", "pointer", "checks"}:
        field, value = {"schema": ("schema", "OTHER"), "status": ("status", "INCOMPLETE"), "target": ("target_contest", 5),
                        "pointer": ("active_pointer_removed", False), "checks": ("checks", {"verified": False})}[kind]
        proof[field] = value
    proof["sha256"] = "0" * 64 if kind == "hash" else op._operator_sha256_json(proof)
    path.write_text("{" if kind == "invalid_json" else "[]" if kind == "not_object" else json.dumps(proof))
    before = path.read_bytes()
    result = op._find_valid_pre_freeze_withdrawal(tmp_path, 4, "epoch")
    assert (result is not None) == (kind == "valid")
    if result:
        assert result[0] == path and result[1] == proof
    assert path.read_bytes() == before


def test_idempotent_action_persists_once_and_replays_without_calling_action(tmp_path):
    calls = []

    def action():
        calls.append(True)
        return {"status": "DONE", "target_contest": 4}

    execute = original(op._run_idempotent)
    first = execute(tmp_path, "AUTHORIZE", 4, None, {"request": 4}, action)
    second = execute(tmp_path, "AUTHORIZE", 4, None, {"request": 4}, action)
    assert first == second and first["status"] == "DONE" and calls == [True]


@pytest.mark.parametrize("failure", ["wrong_target", "terminal_transition", "report_incomplete", "reviewed", "closed"])
def test_completion_respects_lifecycle_failures_and_review_boundary(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    state = {"state": "FROZEN", "target_contest": 4}
    if failure == "wrong_target":
        state["target_contest"] = 8
    elif failure == "report_incomplete":
        state["state"] = "ADJUDICATED"
    elif failure == "reviewed":
        state["state"] = "REVIEWED"
    elif failure == "closed":
        state.update(state="HOLD", target_contest=5, completed_contest=4)
    monkeypatch.setattr(op, "load_lifecycle", lambda root: dict(state))
    monkeypatch.setattr(op, "terminal_operation", lambda *a, **k: {"adjudication_status": "ADJUDICATED"})
    monkeypatch.setattr(op, "post_result_report_operation", lambda *a, **k: {"status": "INCOMPLETE"})
    if failure == "reviewed":
        result = op.complete_result_operation(tmp_path, 4)
        assert result["status"] == "POST_RESULT_REVIEWED_PENDING_ROLLOVER" and result["terminal_promotion_attempted"] is False
    elif failure == "closed":
        result = op.complete_result_operation(tmp_path, 4)
        assert result["status"] == "POST_RESULT_ALREADY_CLOSED" and result["terminal_promotion_attempted"] is False
    else:
        with pytest.raises((ValueError, RuntimeError)):
            op.complete_result_operation(tmp_path, 4)
    assert snapshot(tmp_path) == {}


@pytest.mark.parametrize("change", ["paths_missing", "absolute", "traversal", "absent_file", "not_operator", "wrong_freeze", "no_adjudication"])
def test_adjudication_recovery_refuses_unbound_or_missing_ledger(tmp_path, monkeypatch, change):
    active = {"state_paths": {"ledger": "ledger.json"}}
    observation = {"result_input_authority": "OPERATOR", "actual_numbers": [1, 2, 3, 4, 5, 6]}
    freeze = {"freeze_sha256": "f" * 64}
    (tmp_path / "ledger.json").write_text("{}")
    if change == "paths_missing":
        active = {}
    elif change == "absolute":
        active["state_paths"]["ledger"] = str(tmp_path / "ledger.json")
    elif change == "traversal":
        active["state_paths"]["ledger"] = "../ledger.json"
    elif change == "absent_file":
        (tmp_path / "ledger.json").unlink()
    elif change == "not_operator":
        observation["result_input_authority"] = "UNVERIFIED"
    elif change == "wrong_freeze":
        freeze["freeze_sha256"] = "e" * 64
    monkeypatch.setattr(op, "load_ledger", lambda path: {"events": []})
    monkeypatch.setattr(op, "active_freeze", lambda ledger, target: freeze)
    before = snapshot(tmp_path)
    assert op._verified_adjudication_recovery(tmp_path, active, 4, "f" * 64, observation) is False
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["status", "target", "valid"])
def test_generation_authorization_requires_prepared_exact_target(tmp_path, monkeypatch, change):
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "PREPARED"})
    active = {"status": "RESET_READY", "operator_selected_target": True, "target_contest": 4}
    if change == "status":
        active["status"] = "FROZEN"
    elif change == "target":
        active["target_contest"] = 5
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    calls = []
    monkeypatch.setattr(op, "authorize_manual_generation", lambda *a: calls.append(a) or {"status": "AUTHORIZED"})
    if change == "valid":
        assert original(op.authorize_generation_operation)(tmp_path, 4)["status"] == "AUTHORIZED"
        assert calls == [(tmp_path, active, 4)]
    else:
        with pytest.raises(ValueError):
            original(op.authorize_generation_operation)(tmp_path, 4)
        assert calls == []


@pytest.mark.parametrize("phase", ["status", "target"])
def test_prepare_key_does_not_bind_inactive_authority(tmp_path, monkeypatch, phase):
    _, authority = authority_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"state": "AUTHORIZED", "target_contest": 4})
    authority["status" if phase == "status" else "target_contest"] = "CONSUMED" if phase == "status" else 5
    rewrite(tmp_path, op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    assert op._prepare_idempotency_payload(tmp_path, 4, (), {}) == {"args": [], "kwargs": {}}


def test_authorization_key_preserves_ordinary_unconsumed_request(tmp_path, monkeypatch):
    authority_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"state": "HOLD", "target_contest": 4})
    assert op._authorization_idempotency_payload(tmp_path, 4, (), {}) == {"args": [], "kwargs": {}}


def test_preflight_detects_missing_epoch_ledger_and_wrong_active_target(tmp_path, monkeypatch):
    from test_smart_operator_preflight import _allow_isolated_root, _active, _schedule
    import smart_product_certification as cert
    _allow_isolated_root(monkeypatch)
    _schedule(monkeypatch)
    monkeypatch.setattr(cert, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    active = _active(tmp_path)
    (tmp_path / op.ACTIVE_PATH).write_text("{}")
    (tmp_path / active["state_paths"]["ledger"]).unlink()
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    before = snapshot(tmp_path)
    assert op.preflight_operation(tmp_path, 3060)["status"] == "BLOCKED_INTEGRITY"
    active["target_contest"] = 3061
    with pytest.raises(ValueError, match="does not match preflight target"):
        op.preflight_operation(tmp_path, 3060)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("with_payload", [False, True])
def test_catchup_operation_binds_explicit_batch_evidence(tmp_path, monkeypatch, with_payload):
    import smart_missed_catchup as catchup
    calls = []
    monkeypatch.setattr(catchup, "load_official_payload_batch", lambda path: ({4: {"numero": 4}}, {"file": path}))
    monkeypatch.setattr(catchup, "catch_up_missed_results", lambda *a, **k: calls.append((a, k)) or {"status": "BOUND"})
    result = original(op.catch_up_missed_operation)(tmp_path, "4", "batch.json" if with_payload else None)
    assert result["status"] == "BOUND"
    assert calls == [((tmp_path, 4), {"payloads": {4: {"numero": 4}} if with_payload else None,
                                    "payload_batch_evidence": {"file": "batch.json"} if with_payload else None})]


def test_read_card_and_hold_dispatch_use_exact_requested_target(tmp_path, monkeypatch):
    import smart_frozen_card_reader as cards
    calls = []
    monkeypatch.setattr(cards, "read_frozen_card", lambda *a: calls.append(a) or {"status": "FROZEN"})
    assert op.show_card_operation(tmp_path, "4")["status"] == "FROZEN"
    assert calls == [(tmp_path, 4)]
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "canonical_rollover", lambda *a: calls.append(a) or {"status": "HOLD"})
    assert original(op.hold_operation)(tmp_path, "4", "hold.json")["status"] == "HOLD"
    assert calls[-1] == (tmp_path, 4, "hold.json")


@pytest.mark.parametrize("target_matches", [False, True])
def test_post_result_report_materializes_bound_bytes_before_learning(tmp_path, monkeypatch, target_matches):
    import smart_post_result_report as reports
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    source = tmp_path / "result.xlsx"
    source.write_bytes(b"adjudicated history")
    active = {"target_contest": 4 if target_matches else 5, "state_paths": {"ledger": "epoch/ledger.json"}}
    event = {"event_type": "ADJUDICATION", "target_contest": 4, "result_data_file": source.name, "result_data_sha256": op.sha256_file(source)}
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "ADJUDICATED"})
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(op, "load_ledger", lambda path: {"events": [event]})
    calls = []
    monkeypatch.setattr(reports, "emit_post_result_report", lambda *a: calls.append("report") or {"status": "REPORTED"})

    def complete(*args):
        assert (epoch / "Mega-Sena_through_4.xlsx").read_bytes() == source.read_bytes()
        calls.append("learning")
        return {"status": "COMPLETED"}

    monkeypatch.setattr(op.terminal_executor, "complete_adjudicated_sequence", complete)
    monkeypatch.setattr(op, "advance_completed_epoch", lambda *a: calls.append("history") or {"status": "ADVANCED"})
    if target_matches:
        result = original(op.post_result_report_operation)(tmp_path, 4)
        assert result["status"] == "POST_RESULT_SEQUENCE_COMPLETED"
        assert result["result_dataset"]["sha256"] == op.sha256_file(source)
        assert calls == ["report", "learning", "history"]
    else:
        with pytest.raises(ValueError, match="does not match report target"):
            original(op.post_result_report_operation)(tmp_path, 4)
        assert calls == [] and not (epoch / "Mega-Sena_through_4.xlsx").exists()


@pytest.mark.parametrize("change", ["status", "target", "proof", "unstructured_result", "valid_report"])
def test_adjudication_checks_generation_authority_and_rolls_back_invalid_result(tmp_path, monkeypatch, change):
    import smart_post_result_report as reports
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_bytes(b"ledger-before")
    lifecycle_path = tmp_path / "SMART_OPERATIONAL_LIFECYCLE.json"
    lifecycle_path.write_bytes(b"lifecycle-before")
    active = {"target_contest": 4, "state_paths": {"ledger": "ledger.json", "freeze": "freeze.json"}}
    current = {"status": "FROZEN", "freeze_authority_present": True, "target_contest": 4, "generation_proof_valid": True, "freeze_sha256": "f" * 64}
    if change == "status":
        current["status"] = "ADJUDICATED"
    elif change == "target":
        current["target_contest"] = 5
    elif change == "proof":
        current["generation_proof_valid"] = False
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "FROZEN"})
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(op, "resolve_current_epoch", lambda root: current)
    monkeypatch.setattr(op, "load_ledger", lambda path: {"events": []})
    monkeypatch.setattr(op, "active_freeze", lambda *a: {"freeze_sha256": "f" * 64})
    calls = []

    def adjudicate(*args):
        calls.append("adjudicate")
        ledger_path.write_bytes(b"ledger-partially-mutated")
        return None if change == "unstructured_result" else {"status": "ADJUDICATED"}

    monkeypatch.setattr(op, "adjudicate", adjudicate)
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: {"state": "ADJUDICATED"})
    monkeypatch.setattr(reports, "emit_post_result_report", lambda *a: {"status": "REPORTED"})
    before = snapshot(tmp_path)
    if change == "valid_report":
        result = original(op.adjudicate_operation)(tmp_path, 4, "result.xlsx")
        assert result["post_result_report"]["status"] == "REPORTED" and calls == ["adjudicate"]
    else:
        with pytest.raises((ValueError, RuntimeError)):
            original(op.adjudicate_operation)(tmp_path, 4, "result.xlsx")
        assert snapshot(tmp_path) == before
        assert calls == (["adjudicate"] if change == "unstructured_result" else [])


def test_existing_authorization_can_recover_lifecycle_transition(tmp_path, monkeypatch):
    hold, authority = authority_fixture(tmp_path, monkeypatch)
    hold.update(automatic_prepare_forbidden=True, prepare_allowed=False, review_file="review.json",
                review_file_sha256=op.sha256_file(tmp_path / "review.json"), canonical_sha256_at_review=op.sha256_file(tmp_path / "Mega-Sena.xlsx"))
    rewrite(tmp_path, op.POST_RESULT_HOLD_PATH, hold)
    prior = (tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH).read_bytes()
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    calls = []
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: calls.append((a, k)) or {"state": "AUTHORIZED"})
    result = original(op.authorize_next_cycle_operation)(tmp_path, 4)
    assert result["status"] == "AUTHORIZED" and result["operational_lifecycle"]["state"] == "AUTHORIZED"
    assert len(calls) == 1 and calls[0][0][1:3] == ("HOLD", "AUTHORIZED")
    assert (tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH).read_bytes() == prior


def test_new_authorization_can_supersede_a_consumed_completed_target(tmp_path, monkeypatch):
    hold, authority = authority_fixture(tmp_path, monkeypatch)
    hold.update(automatic_prepare_forbidden=True, prepare_allowed=False, completed_contest=3, review_file="review.json",
                review_file_sha256=op.sha256_file(tmp_path / "review.json"), canonical_sha256_at_review=op.sha256_file(tmp_path / "Mega-Sena.xlsx"))
    rewrite(tmp_path, op.POST_RESULT_HOLD_PATH, hold)
    authority.update(target_contest=3, consumed=True, status="CONSUMED")
    prior = rewrite(tmp_path, op.NEXT_CYCLE_AUTHORITY_PATH, authority)
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: {"state": "AUTHORIZED"})
    result = original(op.authorize_next_cycle_operation)(tmp_path, 4)
    assert result["supersedes_completed_cycle_authority"] is True and result["target_contest"] == 4
    assert result["previous_document_sha256"] == prior["sha256"] and result["consumed"] is False


def test_valid_active_hash_is_bound_when_consuming_reservation(tmp_path, monkeypatch):
    authority_fixture(tmp_path, monkeypatch, reserved=True)
    active = {"target_contest": 4, "epoch_id": "epoch", "sha256": "a" * 64}
    monkeypatch.setattr(op._test_identity, "_authorized_pytest_sandbox", lambda root: False)
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    result = op._consume_reserved_next_cycle_authority(tmp_path, 4, "tx", "epoch", active)
    assert result["status"] == "CONSUMED" and result["active_epoch_sha256_at_consumption"] == active["sha256"]


def test_prepare_payload_does_not_bind_a_missing_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"state": "AUTHORIZED", "target_contest": 4})
    assert op._prepare_idempotency_payload(tmp_path, 4, (), {}) == {"args": [], "kwargs": {}}


def test_registration_and_terminal_refuse_a_different_epoch_before_consumption(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "FROZEN"})
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: {"status": "FROZEN", "target_contest": 5})
    with pytest.raises(ValueError, match="exact frozen epoch"):
        original(op.register_result_operation)(tmp_path, 4, "result.json")
    with pytest.raises(ValueError, match="does not match terminal target"):
        original(op.terminal_operation)(tmp_path, 4)
    assert snapshot(tmp_path) == {}


def test_preflight_waits_for_operator_input_without_fetching_or_mutating(tmp_path, monkeypatch):
    from test_smart_result_consumption_readiness import _setup
    _setup(monkeypatch, tmp_path)
    (tmp_path / "SMART_OPERATOR_RESULT_3068.json").unlink()
    monkeypatch.setattr(op.terminal_executor, "probe", lambda *a: pytest.fail("missing operator input must not trigger fetch"))
    before = snapshot(tmp_path)
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "WAITING_OPERATOR_RESULT" and result["canonical_writes_performed"] is False
    assert snapshot(tmp_path) == before


def test_status_reports_invalid_active_epoch_without_suppressing_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    monkeypatch.setattr(op, "reconcile_startup", lambda *a, **k: {"status": "RECOVERY_REQUIRED"})
    monkeypatch.setattr(op, "audit_state_boundaries", lambda root: {"status": "FAIL"})
    monkeypatch.setattr("smart_historical_binding.build", lambda *a: {"status": "PASS"})
    monkeypatch.setattr("smart_proof_chain.inspect", lambda *a: {"status": "FAIL"})
    (tmp_path / op.ACTIVE_PATH).write_text("{")
    before = snapshot(tmp_path)
    result = op.status(tmp_path)
    assert result["status"] == "RECOVERY_REQUIRED" and result["active_operation"]["status"] == "INVALID"
    assert "reason" in result["active_operation"] and snapshot(tmp_path) == before


@pytest.mark.parametrize("failure", ["reserve_denied", "prepared_receipt", "foreign_reservation", "already_rolled_back"])
def test_prepare_precommit_failure_releases_only_its_own_reservation(tmp_path, monkeypatch, failure):
    authority_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    import smart_product_certification as cert
    monkeypatch.setattr(cert, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    monkeypatch.setattr(op, "validate_target_against_history", lambda *a: {"data_sha256": op.sha256_file(tmp_path / "Mega-Sena.xlsx")})
    monkeypatch.setattr(op, "resolve_target_schedule", lambda *a: {"target_contest": 4})
    monkeypatch.setattr(op, "assert_pre_draw_window", lambda *a: {"status": "PASS"})
    reserve = op._reserve_next_cycle_authority

    def reserve_with_failure(root, target, transaction, epoch):
        if failure == "reserve_denied":
            raise PermissionError("reservation unavailable")
        return reserve(root, target, "another-transaction" if failure == "foreign_reservation" else transaction, epoch)

    def receipt_failed(*a, **k):
        if failure == "already_rolled_back":
            op.journal_rolled_back(*a, **k)
        raise OSError("prepared receipt could not be persisted")

    monkeypatch.setattr(op, "_reserve_next_cycle_authority", reserve_with_failure)
    monkeypatch.setattr(op, "journal_prepared", receipt_failed)
    canonical_before = (tmp_path / "Mega-Sena.xlsx").read_bytes()
    with pytest.raises((PermissionError, OSError)):
        original(op.prepare_operation)(tmp_path, 4)
    result = op._load_operator_hashed_doc(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, op.NEXT_CYCLE_AUTHORITY_SCHEMA)
    assert result["status"] == ("RESERVED" if failure == "foreign_reservation" else "AUTHORIZED")
    assert result["consumed"] is False
    if failure == "foreign_reservation":
        assert result["reservation_transaction_id"] == "another-transaction"
    assert not (tmp_path / op.ACTIVE_PATH).exists()
    assert (tmp_path / "Mega-Sena.xlsx").read_bytes() == canonical_before


def test_prepare_propagates_corrupt_active_epoch_outside_pytest_adapter(tmp_path, monkeypatch):
    authority_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    import smart_product_certification as cert
    monkeypatch.setattr(cert, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    monkeypatch.setattr(op._test_identity, "_authorized_pytest_sandbox", lambda root: False)
    (tmp_path / op.ACTIVE_PATH).write_text("{")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        original(op.prepare_operation)(tmp_path, 4)
    assert snapshot(tmp_path) == before


def test_withdrawal_rejects_invalid_manual_generation_authority(tmp_path, monkeypatch):
    from test_smart_operator_seed_rollover_20260910 import _make_reset_ready
    active, ledger, data = _make_reset_ready(tmp_path, [{"event_type": "ADJUDICATION", "target_contest": 3055}])
    (ledger.parent / "SMART_MANUAL_GENERATION_AUTHORITY.json").write_text("{")
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    before = snapshot(tmp_path)
    with pytest.raises(RuntimeError, match="pre-freeze withdrawal blocked"):
        original(op.withdraw_pre_freeze_operation)(tmp_path, 3056)
    assert snapshot(tmp_path) == before


def test_prepare_binds_real_active_epoch_hash_to_consumed_authority(tmp_path, monkeypatch):
    authority_fixture(tmp_path, monkeypatch)
    import smart_operational_lifecycle as lifecycle
    lifecycle.initialize_from_legacy(tmp_path)
    lifecycle.transition(tmp_path, "HOLD", "AUTHORIZED", target_contest=4, actor="test_explicit_authorization")
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    import smart_product_certification as cert
    monkeypatch.setattr(cert, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    monkeypatch.setattr(op, "validate_target_against_history", lambda path, target: {"data_sha256": op.sha256_file(path), "cutoff_contest": 3})
    monkeypatch.setattr(op, "resolve_target_schedule", lambda *a: {"target_contest": 4})
    monkeypatch.setattr(op, "assert_pre_draw_window", lambda *a: {"status": "PASS"})
    result = original(op.prepare_operation)(tmp_path, 4)
    active = op.verify_active_epoch(tmp_path / op.ACTIVE_PATH)
    authority = op._load_operator_hashed_doc(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, op.NEXT_CYCLE_AUTHORITY_SCHEMA)
    assert result["status"] == "READY_TO_FREEZE" and authority["status"] == "CONSUMED"
    assert authority["active_epoch_sha256_at_consumption"] == active["sha256"]
    assert authority["prepared_epoch_id"] == active["epoch_id"]
    assert lifecycle.load_lifecycle(tmp_path)["state"] == "PREPARED"
    assert (tmp_path / active["data_file"]).read_bytes() == (tmp_path / "Mega-Sena.xlsx").read_bytes()

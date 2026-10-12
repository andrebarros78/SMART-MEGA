from pathlib import Path
import json

import smart_post_result_report as pr


def _fixture(tmp_path: Path, *, reported_hits=None):
    epoch = tmp_path / "runtime" / "learning_epochs" / "operator-999-fixture"
    epoch.mkdir(parents=True)
    freeze = epoch / "SMART_999_CHAMPION_CHALLENGER_FREEZE.json"
    freeze.write_text(json.dumps({"champion": {"top6": [1, 2, 3, 4, 5, 6]}}), encoding="utf-8")
    fsha = pr._sha256_file(freeze)
    adjudication = {
        "event_type": "ADJUDICATION",
        "target_contest": 999,
        "actual_numbers": [1, 2, 7, 8, 9, 10],
    }
    if reported_hits is not None:
        adjudication["hits"] = reported_hits
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    ledger.write_text(json.dumps({"events": [
        {"event_type": "FREEZE", "target_contest": 999, "freeze_sha256": fsha, "top6": [1, 2, 3, 4, 5, 6]},
        adjudication,
    ]}), encoding="utf-8")
    return {
        "target_contest": 999,
        "freeze_authority": {
            "file": str(freeze.relative_to(tmp_path)).replace("\\", "/"),
            "sha256": fsha,
            "target_contest": 999,
            "cutoff_contest": 998,
        },
        "state_paths": {
            "freeze": str(freeze.relative_to(tmp_path)).replace("\\", "/"),
            "ledger": str(ledger.relative_to(tmp_path)).replace("\\", "/"),
        },
    }


def test_report_contains_required_operational_fields(tmp_path: Path) -> None:
    out = pr.emit_post_result_report(tmp_path, _fixture(tmp_path, reported_hits=2))
    report = out["report"]
    assert out["status"] == "EMITTED"
    assert report["contest_number"] == 999
    assert report["official_result"] == [1, 2, 7, 8, 9, 10]
    assert report["generated_card"] == [1, 2, 3, 4, 5, 6]
    assert report["hit_count"] == 2
    assert report["matched_numbers"] == [1, 2]
    assert report["self_analysis"]["single_contest_weight_change_prohibited"] is True
    md = (tmp_path / out["markdown_file"]).read_text(encoding="utf-8")
    assert "Concurso 999" in md
    assert "Número de acertos:** 2/6" in md
    assert "Autoanálise construtiva" in md


def test_report_detects_hit_count_divergence(tmp_path: Path) -> None:
    out = pr.emit_post_result_report(tmp_path, _fixture(tmp_path, reported_hits=5))
    assert out["report"]["status"] == "PASS_WITH_PROCESS_FINDINGS"
    assert any("Divergência de contabilização" in item for item in out["report"]["process_audit"]["findings"])


def test_report_is_idempotent_for_same_evidence(tmp_path: Path) -> None:
    active = _fixture(tmp_path, reported_hits=2)
    first = pr.emit_post_result_report(tmp_path, active)
    second = pr.emit_post_result_report(tmp_path, active)
    assert first["status"] == "EMITTED"
    assert second["status"] == "EXISTING_VALID"
    assert second["report"]["source_fingerprint"] == first["report"]["source_fingerprint"]

from smart_post_result_report import _numbers


def test_numbers_accepts_portfolio_game_records():
    assert _numbers({"game_id": "G1", "numbers": [1, 2, 3, 4, 5, 6]}) == [1, 2, 3, 4, 5, 6]
    assert _numbers({"game_id": "BAD", "numbers": [1, 1, 3, 4, 5, 6]}) is None


def test_post_result_uses_frozen_primary_when_it_differs_from_champion(tmp_path):
    active=_fixture(tmp_path,reported_hits=2)
    ledger=tmp_path/active["state_paths"]["ledger"]
    doc=json.loads(ledger.read_text(encoding="utf-8"))
    doc["events"][0]["primary_card"]={"numbers":[1,2,7,8,9,10]}
    ledger.write_text(json.dumps(doc),encoding="utf-8")
    result=pr.emit_post_result_report(tmp_path,active)
    report=result["report"]
    assert report["status"]=="PASS"
    assert report["generated_card"]==[1,2,7,8,9,10]
    assert report["hit_count"]==6
    assert report["champion_hits"]==2
    assert report["matched_numbers"]==[1,2,7,8,9,10]


def test_post_result_rejects_invalid_frozen_primary_evidence(tmp_path):
    import pytest
    active=_fixture(tmp_path)
    ledger=tmp_path/active["state_paths"]["ledger"]
    doc=json.loads(ledger.read_text(encoding="utf-8"))
    doc["events"][0]["primary_card"]={"numbers":[1,1,2,3,4,5]}
    ledger.write_text(json.dumps(doc),encoding="utf-8")
    with pytest.raises(ValueError,match="frozen primary card evidence invalid"):
        pr.emit_post_result_report(tmp_path,active)


def test_post_result_immutable_ledger_survives_learning_update(tmp_path: Path) -> None:
    from smart_false_negative_rescue import build_profile_from_reports
    active = _fixture(tmp_path, reported_hits=2)
    freeze = tmp_path / active["state_paths"]["freeze"]
    freeze_obj = json.loads(freeze.read_text(encoding="utf-8"))
    freeze_obj["target_contest"] = 999
    freeze.write_text(json.dumps(freeze_obj), encoding="utf-8")
    freeze_sha = pr._sha256_file(freeze)
    active["freeze_authority"]["sha256"] = freeze_sha
    ledger = tmp_path / active["state_paths"]["ledger"]
    ledger_obj = json.loads(ledger.read_text(encoding="utf-8"))
    for event in ledger_obj["events"]:
        event["freeze_sha256"] = freeze_sha
    ledger.write_text(json.dumps(ledger_obj), encoding="utf-8")
    before = ledger.read_bytes()
    report = pr.emit_post_result_report(tmp_path, active)["report"]
    ledger_sha = report["process_audit"]["ledger_sha256"]
    snapshot = (tmp_path / "SMART_STATE_ARCHIVE" / "hash-bound-learning" / "999"
                / f"SMART_SIGNAL_LEDGER.{ledger_sha}.json")
    assert snapshot.read_bytes() == before
    ledger_obj["events"].append({"event_type": "LEARNING_UPDATE", "target_contest": 999})
    ledger.write_text(json.dumps(ledger_obj), encoding="utf-8")
    assert snapshot.read_bytes() == before
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text("{}", encoding="utf-8")
    profile = build_profile_from_reports(tmp_path, through_contest=999)
    assert profile["source_contests"] == [999], profile["quarantined_reasons"]
    assert profile["quarantined_count"] == 0
    assert profile["recovered_verified_evidence"] == {"999": ["ledger"]}

    snapshot.write_bytes(b"tampered")
    rejected = build_profile_from_reports(tmp_path, through_contest=999)
    assert rejected["source_contests"] == []
    assert rejected["quarantined_count"] == 1


def test_post_result_rejects_corrupted_existing_ledger_archive(tmp_path: Path) -> None:
    import pytest
    active = _fixture(tmp_path, reported_hits=2)
    out = pr.emit_post_result_report(tmp_path, active)
    digest = out["report"]["process_audit"]["ledger_sha256"]
    archive = (tmp_path / "SMART_STATE_ARCHIVE" / "hash-bound-learning" / "999"
               / f"SMART_SIGNAL_LEDGER.{digest}.json")
    archive.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="ledger archive hash mismatch"):
        pr.emit_post_result_report(tmp_path, active)


def _inject_signal_snapshot(tmp_path: Path, active: dict, *, tamper: bool = False) -> None:
    """Attach a legitimate pre-result challenger snapshot to a sandbox freeze."""
    freeze_path = tmp_path / active["state_paths"]["freeze"]
    doc = json.loads(freeze_path.read_text(encoding="utf-8"))
    doc["challenger"] = {
        "top6": [7, 8, 9, 10, 11, 12] if tamper else [1, 2, 3, 4, 5, 6],
        "raw_signals": {
            "supports_top6": {"values": {str(n): (1.0 if n <= 6 else 0.0) for n in range(1, 61)}},
            "opposition": {"values": {str(n): (1.0 if 7 <= n <= 12 else 0.0) for n in range(1, 61)}},
        },
        "weights": {"supports_top6": 0.8, "opposition": 0.2},
    }
    freeze_path.write_text(json.dumps(doc), encoding="utf-8")
    updated_sha = pr._sha256_file(freeze_path)
    active["freeze_authority"]["sha256"] = updated_sha
    ledger_path = tmp_path / active["state_paths"]["ledger"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["events"][0]["freeze_sha256"] = updated_sha
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")


def test_post_result_consumes_actual_frozen_signal_weights_and_explains_card(tmp_path: Path) -> None:
    active = _fixture(tmp_path, reported_hits=2)
    _inject_signal_snapshot(tmp_path, active)
    result = pr.emit_post_result_report(tmp_path, active)
    report = result["report"]
    diag = report["signal_diagnostic"]
    assert report["hit_count"] == 2
    assert diag["status"] == "PASS"
    assert diag["challenger_top6"] == [1, 2, 3, 4, 5, 6]
    assert diag["challenger_hits"] == 2
    assert diag["signal_count"] == 2
    assert diag["top_two_weight_share"] == 1.0
    assert [row["signal"] for row in diag["per_signal"]] == ["supports_top6", "opposition"]
    assert diag["coalition_tested"] == 2
    assert len(diag["attribution_sha256"]) == 64
    assert diag["predictive_promotion_authorized"] is False
    assert diag["retrospective_gain_is_not_predictive_evidence"] is True
    md = (tmp_path / result["markdown_file"]).read_text(encoding="utf-8")
    assert "Diagnóstico dos pesos realmente consumidos" in md
    assert "supports_top6: peso=80.00%" in md
    assert "resultado retrospectivo" in md
    # Reprocessing never changes a previously sealed report or its hash.
    old_bytes = (tmp_path / result["report_file"]).read_bytes()
    reprocessed = pr.emit_post_result_report(tmp_path, active)
    assert reprocessed["status"] == "EXISTING_VALID"
    assert (tmp_path / result["report_file"]).read_bytes() == old_bytes


def test_post_result_detects_tampered_pre_result_signal_snapshot(tmp_path: Path) -> None:
    import pytest
    active = _fixture(tmp_path, reported_hits=2)
    _inject_signal_snapshot(tmp_path, active, tamper=True)
    with pytest.raises(ValueError, match="does not reproduce frozen challenger"):
        pr.emit_post_result_report(tmp_path, active)
    assert not (tmp_path / "SMART_POST_RESULT_REPORT_999.json").exists()


def test_post_result_refuses_incomplete_signal_snapshot(tmp_path: Path) -> None:
    import pytest
    active = _fixture(tmp_path, reported_hits=2)
    _inject_signal_snapshot(tmp_path, active)
    freeze_path = tmp_path / active["state_paths"]["freeze"]
    doc = json.loads(freeze_path.read_text(encoding="utf-8"))
    del doc["challenger"]["weights"]
    freeze_path.write_text(json.dumps(doc), encoding="utf-8")
    updated_sha = pr._sha256_file(freeze_path)
    active["freeze_authority"]["sha256"] = updated_sha
    ledger_path = tmp_path / active["state_paths"]["ledger"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["events"][0]["freeze_sha256"] = updated_sha
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot requires raw_signals and weights"):
        pr.emit_post_result_report(tmp_path, active)


def test_post_result_is_explicit_when_legacy_freeze_has_no_signal_snapshot(tmp_path: Path) -> None:
    result = pr.emit_post_result_report(tmp_path, _fixture(tmp_path, reported_hits=2))
    assert result["report"]["signal_diagnostic"]["status"] == "UNAVAILABLE_LEGACY_FREEZE"
    assert result["report"]["signal_diagnostic"]["predictive_promotion_authorized"] is False


def _with_champion_attribution_fixture(tmp_path: Path, *, tamper_scores: bool = False) -> dict:
    active = _fixture(tmp_path, reported_hits=2)
    freeze_path = tmp_path / active["state_paths"]["freeze"]
    obj = json.loads(freeze_path.read_text())
    signals = {
        "support": {"values": {str(n): (1.0 if n <= 6 else 0.0) for n in range(1, 61)}},
        "against": {"values": {str(n): (1.0 if 7 <= n <= 12 else 0.0) for n in range(1, 61)}},
    }
    obj["champion"]["expert_weights"] = {"support": 0.8, "against": 0.2}
    obj["champion"]["aggregate_scores"] = {
        str(n): (0.9 if n == 1 and tamper_scores else
                 0.8 if n <= 6 else 0.2 if n <= 12 else 0.0)
        for n in range(1, 61)
    }
    obj["challenger"] = {
        "top6": [1, 2, 3, 4, 5, 6], "raw_signals": signals,
        "weights": {"support": 0.8, "against": 0.2},
    }
    freeze_path.write_text(json.dumps(obj), encoding="utf-8")
    digest = pr._sha256_file(freeze_path)
    active["freeze_authority"]["sha256"] = digest
    ledger_path = tmp_path / active["state_paths"]["ledger"]
    ledger = json.loads(ledger_path.read_text())
    ledger["events"][0]["freeze_sha256"] = digest
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    return active


def test_production_champion_contribution_report_generated_card(tmp_path: Path):
    active = _with_champion_attribution_fixture(tmp_path)
    out = pr.emit_post_result_report(tmp_path, active)
    diag = out["report"]["primary_card_diagnostic"]
    assert diag["status"] == "PASS"
    assert diag["model"] == "FROZEN_PRODUCTION_CHAMPION"
    assert diag["signal_count"] == 2
    assert diag["top_two_weight_share"] == 1.0
    assert diag["final_decision"]["champion_hits"] == 2
    assert diag["final_decision"]["actual_primary_hits"] == 2
    assert diag["final_decision"]["decision_changed"] is False
    assert diag["predictive_promotion_authorized"] is False
    assert out["report"]["signal_diagnostic"]["status"] == "PASS"
    assert "Atribuição do Champion e do cartão principal" in (tmp_path / out["markdown_file"]).read_text()


def test_production_champion_and_selected_card_are_not_confused(tmp_path: Path):
    active = _with_champion_attribution_fixture(tmp_path)
    ledger_path = tmp_path / active["state_paths"]["ledger"]
    ledger = json.loads(ledger_path.read_text())
    ledger["events"][0]["primary_card"] = {"numbers": [1, 2, 7, 8, 9, 10]}
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    result = pr.emit_post_result_report(tmp_path, active)
    d = result["report"]["primary_card_diagnostic"]["final_decision"]
    assert result["report"]["hit_count"] == 6
    assert d["champion_hits"] == 2
    assert d["actual_primary_hits"] == 6
    assert d["decision_changed"] is True
    assert d["added_by_final_selection"] == [7, 8, 9, 10]
    assert d["removed_from_champion"] == [3, 4, 5, 6]
    assert d["cause_scope"] == "SELECTOR_PLUS_RESCUE_NOT_ISOLATED"


def test_production_champion_rejects_score_mismatch(tmp_path: Path):
    import pytest
    active = _with_champion_attribution_fixture(tmp_path, tamper_scores=True)
    with pytest.raises(ValueError, match="Champion signal scores do not reproduce"):
        pr.emit_post_result_report(tmp_path, active)
    assert not (tmp_path / "SMART_POST_RESULT_REPORT_999.json").exists()


def _real_operational_skill_fixture(contest=3068):
    """Return a truly frozen source/official pair, not synthetic metrics."""
    from pathlib import Path
    source_root = Path(__file__).resolve().parent
    freeze_path = next((source_root / 'runtime' / 'learning_epochs').glob(
        f'operator-{contest}-*/SMART_{contest}_CHAMPION_CHALLENGER_FREEZE.json'))
    report_path = source_root / f'SMART_POST_RESULT_REPORT_{contest}.json'
    return json.loads(freeze_path.read_text()), json.loads(report_path.read_text())


def test_operational_capabilities_consume_real_quality_weight_calibration_and_learning():
    import hashlib
    freeze, report = _real_operational_skill_fixture()
    before = hashlib.sha256(json.dumps(freeze, sort_keys=True).encode()).hexdigest()
    result = pr._operational_capability_consumption(freeze, report['official_result'])
    assert result['status'] == 'PASS'
    assert result['scope'] == 'REAL_FROZEN_INPUT_POST_RESULT_NATIVE_METHODS'
    assert len(result['native_capabilities_consumed']) == 11
    assert set(result['native_capabilities_consumed']) == set(result['native_methodology_aliases_consumed'])
    assert result['dynamic_weight_replay']['signals'] == 12
    assert result['dynamic_weight_replay']['max_abs_weight_error'] <= 1e-9
    assert result['proper_scoring']['calibration_neutralized'] is True
    assert abs(result['proper_scoring']['frozen_calibrated_brier'] - 0.09) < 1e-12
    assert abs(result['proper_scoring']['uniform_brier'] - 0.09) < 1e-12
    assert result['post_result_marginal_utility']['full_hits'] == report['hit_count']
    assert result['post_result_marginal_utility']['learning_state_written'] is False
    assert result['named_external_skill_executed'] is False
    assert result['predictive_weight_authorized'] is False
    assert result['prospective_superiority_proven'] is False
    assert len(result['sha256']) == 64
    again = pr._operational_capability_consumption(freeze, report['official_result'])
    assert again == result
    assert hashlib.sha256(json.dumps(freeze, sort_keys=True).encode()).hexdigest() == before


def test_operational_skill_consumers_reject_frozen_weight_mismatch():
    from copy import deepcopy
    import pytest
    freeze, report = _real_operational_skill_fixture()
    altered = deepcopy(freeze)
    altered['challenger']['weights']['freq1000'] += 0.01
    with pytest.raises(ValueError, match='does not reproduce frozen Challenger weights'):
        pr._operational_capability_consumption(altered, report['official_result'])


def test_operational_skill_consumers_reject_probability_and_lineage_tampering():
    from copy import deepcopy
    import pytest
    freeze, report = _real_operational_skill_fixture()
    invalid = deepcopy(freeze)
    invalid['challenger']['rank_score_calibration']['probabilities_by_number']['1'] = 0.8
    with pytest.raises(ValueError, match='probability mass does not sum to six'):
        pr._operational_capability_consumption(invalid, report['official_result'])
    foreign = deepcopy(freeze)
    foreign['challenger']['raw_signals']['freq25']['cutoff_contest'] += 1
    with pytest.raises(ValueError, match='cutoff mismatch'):
        pr._operational_capability_consumption(foreign, report['official_result'])


def test_operational_skill_consumption_not_fabricated_for_legacy_freeze(tmp_path: Path):
    active = _fixture(tmp_path, reported_hits=2)
    result = pr.emit_post_result_report(tmp_path, active)
    diag = result['report']['operational_capability_consumption']
    assert diag['status'] == 'UNAVAILABLE_LEGACY_FREEZE'
    assert diag['native_capabilities_consumed'] == []
    assert diag['predictive_weight_authorized'] is False


def test_post_result_report_executes_real_native_skill_consumers_end_to_end(tmp_path: Path):
    from copy import deepcopy
    active = _fixture(tmp_path)
    freeze, _source_report = _real_operational_skill_fixture()
    frozen = deepcopy(freeze)
    frozen['target_contest'] = 999
    frozen['cutoff_contest'] = 998
    frozen.pop('data_file', None)  # fixture does not carry a verified 998 cutoff archive
    for row in frozen['challenger']['raw_signals'].values():
        row['target_contest'] = 999
        row['cutoff_contest'] = 998
    frozen_path = tmp_path / active['state_paths']['freeze']
    frozen_path.write_text(json.dumps(frozen), encoding='utf-8')
    sha = pr._sha256_file(frozen_path)
    active['freeze_authority']['sha256'] = sha
    ledger_path = tmp_path / active['state_paths']['ledger']
    ledger = json.loads(ledger_path.read_text())
    ledger['events'][0]['freeze_sha256'] = sha
    ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
    result = pr.emit_post_result_report(tmp_path, active)
    assert result['status'] == 'EMITTED'
    report = result['report']
    real = report['operational_capability_consumption']
    assert real['status'] == 'PASS'
    assert len(real['native_capabilities_consumed']) == 11
    assert real['dynamic_weight_replay']['reproduces_frozen_weights'] is True
    assert real['post_result_marginal_utility']['full_hits'] == len(
        set(frozen['challenger']['top6']) & set(report['official_result']))
    assert real['actual_result_used_only_after_freeze'] is True
    assert real['named_external_skill_executed'] is False
    assert real['predictive_weight_authorized'] is False
    assert 'Consumo efetivo de competências nativas' in (
        tmp_path / result['markdown_file']).read_text(encoding='utf-8')
    assert pr.emit_post_result_report(tmp_path, active)['status'] == 'EXISTING_VALID'


def test_native_execution_receipts_are_individually_real_consumed_and_hashed():
    from smart_skill_runtime import LIVE_POST_RESULT_BINDINGS
    freeze, report = _real_operational_skill_fixture()
    result = pr._operational_capability_consumption(freeze, report['official_result'])
    receipts = result['native_execution_receipts']
    assert result['native_execution_receipts_verified'] is True
    assert result['execution_receipt_count'] == len(LIVE_POST_RESULT_BINDINGS) == 11
    assert set(receipts) == set(result['native_capabilities_consumed'])
    assert {r['native_function_executed'] for r in receipts.values()}
    for capability, receipt in receipts.items():
        assert receipt['capability'] == capability
        unsigned = dict(receipt)
        observed = unsigned.pop('execution_sha256')
        assert observed == pr._sha256_json(unsigned)
        assert receipt['consumer'] == 'smart_post_result_report._operational_capability_consumption'
        assert receipt['decision_effect'] == 'POST_RESULT_DIAGNOSTIC_ONLY'
        assert receipt['external_skill_code_executed'] is False
        assert receipt['predictive_weight_authorized'] is False
    assert receipts['machine-learning-model-validation']['observed_output']['max_abs_weight_error'] == 0.0
    assert receipts['statistical-analysis']['observed_output']['marginal_utility_sha256'] == result['post_result_marginal_utility']['marginal_utility_sha256']
    assert receipts['superforecasting']['observed_output']['brier'] == result['proper_scoring']['frozen_calibrated_brier']


def test_post_result_rejects_forged_native_execution_receipt(monkeypatch):
    import pytest
    import smart_skill_runtime
    freeze, report = _real_operational_skill_fixture()
    original = smart_skill_runtime.invoke_live_native
    def forged(*args, **kwargs):
        rec = original(*args, **kwargs)
        rec['observed_output']['fabricated'] = 1
        return rec
    monkeypatch.setattr(smart_skill_runtime, 'invoke_live_native', forged)
    with pytest.raises(ValueError, match='native capability receipt invalid'):
        pr._operational_capability_consumption(freeze, report['official_result'])


def test_live_capability_invocation_rejects_quarantine_and_target_tampering():
    import pytest
    from copy import deepcopy
    from smart_skill_runtime import invoke_live_native
    freeze, report = _real_operational_skill_fixture()
    with pytest.raises(KeyError, match='no real post-result native execution'):
        invoke_live_native('z3-formal-verification', freeze, report['official_result'])
    altered = deepcopy(freeze)
    altered['challenger']['raw_signals']['freq25']['target_contest'] -= 1
    with pytest.raises(ValueError, match='requires causal and same-target'):
        invoke_live_native('openai-validate-data', altered, report['official_result'])


def test_frozen_structural_capabilities_execute_real_libraries_with_provenance():
    from smart_skill_runtime import consume_frozen_structural_capabilities
    freeze, _ = _real_operational_skill_fixture()
    root = Path(__file__).resolve().parent
    result = consume_frozen_structural_capabilities(freeze, root)
    assert result['status'] == 'PASS'
    assert result['execution_receipts_count'] == 7
    assert result['data_quality']['cutoff'] == freeze['cutoff_contest']
    assert result['data_quality']['rows'] == freeze['cutoff_contest']
    assert result['third_party_libraries_actually_called'] == ['statsmodels', 'networkx', 'ruptures', 'ortools']
    assert result['shared_solver_executions'] == 2
    assert result['receipts']['operations-research-algorithm-developer']['observed_output']['independent_constrained_solver_executed'] is True
    assert result['receipts']['google-or-tools']['observed_output']['frozen_champion_reproduced'] is True
    assert result['receipts']['statsmodels']['observed_output']['ljung_box_sum_pvalues']
    assert result['receipts']['networkx']['observed_output']['edges'] > 0
    assert result['receipts']['ruptures']['observed_output']['diagnostic_only'] is True
    assert result['receipts']['multiple-testing-fdr-statsmodels']['observed_output']['hypotheses'] == 3
    assert result['predictive_weight_authorized'] is False
    assert result['outcome_used_for_structural_methods'] is False
    validated = pr._structural_capability_diagnostic(freeze, root)
    assert validated == result
    again = pr._structural_capability_diagnostic(freeze, root)
    assert again['sha256'] == result['sha256']


def test_frozen_structural_capabilities_reject_data_hash_and_future_cutoff():
    from copy import deepcopy
    import pytest
    from smart_skill_runtime import consume_frozen_structural_capabilities
    freeze, _ = _real_operational_skill_fixture()
    root = Path(__file__).resolve().parent
    wrong_digest = deepcopy(freeze)
    wrong_digest['data_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='digest mismatch'):
        consume_frozen_structural_capabilities(wrong_digest, root)
    wrong_cutoff = deepcopy(freeze)
    wrong_cutoff['cutoff_contest'] -= 1
    with pytest.raises(ValueError, match='cutoff must precede target'):
        consume_frozen_structural_capabilities(wrong_cutoff, root)
    outside = deepcopy(freeze)
    outside['data_file'] = '../outside-sensitive-data.xlsx'
    with pytest.raises(ValueError, match='missing or outside canonical root'):
        consume_frozen_structural_capabilities(outside, root)


def test_post_result_rejects_forged_structural_execution_receipt(monkeypatch):
    import pytest
    import smart_skill_runtime
    freeze, _ = _real_operational_skill_fixture()
    root = Path(__file__).resolve().parent
    original = smart_skill_runtime.consume_frozen_structural_capabilities
    def forged(*args, **kwargs):
        payload = original(*args, **kwargs)
        payload['receipts']['statsmodels']['observed_output']['fabricated'] = 42
        payload['sha256'] = pr._sha256_json({k:v for k,v in payload.items() if k!='sha256'})
        return payload
    monkeypatch.setattr(smart_skill_runtime, 'consume_frozen_structural_capabilities', forged)
    with pytest.raises(ValueError, match='structural capability receipt hash invalid'):
        pr._structural_capability_diagnostic(freeze, root)


def test_real_frozen_structural_consumer_reaches_post_result_report(tmp_path: Path):
    import shutil
    from copy import deepcopy
    root = Path(__file__).resolve().parent
    freeze, original_report = _real_operational_skill_fixture()
    contest = freeze['target_contest']
    frozen_path = tmp_path/'runtime'/'learning_epochs'/f'operator-{contest}-test'/f'SMART_{contest}_CHAMPION_CHALLENGER_FREEZE.json'
    frozen_path.parent.mkdir(parents=True)
    # Copy the actual pre-result cutoff dataset, without moving the result into it.
    data_path = tmp_path/freeze['data_file']
    data_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root/freeze['data_file'], data_path)
    frozen = deepcopy(freeze)
    frozen.pop('portfolio_file', None)
    frozen.pop('portfolio_sha256', None)
    frozen_path.write_text(json.dumps(frozen,ensure_ascii=False),encoding='utf-8')
    freeze_sha = pr._sha256_file(frozen_path)
    ledger_path = frozen_path.parent/'SMART_SIGNAL_LEDGER.json'
    ledger_path.write_text(json.dumps({'events':[
        {'event_type':'FREEZE','target_contest':contest,'freeze_sha256':freeze_sha},
        {'event_type':'ADJUDICATION','target_contest':contest,
         'actual_numbers':original_report['official_result'],'hits':original_report['champion_hits']},
    ]}),encoding='utf-8')
    active={'target_contest':contest,'freeze_authority':{'sha256':freeze_sha},
            'state_paths':{'freeze':str(frozen_path.relative_to(tmp_path)),
                           'ledger':str(ledger_path.relative_to(tmp_path))}}
    emitted = pr.emit_post_result_report(tmp_path, active)
    assert emitted['status']=='EMITTED'
    structural = emitted['report']['structural_capability_consumption']
    assert structural['status']=='PASS'
    assert structural['execution_receipts_count']==7
    assert structural['receipts']['google-or-tools']['observed_output']['frozen_champion_reproduced'] is True
    assert len(emitted['report']['operational_capability_consumption']['native_execution_receipts']) == 11
    assert 'Execuções estruturais vinculadas ao histórico congelado' in (
        tmp_path/emitted['markdown_file']).read_text()
    assert pr.emit_post_result_report(tmp_path,active)['status']=='EXISTING_VALID'

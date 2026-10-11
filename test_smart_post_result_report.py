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

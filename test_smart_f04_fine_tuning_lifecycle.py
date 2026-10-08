from pathlib import Path

import smart_fine_tuning_lifecycle as lifecycle


def _report(data_sha: str, target: int):
    report = {
        "schema": "SMART_AI_FINE_TUNING_1",
        "status": "PASS",
        "target_contest": target,
        "cutoff_contest": target - 1,
        "data_file": "synthetic.xlsx",
        "data_sha256": data_sha,
        "start": 1000,
        "partitions": {"calibration": [1500, 2499], "validation": [2500, 2850], "holdout": [2851, target - 1]},
        "candidate_count": 1,
        "selection": {"selected_candidate_id": "baseline", "holdout_used_for_selection": False},
        "adjudication": {"effective_candidate_id": "baseline", "promotion_authorized": False},
        "results": [{"candidate": {"candidate_id": "baseline", "eta": 0.6931471805599453, "redundancy_threshold": 0.85, "meta_strength": 0.06}}],
        "guardrails": {"future_result_used": False, "holdout_used_for_selection": False},
    }
    report["sha256"] = lifecycle.sha256_json(report)
    return report


def test_f04_lifecycle_generates_and_reuses_epoch_authority(tmp_path, monkeypatch):
    data = tmp_path / "cutoff.xlsx"
    data.write_bytes(b"causal-cutoff")
    epoch = tmp_path / "epoch"
    calls = {"run": 0}

    def fake_run(data_file, target_contest, *, start, max_workers):
        calls["run"] += 1
        return _report(lifecycle.sha256_file(Path(data_file)), int(target_contest))

    monkeypatch.setattr(lifecycle, "run_fine_tuning", fake_run)
    first = lifecycle.ensure_pre_freeze_authority(data, 3001, epoch, max_workers=1)
    second = lifecycle.ensure_pre_freeze_authority(data, 3001, epoch, max_workers=1)

    assert calls["run"] == 1
    assert first["reused_existing_authority"] is False
    assert second["reused_existing_authority"] is True
    assert first["data_sha256"] == lifecycle.sha256_file(data)
    assert first["holdout_used_for_selection"] is False
    assert first["future_result_used"] is False
    assert first["effective_candidate_id"] == "baseline"


def test_f04_lifecycle_rejects_partial_artifacts(tmp_path):
    data = tmp_path / "cutoff.xlsx"
    data.write_bytes(b"causal-cutoff")
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    (epoch / lifecycle.REPORT_NAME).write_text("{}", encoding="utf-8")
    import pytest
    with pytest.raises(RuntimeError, match="partial fine-tuning"):
        lifecycle.ensure_pre_freeze_authority(data, 3001, epoch, max_workers=1)


def test_f04_full_process_wires_epoch_authority_into_freeze():
    source = Path("smart_full_process_pipeline.py").read_text(encoding="utf-8")
    assert "ensure_pre_freeze_authority(" in source
    assert 'ai_hyperparameter_authority_path=Path(fine_tuning["authority_file"])' in source
    assert '"fine_tuning_consumed_by_challenger"' in source

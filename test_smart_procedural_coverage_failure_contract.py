import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "smart_procedural_coverage_gate.py"


def run_gate(root):
    return subprocess.run(
        [sys.executable, "-E", "-B", "-X", "utf8", str(SCRIPT)],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def test_missing_procedural_inputs_fail_closed_with_structured_output(tmp_path):
    result = run_gate(tmp_path)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "BLOCKED_MISSING_INPUT"
    assert report["predictive_weight_authorized"] is False
    assert report["decision"] == "BLOCK_PREDICTIVE_PROMOTION"
    assert report["erro"] and report["causa"] and report["acao_sugerida"]
    assert not (tmp_path / "runtime/procedural_sources/PROCEDURAL_COVERAGE_GATE.json").exists()


def test_malformed_procedural_inputs_fail_closed_with_structured_output(tmp_path):
    source = tmp_path / "runtime/procedural_sources/CRONOGRAM_ARCHIVE_MANIFEST.json"
    source.parent.mkdir(parents=True)
    source.write_text("{invalid", encoding="utf-8")
    result = run_gate(tmp_path)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "BLOCKED_INVALID_INPUT"
    assert report["predictive_weight_authorized"] is False
    assert report["decision"] == "BLOCK_PREDICTIVE_PROMOTION"


def test_valid_diagnostic_inputs_preserve_promotion_block_and_metrics(tmp_path):
    documents = {
        "runtime/procedural_sources/CRONOGRAM_ARCHIVE_MANIFEST.json": {"documents": [{"status": "FOUND"}]},
        "runtime/procedural_sources/MEGA_PROCEDURAL_CRONOGRAM_DATASET.json": {"rows": [{"evidence_status": "VERIFIED_CONTEST_DATE_IN_OFFICIAL_CRONOGRAM", "location_candidate_raw": "SAO PAULO"}]},
        "runtime/procedural_sources/YOUTUBE_PROCEDURAL_RECENT.json": {"rows": [{"status": "PASS", "ball_case_identifier": "A"}, {"status": "PASS", "ball_case_identifier": "B"}]},
        "runtime/historical_training_shadow/PROCEDURAL_VENUE_EXPERIMENT.json": {"evaluation_venue_counts": {"A": 20, "B": 20}},
    }
    for relative, document in documents.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
    result = run_gate(tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    saved = json.loads((tmp_path / "runtime/procedural_sources/PROCEDURAL_COVERAGE_GATE.json").read_text(encoding="utf-8"))
    assert saved == report
    assert report["documents_found"] == report["verified_contest_date_rows"] == 1
    assert report["predictive_weight_authorized"] is False
    assert report["decision"] == "BLOCK_PREDICTIVE_PROMOTION"

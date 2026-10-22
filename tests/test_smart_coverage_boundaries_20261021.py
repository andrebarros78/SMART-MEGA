"""Exercise rejected evidence and recovery paths against the real modules."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import adjudicate_signal_challenger as adjudication
import smart_agent_skill_orchestration as orchestration
import smart_canonical_history_advance as history
import smart_continuous_red_team as redteam
import smart_global_integrity as integrity
import smart_independent_audit as independent
import smart_material_deficiency_registry as deficiencies
import smart_sequential_prospective_proof as sequential

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_real_redteam_cli_runs_all_scenarios_without_touching_repository(tmp_path):
    names = (*redteam.BEHAVIORAL_FILES, "smart_continuous_red_team.py")
    before = {name: digest(ROOT / name) for name in names}
    for name in names:
        shutil.copyfile(ROOT / name, tmp_path / name)
    result = subprocess.run(
        [sys.executable, str(ROOT / "smart_continuous_red_team.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((tmp_path / redteam.REPORT_PATH).read_text())
    assert set(report["scenarios"]) == set(redteam.EXPECTED_SCENARIOS)
    assert all(report["checks"].values()) and report["failed"] == []
    assert report["prospective_predictive_claim"] is False
    assert redteam.verify_latest_report(tmp_path / redteam.REPORT_PATH, ROOT)["status"] == "PASS"
    assert before == {name: digest(ROOT / name) for name in names}


def test_relative_independent_audit_hash_uses_module_root():
    name = "SMART_DATA_CONTRACT.md"
    assert independent.sha256_file(Path(name)) == digest(ROOT / name)


def test_adjudication_resolver_rejects_ambiguous_same_hash_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "epoch").mkdir()
    first = tmp_path / "freeze.json"
    second = tmp_path / "epoch" / "freeze.json"
    first.write_bytes(b"same frozen bytes")
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match="ambiguous"):
        adjudication._resolve_freeze_file("freeze.json", digest(first), tmp_path / "epoch/ledger.json")
    assert first.read_bytes() == second.read_bytes()


def test_adjudication_resolver_missing_relative_and_resolution_io_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert adjudication._resolve_evidence_file("nested/proof.json", {"freeze_file": "history/freeze.json"}) == Path("history/proof.json")
    original = Path.resolve

    def unavailable(path, *args, **kwargs):
        if str(path) == "absent.json":
            raise OSError("filesystem resolution unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", unavailable)
    assert adjudication._resolve_freeze_file("absent.json", "0" * 64, tmp_path / "ledger.json") == Path("absent.json")


@pytest.mark.parametrize("kind", ["native_ambiguous", "native_wrong_first", "windows_directory", "windows_escape"])
def test_sequential_evidence_requires_unique_in_root_hash(tmp_path, kind):
    root = tmp_path / "root"
    root.mkdir()
    good = root / "one" / "artifact.bin"
    good.parent.mkdir()
    good.write_bytes(b"verified")
    expected = digest(good)
    raw = tmp_path / "retired" / "artifact.bin"
    if kind == "native_ambiguous":
        other = root / "two" / "artifact.bin"
        other.parent.mkdir()
        other.write_bytes(good.read_bytes())
        with pytest.raises(ValueError, match="ambiguous"):
            sequential._resolve_verified_artifact(root, raw, expected, "artifact")
    elif kind == "native_wrong_first":
        wrong = root / "zero" / "artifact.bin"
        wrong.parent.mkdir()
        wrong.write_bytes(b"wrong")
        assert sequential._resolve_verified_artifact(root, raw, expected, "artifact") == good
    elif kind == "windows_directory":
        (root / "artifact.bin").mkdir()
        assert sequential._resolve_verified_artifact(root, r"C:\retired\artifact.bin", expected, "artifact") == good
    else:
        good.unlink()
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"verified")
        good.symlink_to(outside)
        with pytest.raises(ValueError, match="escapes project root"):
            sequential._resolve_verified_artifact(root, r"C:\retired\artifact.bin", expected, "artifact")


def test_history_rejects_invalid_hash_and_nonmatching_archive_bytes(tmp_path):
    epoch = tmp_path / "runtime/learning_epochs/e1"
    epoch.mkdir(parents=True)
    with pytest.raises(ValueError, match="hash mismatch"):
        history._resolve_adjudication_result_evidence(tmp_path, {"result_data_file": "missing", "result_data_sha256": "not-a-hash"}, epoch, 4)
    archive = tmp_path / "SMART_STATE_ARCHIVE"
    archive.mkdir()
    (archive / ("wrong." + "a" * 64 + ".xlsx")).write_bytes(b"untrusted")
    with pytest.raises(ValueError, match="hash mismatch"):
        history._resolve_adjudication_result_evidence(tmp_path, {"result_data_file": "missing", "result_data_sha256": "a" * 64}, epoch, 4)


def test_history_metadata_enrichment_preserves_core_and_existing_values():
    from test_smart_canonical_history_advance import _frame
    original = _frame(2)
    assert not history._core_history_equal(original.drop(columns="Bola1"), original)
    assert not history._core_history_equal(original.iloc[:1], original)
    assert not history._metadata_enrichment_only(original.iloc[:1], original)
    changed = original.copy()
    changed.loc[0, "Bola1"] = 60
    assert not history._metadata_enrichment_only(changed, original)
    filled = original.copy()
    filled["Ganhadores 6 acertos"] = [0, 1]
    assert history._metadata_enrichment_only(filled, original)
    assert not history._metadata_enrichment_only(filled, filled)


@pytest.mark.parametrize("kind", ["directory", "invalid_json", "not_object"])
def test_history_replay_preserves_invalid_receipt_for_investigation(tmp_path, monkeypatch, kind):
    from test_smart_canonical_history_advance import _fixture
    canonical, _, _, _, active = _fixture(tmp_path, monkeypatch)
    history.advance_completed_epoch(tmp_path, active)
    before = canonical.read_bytes()
    receipt = tmp_path / "SMART_CANONICAL_HISTORY_ADVANCE_4.json"
    receipt.unlink()
    if kind == "directory":
        receipt.mkdir()
    else:
        receipt.write_text("{" if kind == "invalid_json" else "[]")
    with pytest.raises(ValueError, match="existing canonical history advance proof invalid"):
        history.advance_completed_epoch(tmp_path, active)
    assert canonical.read_bytes() == before
    assert receipt.is_dir() if kind == "directory" else receipt.read_text() == ("{" if kind == "invalid_json" else "[]")


def test_global_manifest_detects_new_critical_file_not_in_legacy_hash_list(tmp_path, monkeypatch):
    import test_smart_global_integrity as fixtures
    monkeypatch.setattr(integrity, "CRITICAL_SOURCE_FILES", ("a.py",))
    monkeypatch.setattr(integrity, "REQUIRED_GLOBAL_COVERAGE_SOURCES", ("a.py",))
    monkeypatch.setattr(redteam, "verify_latest_report", lambda *a, **k: fixtures._red_status())
    (tmp_path / "a.py").write_text("VALUE = 1\n")
    (tmp_path / integrity.DEFAULT_RED_TEAM_PATH).write_text("red")
    fixtures._write_p14(tmp_path)
    cov = fixtures._write_coverage(tmp_path)
    junit = fixtures._write_junit(tmp_path)
    gate = fixtures._gate()
    proof = integrity.build_global_integrity_proof(tmp_path, gate, junit, [(cov.name, "a.py")])
    proof_path = tmp_path / integrity.DEFAULT_PROOF_PATH
    proof_path.write_text(json.dumps(proof))
    gate["global_integrity"] = {"file": proof_path.name, "sha256": digest(proof_path)}
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(gate))
    assert integrity.verify_global_integrity(tmp_path, gate_path, proof_path)["status"] == "PASS"
    (tmp_path / "smart_operator.py").write_text("VALUE = 2\n")
    with pytest.raises(ValueError, match="critical code manifest is stale"):
        integrity.verify_global_integrity(tmp_path, gate_path, proof_path)


@pytest.mark.parametrize("failure", ["backup_exists", "source_rename", "backup_cleanup", "concurrent_delete"])
def test_deficiency_replace_fallback_preserves_recoverable_bytes(tmp_path, monkeypatch, failure):
    source, target = tmp_path / "source", tmp_path / "target"
    backup = tmp_path / "target.replace-backup"
    source.write_bytes(b"new")
    target.write_bytes(b"old")
    original_replace, original_rename, original_unlink = Path.replace, Path.rename, Path.unlink

    def replace(path, destination):
        if path == source:
            raise PermissionError("replace denied")
        return original_replace(path, destination)

    def rename(path, destination):
        if failure == "source_rename" and path == source:
            raise OSError("rename denied")
        return original_rename(path, destination)

    def unlink(path, *args, **kwargs):
        if path == backup:
            if failure == "concurrent_delete":
                original_unlink(target)
            raise PermissionError("cleanup denied")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(Path, "rename", rename)
    if failure == "backup_exists":
        backup.write_bytes(b"prior backup")
    if failure in {"backup_cleanup", "concurrent_delete"}:
        monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises((PermissionError, OSError)):
        deficiencies._replace_with_retry(source, target, attempts=1, delay_seconds=0)
    if failure in {"backup_exists", "source_rename"}:
        assert target.read_bytes() == b"old" and source.read_bytes() == b"new"
    else:
        assert backup.read_bytes() == b"old"
        if failure == "backup_cleanup":
            assert target.read_bytes() == b"new"


def test_deficiency_upsert_appends_then_updates_without_reopening_unresolved(tmp_path):
    path = tmp_path / "registry.json"
    first = {"id": "D1", "severity": "P1", "status": "OPEN", "summary": "first", "evidence": []}
    second = {**first, "id": "D2", "summary": "second"}
    deficiencies.write_registry(path, deficiencies.build_registry([first]))
    assert deficiencies.upsert_deficiency(path, second, root=tmp_path)["entry_count"] == 2
    second["summary"] = "still open"
    result = deficiencies.upsert_deficiency(path, second, root=tmp_path)
    assert result["open_count"] == 2
    assert result["open_entries"][1]["status"] == "OPEN"


@pytest.mark.parametrize("kind", ["empty_active", "bad_hold", "valid_hold", "inactive_hold"])
def test_orchestration_auto_respects_hold_and_actual_lifecycle(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(orchestration, "lifecycle_runtime_phase", lambda root: "PRE_FREEZE")
    if kind == "empty_active":
        (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text("{}")
    else:
        path = tmp_path / "SMART_NEXT_CYCLE_HOLD.json"
        path.write_text("{" if kind == "bad_hold" else json.dumps({"status": "AWAITING_OPERATOR_APPLY_OR_GENERATE", "prepare_allowed": False, "generation_allowed": kind != "valid_hold"}))
    if kind == "bad_hold":
        with pytest.raises(ValueError, match="hold cannot be parsed"):
            orchestration.resolve_runtime_phase(tmp_path)
    else:
        assert orchestration.resolve_runtime_phase(tmp_path) == ("POST_RESULT_HOLD" if kind == "valid_hold" else "PRE_FREEZE")


def test_orchestration_hold_context_and_build_are_non_operational(tmp_path, monkeypatch):
    import smart_current_epoch_contract as current
    context = {"status": "POST_RESULT_HOLD", "target_contest": 4, "cutoff_contest": 3, "data_file": "Mega-Sena.xlsx", "data_sha256": "a" * 64}
    monkeypatch.setattr(current, "resolve", lambda root: context)
    hold = orchestration._resolve_post_result_hold_context(tmp_path)
    assert hold["ledger_file"] is None and hold["prepare_allowed"] is False
    report = orchestration.build_orchestration(ROOT, "POST_RESULT_HOLD")
    assert report["checks"]["post_result_hold_has_no_generation_authority"] is True
    context["status"] = "FROZEN"
    with pytest.raises(ValueError, match="hold context is not active"):
        orchestration._resolve_post_result_hold_context(tmp_path)


def test_orchestration_build_phase_does_not_gain_test_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestration, "lifecycle_runtime_phase", lambda root: "BUILD")
    monkeypatch.setattr(orchestration._test_identity, "_authorized_pytest_sandbox", lambda root: False)
    monkeypatch.setattr(orchestration, "canonical_root", lambda root: Path(root))
    assert orchestration.resolve_runtime_phase(tmp_path) == "BUILD"


@pytest.mark.parametrize("expected_matches", [False, True])
def test_relative_freeze_resolution_returns_the_file_it_checked(tmp_path, monkeypatch, expected_matches):
    monkeypatch.chdir(tmp_path)
    artifact = tmp_path / "freeze.json"
    artifact.write_bytes(b"local frozen evidence")
    expected = digest(artifact) if expected_matches else "0" * 64
    selected = adjudication._resolve_freeze_file("freeze.json", expected, tmp_path / "ledger.json")
    assert selected == artifact and selected.is_absolute()
    assert adjudication.sha256(selected) == digest(artifact)


@pytest.mark.parametrize("outside", [False, True])
def test_portfolio_cli_uses_canonical_root_and_blocks_escape(tmp_path, monkeypatch, capsys, outside):
    import smart_portfolio_pipeline as portfolio
    monkeypatch.setattr(portfolio._test_identity, "_authorized_pytest_sandbox", lambda root: False)
    monkeypatch.setattr(portfolio, "canonical_root", lambda: tmp_path)
    calls = []
    def build(freeze, out):
        calls.append((freeze, out))
        return {"status": "VALIDATED", "target_contest": 4, "portfolio": {"games": [], "solver_status": "TEST",
                "metrics": {"unique_number_count": 0, "max_pairwise_overlap_observed": 0}}}
    monkeypatch.setattr(portfolio, "build_portfolio_package", build)
    monkeypatch.setattr(sys, "argv", ["portfolio", "--freeze", "../freeze.json" if outside else "freeze.json", "--out", "out.json"])
    if outside:
        with pytest.raises(ValueError):
            portfolio.main()
        assert calls == []
    else:
        portfolio.main()
        assert calls == [(tmp_path / "freeze.json", tmp_path / "out.json")]
        assert json.loads(capsys.readouterr().out)["status"] == "VALIDATED"
    assert not (tmp_path / "out.json").exists()


def test_relative_state_archive_is_hashed_at_the_checked_location(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    archive = tmp_path / "state.json"
    archive.write_bytes(b"immutable state evidence")
    expected = digest(archive)
    frozen = {"signal_state_archive_file": "state.json", "signal_state_archive_sha256": expected, "signal_state_sha256": expected}
    ledger_event = {"freeze_file": str(tmp_path / "freeze.json"), "state_archive_file": "state.json", "state_archive_sha256": expected}
    adjudication._validate_state_archive_evidence(ledger_event, frozen)
    assert archive.read_bytes() == b"immutable state evidence"

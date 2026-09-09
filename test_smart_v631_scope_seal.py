from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_scope_seal_runtime_has_no_tracked_executable_residue():
    runtime = ROOT / "runtime"
    bad = sorted(
        p.relative_to(ROOT).as_posix()
        for p in runtime.rglob("*")
        if p.is_file() and p.suffix.lower() in {".py", ".cmd", ".ps1"}
    )
    assert bad == []


def test_scope_seal_runtime_has_no_obsolete_log_or_exit_residue():
    runtime = ROOT / "runtime"
    bad = sorted(
        p.relative_to(ROOT).as_posix()
        for p in runtime.rglob("*")
        if p.is_file() and p.suffix.lower() in {".log", ".exit", ".tmp", ".bak", ".old", ".orig", ".dmp"}
    )
    assert bad == []


def test_scope_seal_active_executables_do_not_bind_historical_project_root():
    needle = r"C:\New Projet\SMART-MEGA"
    allowed = {"smart_agent_skill_orchestration.py"}
    hits = []
    for pattern in ("*.py", "*.cmd", "*.ps1"):
        for p in ROOT.glob(pattern):
            if p.name.startswith("test_") or p.name in allowed:
                continue
            text = p.read_text(encoding="utf-8-sig", errors="ignore")
            if needle.lower() in text.lower():
                hits.append(p.name)
    assert sorted(hits) == []


def test_scope_seal_archive_is_explicitly_non_runtime():
    policy = (ROOT / "SMART_ARCHIVE_RUNTIME_BOUNDARY.md").read_text(encoding="utf-8-sig")
    for marker in (
        "NOT_RUNTIME",
        "NOT_OPERATOR_ENTRYPOINT",
        "NO_AUTO_EXECUTION",
        "NO_PREDICTIVE_AUTHORITY",
        "NO_FREEZE_AUTHORITY",
        "NO_DEPLOYMENT_AUTHORITY",
    ):
        assert marker in policy


def test_scope_seal_release_contains_no_secret_named_files():
    forbidden_names = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
    forbidden_suffixes = {".pem", ".key", ".p12", ".pfx"}
    bad = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".venv" in p.parts or ".git" in p.parts:
            continue
        if p.name.lower() in forbidden_names or p.suffix.lower() in forbidden_suffixes:
            bad.append(p.relative_to(ROOT).as_posix())
    assert sorted(bad) == []

def test_scope_seal_sbom_matches_pinned_lock():
    import hashlib
    import json
    lock = ROOT / "requirements.lock.txt"
    sbom = json.loads((ROOT / "SMART_DEPENDENCY_SBOM_R3.json").read_text(encoding="utf-8-sig"))
    assert sbom["schema"] == "SMART_DEPENDENCY_SBOM_2"
    assert sbom["component_count"] == 75
    assert sbom["all_versions_pinned"] is True
    assert sbom["all_installed_versions_match"] is True
    assert sbom["lock_sha256"] == hashlib.sha256(lock.read_bytes()).hexdigest()


def test_scope_seal_portable_identity_prefers_r3_proof(tmp_path):
    import shutil
    import smart_continuity_consolidator as cc
    proof_dir = tmp_path / "release_evidence"
    proof_dir.mkdir()
    shutil.copy2(ROOT / "release_evidence" / "R2_ENGINEERING_PROOF.json", proof_dir / "R2_ENGINEERING_PROOF.json")
    shutil.copy2(ROOT / "release_evidence" / "R3_SCOPE_SEAL_SOURCE_PROOF.json", proof_dir / "R3_SCOPE_SEAL_SOURCE_PROOF.json")
    identity = cc._source_identity(tmp_path)
    assert identity["source"] == "PORTABLE_RELEASE_PROOF"
    assert identity["release"] == "SMART-MEGA-v6.3.1-PORTABLE-SCOPE-SEAL-R3"
    assert identity["base_commit"] == "15aebb7c3a45ea5139d71f3aa947e61397a2a912"


def test_scope_seal_tampered_r3_proof_fails_closed_even_if_r2_exists(tmp_path):
    import json
    import shutil
    import pytest
    import smart_continuity_consolidator as cc
    proof_dir = tmp_path / "release_evidence"
    proof_dir.mkdir()
    shutil.copy2(ROOT / "release_evidence" / "R2_ENGINEERING_PROOF.json", proof_dir / "R2_ENGINEERING_PROOF.json")
    r3 = proof_dir / "R3_SCOPE_SEAL_SOURCE_PROOF.json"
    shutil.copy2(ROOT / "release_evidence" / "R3_SCOPE_SEAL_SOURCE_PROOF.json", r3)
    doc = json.loads(r3.read_text(encoding="utf-8-sig"))
    doc["objective"] = "tampered"
    r3.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="self-hash invalid"):
        cc._source_identity(tmp_path)

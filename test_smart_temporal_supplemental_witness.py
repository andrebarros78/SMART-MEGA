"""Adversarial temporal authority tests: no retroactive privilege escalation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import smart_temporal_supplemental_witness as tw


ROOT = Path(__file__).resolve().parent
SNAP = ROOT / "release_evidence/RESULT_3071/GITHUB_CONNECTOR_PR54_POSTDRAW_SNAPSHOT.json"


def evidence():
    j = json.loads(SNAP.read_text(encoding="utf-8"))
    return j["pr"], j["commits"]


def local_root(tmp_path, monkeypatch):
    reg = tw._git_registration(ROOT)
    monkeypatch.setattr(tw, "_git_registration", lambda root: copy.deepcopy(reg))
    relative = Path(reg["source_freeze"]["path"])
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    source = ROOT / relative
    path.write_bytes(source.read_bytes())
    for name in ("SMART_ACTIVE_EPOCH.json", "SMART_OPERATOR_RESULT_3071.json"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    return tmp_path, path, reg


def test_verified_current_github_evidence_remains_review_only():
    pr, commits = evidence()
    result = tw.evaluate(ROOT, pr, commits)
    tw.verify_record(result)
    assert result["status"] == "SUPPLEMENTAL_CHRONOLOGY_CORROBORATED_REVIEW_REQUIRED"
    assert result["pre_draw_calendar_margin_days"] == 3
    assert result["original_freeze_git_blob_sha1"] == "f3814faa0dc3b5b1b1f8dd0a457787bd901d110c"
    assert result["github_pr_commits_observed"] == 8
    assert all(not result["controls"][k] for k in ("temporal_guard_pass", "allows_post_result_learning",
                                                        "allows_history_advance", "allows_champion_promotion"))
    assert result["uncertainty"]["exact_initial_PR_head_at_creation_cryptographically_proven"] is False


def test_wrong_pr_or_other_repo_denied():
    pr, commits = evidence()
    pr["number"] = 53
    with pytest.raises(ValueError, match="wrong public pull request"):
        tw.evaluate(ROOT, pr, commits)
    pr, commits = evidence()
    pr["head"]["repo"]["full_name"] = "other/repo"
    with pytest.raises(ValueError, match="wrong GitHub repository"):
        tw.evaluate(ROOT, pr, commits)


def test_post_draw_or_unzoned_timestamp_denied():
    pr, commits = evidence()
    pr["created_at"] = "2026-10-19T00:00:00Z"
    with pytest.raises(ValueError, match="not created before registered draw"):
        tw.evaluate(ROOT, pr, commits)
    pr, commits = evidence()
    pr["created_at"] = "2026-10-15T22:43:39"
    with pytest.raises(ValueError, match="timezone-aware"):
        tw.evaluate(ROOT, pr, commits)


def test_commit_reorder_replacement_and_wrong_head_denied():
    pr, commits = evidence()
    commits[1]["sha"] = "a" * 40
    with pytest.raises(ValueError, match="GitHub PR ancestry"):
        tw.evaluate(ROOT, pr, commits)
    pr, commits = evidence()
    commits[0]["sha"] = "b" * 40
    with pytest.raises(ValueError, match="head/preregistration"):
        tw.evaluate(ROOT, pr, commits)
    pr, commits = evidence()
    pr["head"]["sha"] = "c" * 40
    with pytest.raises(ValueError, match="head/preregistration"):
        tw.evaluate(ROOT, pr, commits)


def test_truncated_commits_cannot_hide_later_head():
    pr, commits = evidence()
    with pytest.raises(ValueError, match="head/preregistration"):
        tw.evaluate(ROOT, pr, commits[:-1])


def test_freeze_byte_tamper_rejected(tmp_path, monkeypatch):
    root, path, _ = local_root(tmp_path, monkeypatch)
    with path.open("ab") as fd:
        fd.write(b"\n")
    pr, commits = evidence()
    with pytest.raises(ValueError, match="original freeze differs"):
        tw.evaluate(root, pr, commits)


def test_pre_draw_authority_rewrite_to_pass_rejected(tmp_path, monkeypatch):
    root, path, _ = local_root(tmp_path, monkeypatch)
    a = json.loads((root / "SMART_ACTIVE_EPOCH.json").read_text())
    a["temporal_guard"]["status"] = "PASS"
    a["temporal_guard"]["before_scheduled_draw"] = True
    (root / "SMART_ACTIVE_EPOCH.json").write_text(json.dumps(a))
    pr, commits = evidence()
    with pytest.raises(ValueError, match="original authority"):
        tw.evaluate(root, pr, commits)


def test_result_leakage_even_with_recomputed_registration_hash_rejected(monkeypatch):
    reg = tw._git_registration(ROOT)
    reg["controls"]["result_used"] = True
    reg["controls"]["actual_numbers"] = [12, 22, 41, 45, 51, 52]
    reg["registration_sha256"] = tw.digest({k: v for k, v in reg.items() if k != "registration_sha256"})
    monkeypatch.setattr(tw, "_git_registration", lambda root: copy.deepcopy(reg))
    pr, commits = evidence()
    with pytest.raises(ValueError, match="result leakage"):
        tw.evaluate(ROOT, pr, commits)


def test_unsigned_source_snapshot_never_grants_learning_even_if_forged():
    pr, commits = evidence()
    record = tw.evaluate(ROOT, pr, commits)
    record["controls"]["allows_post_result_learning"] = True
    with pytest.raises(ValueError, match="self-hash"):
        tw.verify_record(record)
    record["sha256"] = tw.digest({k: v for k, v in record.items() if k != "sha256"})
    with pytest.raises(ValueError, match="unauthorized promotion"):
        tw.verify_record(record)


def test_bad_synthetic_positive_date_claim_cannot_override_pr_timestamp():
    pr, commits = evidence()
    pr["created_at"] = "2030-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="not created"):
        tw.evaluate(ROOT, pr, commits)


def test_only_exact_github_https_endpoints_accepted():
    for url in ("http://api.github.com/repos/andrebarros78/SMART-MEGA/pulls/54",
                "https://evil.invalid/repos/andrebarros78/SMART-MEGA/pulls/54",
                "https://api.github.com/repos/andrebarros78/SMART-MEGA/pulls/55"):
        with pytest.raises(ValueError, match="untrusted|outside allowlist"):
            tw.fetch_github_json(url)


def test_snapshot_is_recorded_as_post_draw_not_live_official():
    obj = json.loads(SNAP.read_text())
    assert obj["retrieved_after_draw"] is True
    assert obj["source_type"] == "github_authenticated_connector"
    assert obj["pr"]["created_at"] == "2026-10-15T22:43:39Z"
    assert len(obj["commits"]) == 8


def test_readonly_verification_does_not_mutate_baseline_freeze_or_authority():
    active = ROOT / "SMART_ACTIVE_EPOCH.json"
    reg = tw._git_registration(ROOT)
    freeze = ROOT / reg["source_freeze"]["path"]
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (active, freeze)]
    pr, commits = evidence()
    tw.evaluate(ROOT, pr, commits)
    assert hashes == [hashlib.sha256(p.read_bytes()).hexdigest() for p in (active, freeze)]


def test_even_forged_early_creation_timestamp_cannot_grant_learning():
    pr, commits = evidence()
    pr["created_at"] = "2026-10-01T00:00:00Z"  # Deliberately untrusted synthetic claim
    record = tw.evaluate(ROOT, pr, commits)
    tw.verify_record(record)
    assert record["controls"]["allows_post_result_learning"] is False
    assert record["controls"]["temporal_guard_pass"] is False
    assert record["uncertainty"]["signed_trusted_pre_draw_timestamp_for_exact_freeze"] is False


def test_existing_terminal_engine_rejects_recovery_despite_valid_supplement():
    """The new research module must not silently alter the production guard."""
    from smart_terminal_engine import active_epoch_context, _active_epoch_binding
    pr, commits = evidence()
    witness = tw.evaluate(ROOT, pr, commits)
    tw.verify_record(witness)
    with active_epoch_context(ROOT, 3071):
        with pytest.raises(ValueError, match="post-result recovery lacks valid pre-draw temporal guard"):
            _active_epoch_binding(ROOT)

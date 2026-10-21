from pathlib import Path
import hashlib
import json
import subprocess
import sys
import pytest

import smart_github_operator as github_operator

from smart_github_operator import allowed_artifact, command_args, _tracked_payload


def test_dispatch_requires_explicit_target_and_known_action():
    assert command_args("status")[-2:] == ["smart_operator.py", "status"]
    assert command_args("freeze", "3067")[-4:] == [
        "smart_operator.py", "freeze", "--target", "3067"
    ]
    assert command_args("catch-up", "3067", "SMART_RESULT.json")[-6:] == [
        "smart_operator.py", "catch-up", "--through", "3067",
        "--payload-file", "SMART_RESULT.json"
    ]
    with pytest.raises(ValueError, match="target"):
        command_args("freeze")
    with pytest.raises(ValueError, match="unsupported"):
        command_args("reset", "3067")
    with pytest.raises(ValueError, match="payload"):
        command_args("adjudicate", "3067")


def test_only_operational_artifacts_can_be_published():
    assert allowed_artifact("SMART_ACTIVE_EPOCH.json")
    assert allowed_artifact("Mega-Sena.xlsx")
    assert allowed_artifact("runtime/learning_epochs/epoch/SMART_SIGNAL_LEDGER.json")
    assert allowed_artifact("SMART_STATE_ARCHIVE/lineage/epoch.xlsx")
    assert allowed_artifact("SMART_STATE_ARCHIVE/lineage/file.json.abc.bak")
    assert not allowed_artifact("smart_operator.py")
    assert not allowed_artifact(".github/workflows/ci.yml")
    assert not allowed_artifact("../outside.json")
    assert not allowed_artifact("runtime/agent.py")
    assert not allowed_artifact("runtime/generated.sh")


def test_payload_cannot_escape_or_be_untracked(tmp_path: Path):
    tracked = tmp_path / "result.json"
    tracked.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="inside"):
        _tracked_payload(tmp_path, str(tmp_path.parent / "outside.json"))
    with pytest.raises(Exception):
        _tracked_payload(tmp_path, "result.json")


@pytest.mark.parametrize("artifact_bytes,should_publish", [
    (b"generated\n", True),
    (b"generated\r\n", True),
    (b"generated \r\n", False),
])
def test_successful_operation_publishes_its_state_to_git(
    tmp_path: Path, monkeypatch, artifact_bytes: bytes, should_publish: bool
):
    """Exercise the commit and remote verification path without touching main."""
    remote = tmp_path / "remote.git"
    root = tmp_path / "checkout"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch=main", str(root)], check=True, capture_output=True)

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=True
        ).stdout.strip()

    git("config", "user.name", "SMART test")
    git("config", "user.email", "smart-test@example.invalid")
    (root / "README.md").write_text("initial\\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "initial")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "main")
    before = git("rev-parse", "HEAD")

    monkeypatch.setattr(github_operator, "__file__", str(root / "smart_github_operator.py"))
    monkeypatch.setattr(
        github_operator,
        "command_args",
        lambda *_: [
            sys.executable, "-c",
            "from pathlib import Path; import json; "
            f"Path('SMART_ACTIVE_EPOCH.json').write_bytes({artifact_bytes!r}); "
            "print(json.dumps({'status':'PREPARED'}))",
        ],
    )
    monkeypatch.setenv("GITHUB_REPOSITORY", "andrebarros78/SMART-MEGA")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    if not should_publish:
        with pytest.raises(subprocess.CalledProcessError):
            github_operator.execute("prepare", "3067")
        assert git("ls-remote", "origin", "refs/heads/main").split()[0] == before
        return
    proof = github_operator.execute("prepare", "3067")
    assert proof["commit"] != before
    assert git("ls-remote", "origin", "refs/heads/main").split()[0] == proof["commit"]
    assert git("--git-dir=" + str(remote), "show", "main:SMART_ACTIVE_EPOCH.json") == "generated"
    assert ".gitattributes" in proof["changed_files"]
    git("--git-dir=" + str(remote), "symbolic-ref", "HEAD", "refs/heads/main")
    checkout = tmp_path / "verified_checkout"
    subprocess.run(
        ["git", "-c", "core.autocrlf=true", "clone", str(remote), str(checkout)],
        check=True, capture_output=True,
    )
    assert (checkout / "SMART_ACTIVE_EPOCH.json").read_bytes() == artifact_bytes
    assert "/SMART_ACTIVE_EPOCH.json -text" in (checkout / ".gitattributes").read_text()


def test_freeze_card_requires_bound_artifact_and_open_pre_draw_window(tmp_path: Path):
    relative = "runtime/learning_epochs/epoch/SMART_3067_PRIMARY_CARD.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    card = {
        "status": "FROZEN", "result_used": False, "target_contest": 3067,
        "product_role": "FINAL_SINGLE_CARD_PRODUCT",
        "freeze_sha256": "a" * 64, "numbers": [1, 2, 3, 7, 8, 9],
        "run_id": "epoch-3067",
        "confidence": {"status": "UNPROVEN_PROSPECTIVE", "level": "LOW", "calibrated": False, "probability_six_hits": None, "guaranteed": False},
    }
    card["sha256"] = hashlib.sha256(
        json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(card), encoding="utf-8")
    proof = {
        "status": "PASS", "result_used": False, "target_contest": 3067,
        "epoch_id": "epoch-3067",
        "freeze_sha256": "a" * 64, "primary_card": card,
        "primary_card_file": relative,
        "primary_card_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "target_schedule": {
            "schema": "SMART_TARGET_SCHEDULE_AUTHORITY_3",
            "target_contest": 3067,
            "scheduled_datetime": "2100-01-01T21:00:00-03:00",
        },
    }
    observation = {"proof": proof}
    result = github_operator._verified_freeze_publication(tmp_path, observation, [relative], "3067")
    assert result["numbers"] == card["numbers"]
    assert result["run_id"] == proof["epoch_id"]
    assert result["confidence"]["level"] == "LOW"
    assert result["confidence"]["calibrated"] is False
    assert result["confidence"]["probability_six_hits"] is None
    original_bytes = path.read_bytes()
    for mutation in (
        {"run_id": None}, {"run_id": "different-epoch"},
        {"confidence": {"status": "PROVEN", "probability_six_hits": 1.0, "guaranteed": True}},
    ):
        altered = {**card, **mutation}
        altered.pop("sha256")
        altered["sha256"] = hashlib.sha256(
            json.dumps(altered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path.write_text(json.dumps(altered), encoding="utf-8")
        altered_proof = {**proof, "primary_card": altered,
                         "primary_card_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        with pytest.raises(ValueError, match="identifier|confidence"):
            github_operator._verified_freeze_publication(tmp_path, {"proof": altered_proof}, [relative], "3067")
    path.write_bytes(original_bytes)

    with pytest.raises(ValueError, match="new persistent artifact"):
        github_operator._verified_freeze_publication(tmp_path, observation, [], "3067")
    expired = {**proof, "target_schedule": {
        **proof["target_schedule"], "scheduled_datetime": "2000-01-01T21:00:00-03:00"
    }}
    with pytest.raises(ValueError, match="freeze window closed"):
        github_operator._verified_freeze_publication(tmp_path, {"proof": expired}, [relative], "3067")
    manual_schedule = {**proof, "target_schedule": {
        "schema": "SMART_TARGET_SCHEDULE_AUTHORITY_3",
        "authority": "OPERATOR_SELECTED_TARGET",
        "operator_selected_target": True,
        "result_used": False,
        "scheduled_datetime": None,
        "target_contest": 3067,
    }}
    with pytest.raises(ValueError, match="verified pre-draw window"):
        github_operator._verified_freeze_publication(
            tmp_path, {"proof": manual_schedule}, [relative], "3067"
        )
    wrong_contest_schedule = {**proof, "target_schedule": {
        **proof["target_schedule"], "target_contest": 3074,
    }}
    with pytest.raises(ValueError, match="schedule target"):
        github_operator._verified_freeze_publication(
            tmp_path, {"proof": wrong_contest_schedule}, [relative], "3067"
        )
    invalid_type_schedule = {**proof, "target_schedule": {
        **proof["target_schedule"], "target_contest": True,
    }}
    with pytest.raises(ValueError, match="schedule target"):
        github_operator._verified_freeze_publication(
            tmp_path, {"proof": invalid_type_schedule}, [relative], "3067"
        )

def test_operator_cli_failure_returns_standardized_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "smart_github_operator.py", "--operation", "prepare", "--target", "3067",
    ])
    def fail(*_):
        raise ValueError("source dataset is missing")
    monkeypatch.setattr(github_operator, "execute", fail)
    assert github_operator.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert set(error) == {"erro", "causa", "acao_sugerida"}
    assert error["erro"] == "OPERACAO_SMART_MEGA_FALHOU"
    assert error["causa"] == "ValueError: source dataset is missing"
    assert error["acao_sugerida"]

def test_operator_git_timeout_is_bounded(monkeypatch, tmp_path):
    def stalled(args, **kwargs):
        assert kwargs["timeout"] == 60
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])
    monkeypatch.setattr(github_operator.subprocess, "run", stalled)
    with pytest.raises(subprocess.TimeoutExpired):
        github_operator._git(tmp_path, "ls-remote", "origin", "refs/heads/main")


def test_native_transaction_journal_survives_git_publication(tmp_path: Path):
    from smart_transaction_journal import (
        JOURNAL_PATH, begin, prepared, committing, committed, read_entries,
    )

    remote, root = tmp_path / "remote.git", tmp_path / "checkout"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(root)],
        check=True, capture_output=True,
    )

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True,
        ).stdout.strip()

    git("config", "user.name", "SMART test")
    git("config", "user.email", "smart-test@example.invalid")
    git("remote", "add", "origin", str(remote))
    for phase in (begin, prepared, committing, committed):
        phase(root, "PREPARE:3067:test", "PREPARE", target_contest=3067)

    relative = JOURNAL_PATH.as_posix()
    original = (root / JOURNAL_PATH).read_bytes()
    entries = read_entries(root)
    assert [entry["phase"] for entry in entries] == [
        "BEGIN", "PREPARED", "COMMITTING", "COMMITTED",
    ]
    assert allowed_artifact(relative)
    for rejected in (
        "runtime/transactions/OTHER.jsonl",
        "runtime/other/SMART_TRANSACTION_JOURNAL.jsonl",
        "artifacts/SMART_TRANSACTION_JOURNAL.jsonl",
        "../runtime/transactions/SMART_TRANSACTION_JOURNAL.jsonl",
    ):
        assert not allowed_artifact(rejected)

    assert github_operator._pin_artifact_bytes(root, [relative])
    git("add", "--", ".gitattributes", relative)
    github_operator._verify_staged_bytes(root, [relative])
    git("commit", "-m", "persist native transaction journal")
    git("push", "origin", "main")
    clone = tmp_path / "verified"
    subprocess.run(
        ["git", "-c", "core.autocrlf=true", "clone", "--branch", "main", str(remote), str(clone)],
        check=True, capture_output=True,
    )
    assert (clone / JOURNAL_PATH).read_bytes() == original
    assert read_entries(clone) == entries


def _prospective_cycle_fixture(tmp_path: Path, monkeypatch):
    """Model reader is isolated; publication still verifies card bytes and cutoff."""
    from smart_frozen_card_reader import sha256_json
    import smart_frozen_card_reader

    target = 3073
    freeze_file = tmp_path / "runtime/learning_epochs/e3073/SMART_FREEZE_3073.json"
    freeze_file.parent.mkdir(parents=True, exist_ok=True)
    freeze_file.write_text("{}", encoding="utf-8")
    (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text(json.dumps({
        "freeze_authority": {"file": str(freeze_file.relative_to(tmp_path)).replace("\\", "/")}
    }), encoding="utf-8")
    relative = "runtime/learning_epochs/e3073/SMART_3073_PRIMARY_CARD.json"
    path = tmp_path / relative
    card = {
        "status": "FROZEN", "result_used": False, "target_contest": target,
        "product_role": "FINAL_SINGLE_CARD_PRODUCT", "freeze_sha256": "a" * 64,
        "numbers": [2, 11, 20, 34, 43, 60], "run_id": "epoch-3073",
        "confidence": {"status": "UNPROVEN_PROSPECTIVE", "level": "LOW",
                       "calibrated": False, "probability_six_hits": None,
                       "guaranteed": False},
    }
    card["sha256"] = sha256_json(card)
    path.write_text(json.dumps(card), encoding="utf-8")
    card_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    proof = {
        "status": "PASS", "result_used": False, "target_contest": target,
        "epoch_id": "epoch-3073", "freeze_sha256": "a" * 64,
        "primary_card": card, "primary_card_file": relative,
        "primary_card_sha256": card_sha,
        "target_schedule": {
            "schema": "SMART_TARGET_SCHEDULE_AUTHORITY_3",
            "target_contest": target, "scheduled_datetime": "2100-01-01T21:00:00-03:00"
        },
    }
    (freeze_file.parent / "FULL_PROCESS_PROOF.json").write_text(
        json.dumps(proof), encoding="utf-8"
    )
    verified = {
        "schema": "SMART_FROZEN_MODEL_CARD_READ_1",
        "status": "FROZEN_MODEL_CARD_VERIFIED", "target_contest": target,
        "numbers": card["numbers"], "primary_card_sha256": card_sha,
        "readonly": True, "result_used_in_generation": False,
        "certified_predictive_advantage": False,
        "past_draw_can_be_reused_as_future_prediction": False,
    }
    verified["sha256"] = sha256_json(verified)
    monkeypatch.setattr(smart_frozen_card_reader, "read_frozen_card",
                        lambda root, selected: verified if selected == target else None)
    return relative, verified, proof


def test_native_github_dispatch_exposes_existing_cycle_and_postresult_actions():
    assert command_args("complete-result", "3071")[-4:] == [
        "smart_operator.py", "complete-result", "--target", "3071"
    ]
    assert command_args("recover-cycle", "3073", "SMART_PUBLIC_RESULT_BATCH_3072.json")[-6:] == [
        "smart_operator.py", "recover-cycle", "--target", "3073",
        "--payload-file", "SMART_PUBLIC_RESULT_BATCH_3072.json"
    ]
    assert command_args("show-card", "3071")[-2:] == ["--target", "3071"]
    with pytest.raises(ValueError, match="target"):
        command_args("recover-cycle", "")
    with pytest.raises(ValueError, match="does not accept"):
        command_args("complete-result", "3071", "SMART_RESULT.json")


def test_native_cycle_publishes_only_new_evidence_bound_prospective_card(tmp_path, monkeypatch):
    relative, verified, proof = _prospective_cycle_fixture(tmp_path, monkeypatch)
    observation = {
        "status": "MODEL_CARD_GENERATED", "retroactive_generation": False,
        "scientific_6of6_proven": False, "target_contest": 3073,
        "card": verified,
    }
    frozen, recovered = github_operator._verified_cycle_card_publication(
        tmp_path, observation, [relative], "3073"
    )
    assert frozen["sha256"] == verified["primary_card_sha256"]
    assert frozen["numbers"] == verified["numbers"]
    assert recovered == proof
    with pytest.raises(ValueError, match="new persistent artifact"):
        github_operator._verified_cycle_card_publication(tmp_path, observation, [], "3073")


def test_native_cycle_rejects_replay_invented_card_or_false_certification(tmp_path, monkeypatch):
    relative, verified, _ = _prospective_cycle_fixture(tmp_path, monkeypatch)
    observation = {
        "status": "MODEL_CARD_GENERATED", "retroactive_generation": False,
        "scientific_6of6_proven": False, "card": verified,
    }
    tampered = dict(observation, card={**verified, "numbers": [1, 2, 3, 4, 5, 6]})
    with pytest.raises(ValueError, match="immutable evidence"):
        github_operator._verified_cycle_card_publication(tmp_path, tampered, [relative], "3073")
    for altered in (
        dict(observation, status="MODEL_CARD_ALREADY_FROZEN"),
        dict(observation, retroactive_generation=True),
        dict(observation, scientific_6of6_proven=True),
    ):
        with pytest.raises(ValueError, match="new prospective"):
            github_operator._verified_cycle_card_publication(tmp_path, altered, [relative], "3073")


def test_native_cycle_rejects_wrong_target_and_missing_full_proof(tmp_path, monkeypatch):
    relative, verified, _ = _prospective_cycle_fixture(tmp_path, monkeypatch)
    observation = {"status": "MODEL_CARD_GENERATED", "retroactive_generation": False,
                   "card": verified}
    with pytest.raises(ValueError, match="new prospective|immutable evidence"):
        github_operator._verified_cycle_card_publication(tmp_path, observation, [relative], "3074")
    (tmp_path / "runtime/learning_epochs/e3073/FULL_PROCESS_PROOF.json").unlink()
    with pytest.raises(ValueError, match="proof is absent"):
        github_operator._verified_cycle_card_publication(tmp_path, observation, [relative], "3073")



def test_pre_draw_guard_requires_exact_contest_and_strict_verified_status(monkeypatch):
    import smart_target_schedule

    schedule = {
        "schema": "SMART_TARGET_SCHEDULE_AUTHORITY_3",
        "target_contest": 3073,
        "scheduled_datetime": "2100-01-01T21:00:00-03:00",
    }
    checked = github_operator._require_verified_pre_draw_window(schedule, 3073)
    assert checked["status"] == "PASS"
    with pytest.raises(ValueError, match="schedule target"):
        github_operator._require_verified_pre_draw_window(schedule, 3074)
    with pytest.raises(ValueError, match="schedule target"):
        github_operator._require_verified_pre_draw_window(
            {**schedule, "target_contest": True}, 3073
        )

    monkeypatch.setattr(
        smart_target_schedule, "assert_pre_draw_window",
        lambda _: {"status": "OPERATOR_UNVERIFIED_DRAW_TIME",
                   "target_contest": 3073, "before_scheduled_draw": False},
    )
    with pytest.raises(ValueError, match="verified pre-draw window"):
        github_operator._require_verified_pre_draw_window(schedule, 3073)

    monkeypatch.setattr(
        smart_target_schedule, "assert_pre_draw_window",
        lambda _: {"status": "PASS", "target_contest": 3074,
                   "before_scheduled_draw": True},
    )
    with pytest.raises(ValueError, match="same target"):
        github_operator._require_verified_pre_draw_window(schedule, 3073)

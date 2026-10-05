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

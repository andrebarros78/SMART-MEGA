from pathlib import Path
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


def test_successful_operation_publishes_its_state_to_git(tmp_path: Path, monkeypatch):
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
            "Path('SMART_ACTIVE_EPOCH.json').write_text('generated'); "
            "print(json.dumps({'status':'PREPARED'}))",
        ],
    )
    monkeypatch.setenv("GITHUB_REPOSITORY", "andrebarros78/SMART-MEGA")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    proof = github_operator.execute("prepare", "3067")
    assert proof["commit"] != before
    assert git("ls-remote", "origin", "refs/heads/main").split()[0] == proof["commit"]
    assert git("--git-dir=" + str(remote), "show", "main:SMART_ACTIVE_EPOCH.json") == "generated"

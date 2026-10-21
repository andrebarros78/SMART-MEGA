"""Fail-closed GitHub-native execution policy; Python stdlib only.

Checks live AI instructions and GitHub workflows, not immutable historical proofs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

POLICY_ID = "SMART_GITHUB_NATIVE_ONLY_20261021"
CANONICAL_REPOSITORY = "andrebarros78/SMART-MEGA"
CANONICAL_BRANCH = "main"
ACTIVE_INSTRUCTIONS = (
    "AGENTS.md",
    "AI_START_HERE.md",
    "README.md",
    "SMART_AI_EXECUTION_ENTRYPOINT.md",
    "SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md",
    "SMART_ARCHIVE_RUNTIME_BOUNDARY.md",
)
REQUIRED_WORKFLOWS = (
    ".github/workflows/ci.yml",
    ".github/workflows/operator.yml",
    ".github/workflows/repository-integrity.yml",
)
LEGACY_PERMISSIONS = (
    "GitHub Actions ou executor federado autorizado",
    "O PC Escola e a rede federada também podem executar",
    "a rede federada e o PC Escola podem executar",
    "rede federada e o PC Escola podem executar",
)
HOSTED_RUNNER = re.compile(r"^(?:ubuntu|windows|macos)-(?:latest|\d{2}\.\d{2})$")
EXTERNAL_DISPATCH = re.compile(r"\b(?:ssh|scp|rsync|tailscale|wireguard|lmcp|s-wmcp|wmcp)\b", re.I)


class PolicyViolation(RuntimeError):
    pass


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise PolicyViolation(f"required policy surface missing/unsafe: {relative}")
    return path.read_text(encoding="utf-8-sig")


def verify(root: str | Path) -> dict[str, object]:
    root = Path(root).resolve()
    for relative in ACTIVE_INSTRUCTIONS:
        content = _read(root, relative)
        for marker in (POLICY_ID, CANONICAL_REPOSITORY, CANONICAL_BRANCH):
            if marker not in content:
                raise PolicyViolation(f"{relative}: missing canonical marker {marker}")
        for legacy in LEGACY_PERMISSIONS:
            if legacy.casefold() in content.casefold():
                raise PolicyViolation(f"{relative}: legacy external execution permission still active")

    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.is_symlink() or not workflow_dir.is_dir():
        raise PolicyViolation("GitHub workflow directory missing/unsafe")
    workflows = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))
    observed = {str(path.relative_to(root)) for path in workflows}
    if not set(REQUIRED_WORKFLOWS).issubset(observed):
        raise PolicyViolation("required GitHub-native workflow removed")
    if not workflows:
        raise PolicyViolation("GitHub-native workflows absent")
    checks = 0
    for path in workflows:
        relative = str(path.relative_to(root))
        content = _read(root, relative)
        runners = re.findall(r"(?m)^\s*runs-on:\s*(\S.*?)\s*$", content)
        if not runners or any(not HOSTED_RUNNER.fullmatch(run) for run in runners):
            raise PolicyViolation(f"{relative}: non-GitHub-hosted runner or no runner")
        if EXTERNAL_DISPATCH.search(content):
            raise PolicyViolation(f"{relative}: legacy external dispatch mechanism")
        partitions = re.split(r"(?m)^\s*-\s*uses:\s*actions/checkout@[^\n]*$", content)
        checkout_count = len(partitions) - 1
        if not checkout_count:
            raise PolicyViolation(f"{relative}: checkout missing")
        if content.count("run: python smart_github_native_policy.py") != checkout_count:
            raise PolicyViolation(f"{relative}: every job must run the native gate")
        for partition in partitions[1:]:
            guard = partition.find("run: python smart_github_native_policy.py")
            if guard < 0:
                raise PolicyViolation(f"{relative}: job lacks native policy gate")
            forbidden_before = [i for needle in ("pip install", "smart_github_operator.py", "python -m pytest")
                                if (i := partition.find(needle)) >= 0]
            if forbidden_before and min(forbidden_before) < guard:
                raise PolicyViolation(f"{relative}: execution starts before native policy gate")
        checks += checkout_count

    operator = _read(root, "smart_github_operator.py")
    for marker in ("GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_EVENT_NAME", "refs/heads/main"):
        if marker not in operator:
            raise PolicyViolation(f"native operator lost its GitHub-only authority: {marker}")
    return {"status": "PASS", "policy_id": POLICY_ID, "workflows": len(workflows),
            "hosted_jobs": checks, "external_execution_allowed": False}


def main() -> int:
    try:
        result = verify(Path(__file__).resolve().parent)
    except (PolicyViolation, OSError, UnicodeError) as exc:
        print(f"GITHUB_NATIVE_POLICY=FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"GITHUB_NATIVE_POLICY=PASS {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

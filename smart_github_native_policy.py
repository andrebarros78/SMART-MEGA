"""Canonical GitHub + explicitly authorized external executor. GitHub Actions banned.

This gate uses only Python stdlib and never executes project workloads.
"""
from __future__ import annotations

import sys
from pathlib import Path

POLICY_ID = "SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021"
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
FORBIDDEN_OLD_RULES = (
    "Somente GitHub Actions em runners hospedados",
    "Only GitHub Actions on GitHub-hosted runners are authorized",
    "GitHub Actions ou executor federado autorizado",
)


class PolicyViolation(RuntimeError):
    pass


def verify(root: str | Path) -> dict[str, object]:
    root = Path(root).resolve()
    for rel in ACTIVE_INSTRUCTIONS:
        path = root / rel
        if not path.is_file() or path.is_symlink():
            raise PolicyViolation(f"missing or unsafe active policy document: {rel}")
        content = path.read_text(encoding="utf-8-sig")
        for marker in (POLICY_ID, CANONICAL_REPOSITORY, CANONICAL_BRANCH):
            if marker not in content:
                raise PolicyViolation(f"{rel}: missing {marker}")
        for old in FORBIDDEN_OLD_RULES:
            if old.casefold() in content.casefold():
                raise PolicyViolation(f"{rel}: obsolete Actions-only permission")
    workflows = root / ".github" / "workflows"
    if workflows.is_symlink():
        raise PolicyViolation("symlinked Actions directory forbidden")
    active = sorted(
        str(p.relative_to(root)) for p in workflows.rglob("*")
        if p.suffix.lower() in {".yml", ".yaml"}
    ) if workflows.is_dir() else []
    if active:
        raise PolicyViolation(f"GitHub Actions is prohibited: {active}")
    return {
        "status": "PASS",
        "policy_id": POLICY_ID,
        "canonical_repository": CANONICAL_REPOSITORY,
        "canonical_branch": CANONICAL_BRANCH,
        "github_actions_authorized": False,
        "external_executors_authorized": True,
        "external_executor_permanent_dependency": False,
    }


def main() -> int:
    try:
        result = verify(Path(__file__).resolve().parent)
    except (PolicyViolation, OSError, UnicodeError) as exc:
        print(f"EXECUTION_POLICY=FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"EXECUTION_POLICY=PASS {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

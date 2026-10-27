"""Canonical GitHub + explicitly authorized external executor. GitHub Actions banned.

This gate uses only Python stdlib and never executes project workloads.
"""
from __future__ import annotations

import re
import sys
import unicodedata
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
    "Somente GitHub Actions com runners hospedados pelo GitHub podem executar",
    "A execu\u00e7\u00e3o do produto ocorre exclusivamente em runners hospedados pelo GitHub",
    "PC Escola \u00e9 obrigat\u00f3rio para gerar cart\u00f5es",
    "PC Casa \u00e9 obrigat\u00f3rio para gerar cart\u00f5es",
)


class PolicyViolation(RuntimeError):
    pass


def _normalized_policy(content: str) -> str:
    text = unicodedata.normalize("NFKD", content).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[\x60*_]", "", text)
    return " ".join(text.split())


def _check_contract(content: str, rel: str) -> None:
    text = _normalized_policy(content)
    if not re.search(r"\bgithub actions\b.{0,60}\b(?:proibid[oa]s?|forbidden|banned|disabled|vedad[oa]s?)\b", text):
        raise PolicyViolation(f"{rel}: missing explicit GitHub Actions prohibition")
    if not re.search(r"\b(?:executores? extern[oa]s?|external (?:temporary )?executors?)\b.{0,85}\b(?:autorizad[oa]s?|permitid[oa]s?|authorized|allowed|approved)\b", text):
        raise PolicyViolation(f"{rel}: missing explicit external executor authorization")
    forbidden = (
        r"\b(?:somente|apenas|exclusivamente|only)\s+github actions\b",
        r"\bgithub actions\b.{0,60}\b(?:obrigatori[oa]s?|exclusiv[oa]s?|necessari[oa]s?|required|must|are allowed)\b",
        r"\bpc (?:escola|casa)\s+(?:e|sera|deve ser)\s+(?:obrigatori[oa]s?|indispensavel|necessari[oa]s?)\b",
        r"\b(?:exige|requer|depende do|depende de)\s+(?:o|do|da)?\s*pc (?:escola|casa)\b",
    )
    if any(re.search(pattern, text) for pattern in forbidden):
        raise PolicyViolation(f"{rel}: obsolete permanent executor or Actions-only requirement")



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
        _check_contract(content, rel)
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

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if raw.count(b"\r\n") > max(0, raw.count(b"\n") - raw.count(b"\r\n")) else "\n"
    return raw.decode("utf-8"), newline


def _write(path: Path, text: str, newline: str) -> None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = normalized if newline == "\n" else normalized.replace("\n", "\r\n")
    path.write_bytes(raw.encode("utf-8"))


def _ensure_import(path: str, anchor: str, import_line: str) -> None:
    p = ROOT / path
    text, newline = _read(p)
    if import_line in text:
        return
    if anchor not in text:
        raise RuntimeError(f"import anchor not found in {path}: {anchor!r}")
    text = text.replace(anchor, anchor + import_line, 1)
    _write(p, text, newline)


def _replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    p = ROOT / path
    text, newline = _read(p)
    if new in text and old not in text:
        return
    observed = text.count(old)
    if observed != count:
        raise RuntimeError(f"replacement precondition failed in {path}: expected {count}, observed {observed}: {old!r}")
    text = text.replace(old, new, count)
    _write(p, text, newline)


def _patch_champion() -> None:
    p = ROOT / "smart_champion_challenger.py"
    text, newline = _read(p)
    import_line = "from smart_source_identity import sha256_source_file\n"
    anchor = "from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule\n"
    if import_line not in text:
        if anchor not in text:
            raise RuntimeError("champion source identity import anchor missing")
        text = text.replace(anchor, anchor + import_line, 1)
    pattern = re.compile(r"\bsha256\(Path\((['\"])([^'\"]+\.py)\1\)\)")
    text, changed = pattern.subn(lambda m: f"sha256_source_file(Path({m.group(1)}{m.group(2)}{m.group(1)}))", text)
    if changed == 0 and "sha256_source_file(Path('smart_v2_engine.py'))" not in text:
        raise RuntimeError("champion component source hash migration found no targets")
    _write(p, text, newline)


def _write_permanent_files() -> None:
    (ROOT / ".gitattributes").write_text(
        "# SMART-MEGA canonical checkout: cryptographically bound files are never EOL-rewritten by Git.\n"
        "*.py -text\n"
        "*.pyi -text\n"
        "*.json -text\n"
        "*.xml -text\n"
        "*.xlsx -text\n"
        "*.xls -text\n"
        "*.csv -text\n"
        "*.md -text\n"
        "*.txt -text\n"
        "*.ini -text\n"
        "*.cmd -text\n"
        ".github/workflows/*.yml text eol=lf\n"
        ".github/workflows/*.yaml text eol=lf\n",
        encoding="utf-8",
        newline="\n",
    )
    (ROOT / "smart_source_identity.py").write_text(
        "from __future__ import annotations\n\n"
        "import hashlib\n"
        "from pathlib import Path\n"
        "from typing import Iterable\n\n"
        "SCHEMA = 'SMART_SOURCE_IDENTITY_1'\n\n\n"
        "def normalize_source_bytes(raw: bytes) -> bytes:\n"
        "    if not isinstance(raw, bytes):\n"
        "        raise TypeError('source identity requires bytes')\n"
        "    return raw.replace(b'\\r\\n', b'\\n').replace(b'\\r', b'\\n')\n\n\n"
        "def sha256_source_bytes(raw: bytes) -> str:\n"
        "    return hashlib.sha256(normalize_source_bytes(raw)).hexdigest()\n\n\n"
        "def sha256_source_file(path: str | Path) -> str:\n"
        "    return sha256_source_bytes(Path(path).read_bytes())\n\n\n"
        "def source_hashes(root: str | Path, filenames: Iterable[str]) -> dict[str, str]:\n"
        "    base = Path(root)\n"
        "    out: dict[str, str] = {}\n"
        "    for name in filenames:\n"
        "        if name in out:\n"
        "            raise ValueError(f'duplicate source identity path: {name}')\n"
        "        path = base / name\n"
        "        if not path.is_file():\n"
        "            raise FileNotFoundError(path)\n"
        "        out[name] = sha256_source_file(path)\n"
        "    return out\n\n\n"
        "__all__ = ['SCHEMA', 'normalize_source_bytes', 'sha256_source_bytes', 'sha256_source_file', 'source_hashes']\n",
        encoding="utf-8",
        newline="\n",
    )
    (ROOT / "test_smart_source_identity.py").write_text(
        "from pathlib import Path\n\n"
        "from smart_source_identity import normalize_source_bytes, sha256_source_bytes, sha256_source_file, source_hashes\n\n\n"
        "def test_source_identity_is_lf_crlf_invariant(tmp_path: Path):\n"
        "    lf = tmp_path / 'lf.py'\n"
        "    crlf = tmp_path / 'crlf.py'\n"
        "    lf.write_bytes(b\"x = 1\\ny = 2\\n\")\n"
        "    crlf.write_bytes(b\"x = 1\\r\\ny = 2\\r\\n\")\n"
        "    assert sha256_source_file(lf) == sha256_source_file(crlf)\n\n\n"
        "def test_source_identity_normalizes_legacy_bare_cr():\n"
        "    assert sha256_source_bytes(b'a\\rb\\r') == sha256_source_bytes(b'a\\nb\\n')\n"
        "    assert normalize_source_bytes(b'a\\r\\nb\\r') == b'a\\nb\\n'\n\n\n"
        "def test_source_identity_preserves_meaningful_non_eol_bytes():\n"
        "    assert sha256_source_bytes(b'x = 1\\n') != sha256_source_bytes(b'x = 2\\n')\n\n\n"
        "def test_source_hashes_rejects_duplicate_paths(tmp_path: Path):\n"
        "    (tmp_path / 'a.py').write_text('x=1\\n', encoding='utf-8')\n"
        "    try:\n"
        "        source_hashes(tmp_path, ['a.py', 'a.py'])\n"
        "    except ValueError as exc:\n"
        "        assert 'duplicate source identity path' in str(exc)\n"
        "    else:\n"
        "        raise AssertionError('duplicate source identity paths must fail closed')\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    _write_permanent_files()

    _ensure_import("smart_critical_code_manifest.py", "from typing import Any\n", "\nfrom smart_source_identity import sha256_source_file\n")
    _replace("smart_critical_code_manifest.py", "files={p.name:sha256_file(p) for p in critical_code_files(root)}", "files={p.name:sha256_source_file(p) for p in critical_code_files(root)}")

    _ensure_import("smart_global_integrity.py", "from typing import Any, Iterable\n", "\nfrom smart_source_identity import sha256_source_file\n")
    _replace("smart_global_integrity.py", "out[name] = sha256_file(p)", "out[name] = sha256_source_file(p)")

    _ensure_import("smart_product_certification.py", "from typing import Any\n", "\nfrom smart_source_identity import sha256_source_file\n")
    _replace("smart_product_certification.py", "rows = [{\"path\": p.name, \"sha256\": sha256_file(p)} for p in _code_files(root)]", "rows = [{\"path\": p.name, \"sha256\": sha256_source_file(p)} for p in _code_files(root)]")

    _ensure_import("smart_regression_runner.py", "from typing import Any, Sequence\n", "\nfrom smart_source_identity import sha256_source_file\n")
    _replace("smart_regression_runner.py", "rows = [{\"path\": path.name, \"sha256\": evidence.sha256_file(path)} for path in _code_files(root)]", "rows = [{\"path\": path.name, \"sha256\": sha256_source_file(path)} for path in _code_files(root)]")

    _ensure_import("smart_learning_activation_authority.py", "from smart_learning_activation_gate import ActivationDecision\n", "from smart_source_identity import sha256_source_file\n")
    _replace("smart_learning_activation_authority.py", "component_hashes[key] = _sha256_file(p)", "component_hashes[key] = sha256_source_file(p)")
    _replace("smart_learning_activation_authority.py", "component_hashes.get(key) != _sha256_file(p)", "component_hashes.get(key) != sha256_source_file(p)")

    _ensure_import("smart_continuous_red_team.py", "from smart_signal_weights import dynamic_weights\n", "from smart_source_identity import sha256_source_file\n")
    _replace("smart_continuous_red_team.py", "out[name] = sha256_file(p)", "out[name] = sha256_source_file(p)")

    _patch_champion()

    _ensure_import("smart_independent_audit.py", "from smart_material_deficiency_registry import load_registry as load_material_deficiency_registry\n", "from smart_source_identity import sha256_source_file\n")
    _replace("smart_independent_audit.py", "sha256_file(project_source) != sha256_file(runtime_source)", "sha256_source_file(project_source) != sha256_source_file(runtime_source)")
    _replace("smart_independent_audit.py", "sha256_file(project_oracle_source) != sha256_file(runtime_oracle_source)", "sha256_source_file(project_oracle_source) != sha256_source_file(runtime_oracle_source)")
    _replace("smart_independent_audit.py", "'source_sha256': sha256_file(source)", "'source_sha256': sha256_source_file(source)")
    _replace("smart_independent_audit.py", "'independent_oracle_sha256': sha256_file(oracle_source)", "'independent_oracle_sha256': sha256_source_file(oracle_source)")
    _replace("smart_independent_audit.py", "current_source_sha = sha256_file(source)", "current_source_sha = sha256_source_file(source)")

    _ensure_import("smart_agent_runtime.py", "from smart_agent_skill_orchestration import AGENTS, LANES, build_orchestration, resolve_runtime_phase\n", "from smart_source_identity import sha256_source_file\n")
    _replace(
        "smart_agent_runtime.py",
        "records.append({\"path\": relative.replace(\"\\\\\", \"/\"), \"sha256\": sha256_file(path)})",
        "records.append({\"path\": relative.replace(\"\\\\\", \"/\"), \"sha256\": sha256_source_file(path) if path.suffix.lower() == '.py' else sha256_file(path)})",
    )

    required = {
        "smart_critical_code_manifest.py": "sha256_source_file(p)",
        "smart_global_integrity.py": "out[name] = sha256_source_file(p)",
        "smart_product_certification.py": "sha256_source_file(p)",
        "smart_regression_runner.py": "sha256_source_file(path)",
        "smart_learning_activation_authority.py": "component_hashes[key] = sha256_source_file(p)",
        "smart_continuous_red_team.py": "out[name] = sha256_source_file(p)",
        "smart_champion_challenger.py": "sha256_source_file(Path('smart_v2_engine.py'))",
        "smart_independent_audit.py": "current_source_sha = sha256_source_file(source)",
        "smart_agent_runtime.py": "sha256_source_file(path) if path.suffix.lower() == '.py'",
    }
    for name, marker in required.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        if marker not in text:
            raise RuntimeError(f"source identity marker missing after migration: {name}: {marker}")

    print("SOURCE_IDENTITY_MIGRATION=PASS")


if __name__ == "__main__":
    main()

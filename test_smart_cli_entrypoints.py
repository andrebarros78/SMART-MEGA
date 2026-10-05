"""Import and parse every root CLI without changing operational state."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


def _cli_files():
    paths = []
    for path in sorted(ROOT.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Attribute) and node.func.attr == "ArgumentParser"
                or isinstance(node.func, ast.Name) and node.func.id == "ArgumentParser"
            )
            for node in ast.walk(tree)
        ):
            paths.append(path)
    return paths


@pytest.mark.parametrize("path", _cli_files(), ids=lambda path: path.name)
def test_root_cli_help_imports_and_exits_cleanly(path, record_property):
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(path), "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    evidence = {"command": path.name, "input": "--help",
                "returncode": result.returncode, "elapsed_seconds": round(time.monotonic() - started, 3),
                "stdout": result.stdout[:400], "stderr": result.stderr[:2000]}
    record_property("cli_smoke", json.dumps(evidence, ensure_ascii=False))
    assert result.returncode == 0, json.dumps(evidence, ensure_ascii=False)
    assert "usage:" in result.stdout.lower(), json.dumps(evidence, ensure_ascii=False)

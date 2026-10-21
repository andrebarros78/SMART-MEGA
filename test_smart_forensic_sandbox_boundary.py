"""Exercise production guards in fresh interpreters, outside pytest adapters."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PROBES = {
    "identity": "from smart_canonical_identity import require_canonical_identity; require_canonical_identity(root)",
    "lifecycle_load": "from smart_operational_lifecycle import load_lifecycle; load_lifecycle(root)",
    "lifecycle_state": "from smart_operational_lifecycle import assert_state; assert_state(root, 'FROZEN', target_contest=9999)",
    "persisted_synthetic_lifecycle": """import json
import smart_operational_lifecycle as lifecycle
doc = lifecycle._synthetic_lifecycle('IDLE')
(root / lifecycle.STATE_FILE).write_text(json.dumps(doc), encoding='utf-8')
lifecycle.assert_state(root, 'FROZEN', target_contest=9999)
""",
    "reconciliation": "from smart_startup_reconciler import assert_reconciled; assert_reconciled(root, 9999)",
    "lock": "from smart_operation_lock import update_current_process_lock; update_current_process_lock(root, target_contest=9999)",
    "epoch_cas": """from smart_learning_epoch_reset import write_active_epoch
path = root / 'SMART_ACTIVE_EPOCH.json'
doc = {'schema': 'SMART_ACTIVE_LEARNING_EPOCH_2', 'status': 'RESET_READY',
       'target_contest': 9999, 'cutoff_contest': 9998, 'result_used': False}
write_active_epoch(path, doc)
write_active_epoch(path, doc)
""",
}


@pytest.mark.parametrize("probe", PROBES)
@pytest.mark.parametrize("forged_pytest_environment", [False, True])
def test_path_and_environment_never_authorize_production_guards(
    tmp_path: Path, probe: str, forged_pytest_environment: bool,
) -> None:
    root = tmp_path / "pytest-production-copy"
    root.mkdir()
    repository = Path(__file__).resolve().parent
    script = """import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
root = pathlib.Path(sys.argv[2])
try:
    exec(sys.argv[3])
except (ValueError, RuntimeError, FileNotFoundError, PermissionError) as exc:
    print(json.dumps({'denied': True, 'exception': type(exc).__name__}))
else:
    print(json.dumps({'denied': False}))
"""
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    if forged_pytest_environment:
        env["PYTEST_CURRENT_TEST"] = "forged_test.py::test_authorized (call)"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(repository), str(root), PROBES[probe]],
        env=env, text=True, capture_output=True, check=True, timeout=90,
    )
    assert json.loads(result.stdout)["denied"] is True, (probe, result.stdout)


def test_local_copies_do_not_override_the_current_git_checkout(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parent
    copy = str(tmp_path / "SMART-MEGA-V6-isolated-copy")
    script = """import json, sys
sys.path.insert(0, sys.argv[1])
import smart_canonical_identity as identity
identity.discover_competing_roots = lambda *args: (sys.argv[2],)
print(json.dumps(identity.require_canonical_identity(sys.argv[1])))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(repository), copy],
        text=True, capture_output=True, check=True, timeout=60,
    )
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["git_identity"]["repository_root"] == str(repository)
    assert receipt["observed_local_copies"] == [copy]
    assert receipt["competing_roots"] == []

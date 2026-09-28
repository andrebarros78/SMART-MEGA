from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from smart_operational_lifecycle import SCHEMA, _sha_json, load_lifecycle, transition


def _write_lifecycle(root: Path, *, state: str, target: int, completed: int | None = None) -> dict:
    doc = {
        "schema": SCHEMA,
        "state": state,
        "revision": 1,
        "project": "SMART-MEGA",
        "effective_version": "6.3.2",
        "target_contest": target,
        "completed_contest": completed,
        "previous_state": "ADJUDICATED",
        "transition": "ADJUDICATED_TO_REVIEWED",
        "transition_actor": "test",
        "transition_utc": datetime.now(timezone.utc).isoformat(),
        "previous_lifecycle_sha256": "0" * 64,
        "authority": "SINGLE_OPERATIONAL_LIFECYCLE",
        "legacy_documents_are_evidence_not_authority": True,
        "migration_mode": "TEST",
        "evidence": {},
    }
    doc["sha256"] = _sha_json(doc)
    (root / "SMART_OPERATIONAL_LIFECYCLE.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def test_reviewed_to_hold_validates_previous_target_and_writes_next_target(tmp_path: Path) -> None:
    _write_lifecycle(tmp_path, state="REVIEWED", target=3061, completed=3060)

    result = transition(
        tmp_path,
        "REVIEWED",
        "HOLD",
        target_contest=3062,
        completed_contest=3061,
        actor="test_reviewed_to_hold",
        evidence={"hold": {"file": "SMART_NEXT_CYCLE_HOLD.json"}},
    )

    assert result["state"] == "HOLD"
    assert result["target_contest"] == 3062
    assert result["completed_contest"] == 3061
    assert result["transition"] == "REVIEWED_TO_HOLD"
    assert load_lifecycle(tmp_path)["sha256"] == result["sha256"]

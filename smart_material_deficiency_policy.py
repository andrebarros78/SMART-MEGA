from __future__ import annotations
from typing import Any, Iterable

SUPERVISORY_FRESHNESS_DEFICIENCY_ID = "D037_AGENT_ECOSYSTEM_MATERIAL_SUPERVISOR_FAIL"

def material_blockers(entries: Iterable[dict[str, Any]], *, allow_supervisory_freshness_self_resolution: bool=False) -> list[dict[str, Any]]:
    rows=[dict(e) for e in entries if isinstance(e,dict) and e.get("status") in {"OPEN","REOPENED"}]
    if allow_supervisory_freshness_self_resolution:
        rows=[e for e in rows if e.get("id") != SUPERVISORY_FRESHNESS_DEFICIENCY_ID]
    return rows

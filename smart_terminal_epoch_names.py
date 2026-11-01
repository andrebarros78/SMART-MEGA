"""Pure active-epoch filename and configuration derivation.

No mutation of the epoch document, global engine settings or frozen evidence.
The terminal engine retains its lock, authority check and restoration boundary.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def epoch_runtime_names(active: dict[str, Any], selected: int) -> dict[str, Any]:
    state_paths = active.get("state_paths")
    if not isinstance(state_paths, dict) or not state_paths.get("ledger"):
        raise ValueError("active epoch ledger path missing")
    epoch_rel = Path(str(state_paths["ledger"])).parent
    return {
        "SCHEMA": "SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1",
        "TARGET": selected,
        "CUTOFF": selected - 1,
        "PRE_RESULT_DATA": str(active.get("data_file", "")),
        "RESULT_DATA": (epoch_rel / f"Mega-Sena_through_{selected}.xlsx").as_posix(),
        "INGEST_PROOF": (epoch_rel / f"SMART_OFFICIAL_RESULT_INGEST_{selected}.json").as_posix(),
        "PRIMARY_PAYLOAD": (epoch_rel / f"SMART_{selected}_OFFICIAL_PRIMARY_PAYLOAD.json").as_posix(),
        "CONSENSUS_FILE": (epoch_rel / f"SMART_{selected}_OFFICIAL_EVIDENCE_CURRENT.json").as_posix(),
        "LEARNED_STATE": f"SMART_SIGNAL_STATE_{selected}_LEARNED.json",
        "RESULT_STORE_PROOF": f"SMART_CANONICAL_HISTORY_ADVANCE_{selected}.json",
        "TERMINAL_PROOF": (epoch_rel / f"SMART_TERMINAL_6OF6_PROOF_{selected}.json").as_posix(),
        "STATUS_FILE": (epoch_rel / f"SMART_TERMINAL_EXECUTOR_STATUS_{selected}.json").as_posix(),
        "INDEPENDENT_AUDIT_FILE": (epoch_rel / f"SMART_P14_INDEPENDENT_AUDIT_{selected}.json").as_posix(),
    }
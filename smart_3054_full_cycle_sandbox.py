from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import adjudicate_signal_challenger as adjudicator
import smart_3054_adjudication_preflight as preflight
import smart_official_result_ingest as official_ingest
import smart_sequential_prospective_proof as sequential
from smart_signal_agent import SmartSignalAgent
from smart_v2_engine import load_draws

SCHEMA = "SMART_3054_FULL_CYCLE_SANDBOX_V1"
TARGET = 3054
EXPECTED_FREEZE_SHA256 = preflight.EXPECTED_FREEZE_SHA256
CANONICAL_PROTECTED = (
    "SMART_SIGNAL_LEDGER.json",
    "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json",
    "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json",
    "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json",
    "Mega-Sena.xlsx",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _hashes(root: Path) -> dict[str, str]:
    return {name: sha256_file(root / name) for name in CANONICAL_PROTECTED}


def _agent_from_prestate(prestate: dict[str, Any]) -> SmartSignalAgent:
    return SmartSignalAgent(
        start=int(prestate["start_index"]),
        eta=float(prestate["eta"]),
        redundancy_threshold=float(prestate["redundancy_consensus_threshold"]),
        meta_strength=float(prestate["meta_strength"]),
        calibration_strength=float(prestate["calibration_strength"]),
    )


def build_sandbox(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    readiness = preflight.build_preflight(root)
    if readiness["readiness_status"] != "PASS":
        raise RuntimeError("3054 adjudication preflight is not PASS")

    hashes_before = _hashes(root)
    if hashes_before["SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"] != EXPECTED_FREEZE_SHA256:
        raise ValueError("3054 freeze hash mismatch")

    prestate = json.loads((root / "SMART_SIGNAL_STATE_3054_V2.json").read_text(encoding="utf-8-sig"))
    if int(prestate.get("last_contest", -1)) != 3053:
        raise ValueError("3054 prestate must end at 3053")
    if prestate.get("data_sha256") != sha256_file(root / "Mega-Sena_through_3053_v2.xlsx"):
        raise ValueError("3054 prestate data hash mismatch")

    with tempfile.TemporaryDirectory(prefix="smart3054-full-cycle-") as raw_tmp:
        tmp = Path(raw_tmp)
        ledger = tmp / "SMART_SIGNAL_LEDGER.sandbox.json"
        through = tmp / "Mega-Sena_through_3054.synthetic.xlsx"
        learned = tmp / "SMART_SIGNAL_STATE_3054_LEARNED.synthetic.json"
        shutil.copy2(root / "SMART_SIGNAL_LEDGER.json", ledger)

        synthetic_payload = {
            "numero": TARGET,
            "dataApuracao": "05/09/2026",
            "listaDezenas": ["01", "02", "03", "04", "05", "06"],
            "acumulado": False,
        }
        official = official_ingest.validate_official_payload(synthetic_payload, TARGET)
        frame = official_ingest.build_extended_frame(root / "Mega-Sena.xlsx", TARGET, official)
        frame.to_excel(through, index=False)
        draws, contests = load_draws(through)
        if int(contests[-1]) != TARGET:
            raise RuntimeError("sandbox result dataset does not end at 3054")

        cwd_before = Path.cwd()
        try:
            os.chdir(root)
            adjudication = adjudicator.adjudicate(through, TARGET, ledger)
            agent = _agent_from_prestate(prestate)
            replay = agent.replay_history(draws, contests)
            learned_state = agent.state_document(data_sha256=sha256_file(through))
            learned_state.update({
                "sequential_learning_target": TARGET,
                "learning_after_adjudication": True,
                "sandbox_only": True,
                "synthetic_result_has_predictive_authority": False,
            })
            learned.write_text(json.dumps(learned_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            learning = sequential.append_learning_update(ledger, TARGET, learned, through)
            proof = sequential.append_sequence_proof(ledger, TARGET)
            final_ledger = json.loads(ledger.read_text(encoding="utf-8"))
            validation = sequential.validate_target_sequence(
                final_ledger,
                TARGET,
                require_learning=True,
                require_proof=True,
                verify_files=True,
                root=root,
            )

            duplicate_learning_rejected = False
            duplicate_learning_error = None
            try:
                sequential.append_learning_update(ledger, TARGET, learned, through)
            except ValueError as exc:
                duplicate_learning_rejected = True
                duplicate_learning_error = str(exc)

            duplicate_proof_rejected = False
            duplicate_proof_error = None
            try:
                sequential.append_sequence_proof(ledger, TARGET)
            except ValueError as exc:
                duplicate_proof_rejected = True
                duplicate_proof_error = str(exc)
        finally:
            os.chdir(cwd_before)

        if not validation.get("valid"):
            raise RuntimeError("full sandbox sequence validation failed")
        if not duplicate_learning_rejected or not duplicate_proof_rejected:
            raise RuntimeError("full sandbox duplicate guards failed")
        if int(learned_state.get("last_contest", -1)) != TARGET:
            raise RuntimeError("learned state does not end at 3054")

        target_types = [
            event.get("event_type")
            for event in final_ledger.get("events", [])
            if int(event.get("target_contest", -1)) == TARGET
        ]
        expected_tail = [sequential.LEARNING_EVENT, sequential.PROOF_EVENT]
        if target_types[-2:] != expected_tail:
            raise RuntimeError("full sandbox sequence does not end in learning then proof")

        hashes_after = _hashes(root)
        if hashes_after != hashes_before:
            raise RuntimeError("full-cycle sandbox mutated canonical protected artifacts")

        checks = {
            "preflight_pass": True,
            "synthetic_official_payload_validated": True,
            "synthetic_dataset_ends_at_3054": True,
            "adjudication_completed": int(adjudication["target_contest"]) == TARGET,
            "learning_state_trained_through_3054": int(learned_state["last_contest"]) == TARGET,
            "learning_event_recorded": learning.get("status") == "LEARNING_RECORDED",
            "sequential_proof_recorded": proof.get("status") == "SEQUENCE_PROVEN",
            "full_sequence_valid": validation.get("valid") is True,
            "duplicate_learning_rejected": duplicate_learning_rejected,
            "duplicate_proof_rejected": duplicate_proof_rejected,
            "canonical_protected_artifacts_unchanged": hashes_after == hashes_before,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "schema": SCHEMA,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "target_contest": TARGET,
            "cutoff_contest": 3053,
            "status": status,
            "active_freeze_sha256": EXPECTED_FREEZE_SHA256,
            "synthetic_result": official["numbers"],
            "synthetic_result_authority": "NONE_SANDBOX_ONLY",
            "adjudication": {
                "champion_hits": int(adjudication["champion_hits"]),
                "challenger_hits": int(adjudication["challenger_hits"]),
                "e_value_after": float(adjudication["e_value_after"]),
            },
            "learning": {
                "agent_start_index": int(prestate["start_index"]),
                "last_contest": int(learned_state["last_contest"]),
                "data_sha256": learned_state["data_sha256"],
                "replay_rows": len(replay["rows"]),
                "learning_event_status": learning["status"],
            },
            "sequence": validation,
            "target_event_types": target_types,
            "duplicate_guards": {
                "learning_rejected": duplicate_learning_rejected,
                "learning_error": duplicate_learning_error,
                "proof_rejected": duplicate_proof_rejected,
                "proof_error": duplicate_proof_error,
            },
            "canonical_hashes_before": hashes_before,
            "canonical_hashes_after": hashes_after,
            "checks": checks,
            "official_result_ingested": False,
            "canonical_learning_executed": False,
            "terminal_6of6_proven": False,
        }


def write_sandbox(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    document = build_sandbox(root)
    (root / "SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = write_sandbox(project_root)
    print(json.dumps({
        "status": result["status"],
        "target": result["target_contest"],
        "learning_last_contest": result["learning"]["last_contest"],
        "sequence_valid": result["sequence"]["valid"],
        "duplicate_guards": result["duplicate_guards"],
        "canonical_unchanged": result["checks"]["canonical_protected_artifacts_unchanged"],
    }, ensure_ascii=False))

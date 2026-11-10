"""Research-only reproducible two-stage causal replay. Never touches official epochs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from smart_native_signal_research import (
    _approved_local, canonical_hash, hash_document, strict_json_loads,
    produce_contributions, build_research_challenger, ablate_research,
    adjudicate_replay, next_epoch_research_weights,
)
from smart_frontier_signal_lab import sha256_file
import smart_v2_engine as e

SCHEMA = "SMART_NATIVE_RESEARCH_E2E_V1"
CUTS = (3073, 3074, 3075, 3076, 3077, 3078, 3079, 3080)
RESEARCH_WEIGHTS = {
    "frontier_gap_hazard": 0.05,
    "frontier_transition_markov": 0.0,
    "frontier_cooccurrence_graph": 0.0,
    "frontier_weekday_bayes": 0.0,
    "frontier_recent_lift": 0.1,
}


def _save(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        actual = strict_json_loads(path.read_text(encoding="utf-8"))
        if actual != document:
            raise ValueError(f"conflict: refuses overwriting recorded replay artifact {path}")
        return
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _load(path: Path) -> dict:
    data = strict_json_loads(path.read_text(encoding="utf-8"))
    if data["sha256"] != canonical_hash({k: v for k, v in data.items() if k != "sha256"}):
        raise ValueError(f"replay authority document corrupted: {path}")
    return data


def prepare(master: Path, out: Path) -> dict:
    master = _approved_local(master)
    out = _approved_local(out)
    if not master.is_file():
        raise FileNotFoundError(master)
    frame = pd.read_excel(master)
    draws, contests = e.load_draws(master)
    if len(frame) != len(contests) or len(set(contests.tolist())) != len(contests):
        raise ValueError("master historical workbook corrupt")
    if int(contests[-1]) < max(CUTS) + 1:
        raise ValueError("master lacks the last required historical result")
    if int(contests[0]) != 1 or any(int(contests[i])-int(contests[i-1]) != 1 for i in range(1,len(contests))):
        raise ValueError("historical contests are not contiguous")
    if "Concurso" not in frame:
        raise ValueError("no column Concurso")
    verified_contests = frame["Concurso"].to_numpy()
    if any(int(verified_contests[i]) != int(contests[i]) for i in range(len(contests))):
        raise ValueError("contest column did not match engine")
    rows = []
    out.mkdir(parents=True, exist_ok=True)
    for cut in CUTS:
        p = out / f"Mega-Sena_cutoff_{cut}.xlsx"
        if not p.exists():
            frame.iloc[:cut].to_excel(p, index=False)
        actual_draws, actual_contests = e.load_draws(p)
        if len(actual_contests) != cut or int(actual_contests[-1]) != cut:
            raise ValueError("source snapshot violates declared cutoff")
        if not (actual_draws == draws[:cut]).all():
            raise ValueError("source snapshot differs from original historical rows")
        rows.append({"cutoff_contest": cut, "target_contest": cut+1, "filename": p.name,
                     "dataset_sha256": sha256_file(p), "row_count": cut})
    manifest = hash_document({
        "schema": SCHEMA, "mode": "HISTORICAL_REPLAY_PREPARED",
        "cutoffs_predeclared": list(CUTS),
        "master_file_sha256": sha256_file(master),
        "sources_are_historical_workbook_not_independent_CAIXA_api": True,
        "snapshots": rows,
        "production_authority": False, "prospective_advantage_proven": False
    })
    _save(out/"REPLAY_MANIFEST.json", manifest)
    return manifest


def freeze(out: Path) -> dict:
    out = _approved_local(out)
    manifest = _load(out/"REPLAY_MANIFEST.json")
    if tuple(manifest["cutoffs_predeclared"]) != CUTS:
        raise ValueError("replay cases do not match preregistered windows")
    results = []
    for entry in manifest["snapshots"]:
        target = int(entry["target_contest"])
        path = _approved_local(out/entry["filename"])
        if sha256_file(path) != entry["dataset_sha256"]:
            raise ValueError("cutoff snapshot dataset hash changed")
        contributions = produce_contributions(path, target_contest=target,
                                               epoch_id=f"REPLAY-{target}")
        rows = [contributions[name] for name in sorted(contributions)]
        challenger = build_research_challenger(rows, RESEARCH_WEIGHTS)
        ablations = ablate_research(rows, RESEARCH_WEIGHTS, full=challenger)
        freeze_doc = hash_document({
            "schema": SCHEMA,
            "mode": "HISTORICAL_REPLAY_FROZEN",
            "target_contest": target, "cutoff_contest": target - 1,
            "manifest_sha256": manifest["sha256"],
            "dataset_sha256": entry["dataset_sha256"],
            "contributions": contributions,
            "challenger": challenger,
            "ablation": ablations,
            "result_used": False,
            "production_authority": False,
        })
        _save(out/f"REPLAY_FREEZE_{target}.json", freeze_doc)
        results.append({
            "target_contest": target,
            "freeze_sha256": freeze_doc["sha256"],
            "top6": challenger["top6"],
            "max_producer_delta": max(v["max_abs_delta"] for v in ablations["by_producer"].values()),
        })
    return {"prepared": len(results), "freeze_rows": results, "result_used": False}


def adjudicate(master: Path, out: Path) -> dict:
    out = _approved_local(out)
    master = _approved_local(master)
    manifest = _load(out/"REPLAY_MANIFEST.json")
    if manifest["master_file_sha256"] != sha256_file(master):
        raise ValueError("original historical result workbook changed")
    actual_draws, contests = e.load_draws(master)
    lookup = {int(c): sorted(map(int, actual_draws[i].tolist())) for i, c in enumerate(contests)}
    rows = []
    for entry in manifest["snapshots"]:
        target = entry["target_contest"]
        frozen = _load(out/f"REPLAY_FREEZE_{target}.json")
        if frozen["manifest_sha256"] != manifest["sha256"] or frozen["dataset_sha256"] != entry["dataset_sha256"]:
            raise ValueError("freeze not bound to original snapshot")
        result = {
            "contest": target, "numbers": lookup[target],
            "source_sha256": sha256_file(master), "source_kind": "HISTORICAL_REPLAY",
        }
        receipt = adjudicate_replay(frozen["challenger"], result, out/"ledger", source_path=master)
        again = adjudicate_replay(frozen["challenger"], result, out/"ledger", source_path=master)
        if receipt != again or receipt["result_source_verified"] is not True:
            raise ValueError("adjudication replay idempotency or source failed")
        rows.append({"contest": target, "challenger_hits": receipt["challenger_hits"],
                     "challenger_top6": frozen["challenger"]["top6"],
                     "result_numbers": lookup[target],
                     "freeze_sha256": frozen["sha256"],
                     "adjudication_sha256": receipt["sha256"],
                     "max_producer_delta": max(v["max_abs_delta"] for v in frozen["ablation"]["by_producer"].values()),
                     "result_source_verified": True})
    proof = hash_document({
        "schema": SCHEMA, "mode": "HISTORICAL_TWO_PHASE_REPLAY_COMPLETE",
        "precommitted_cutoffs": list(CUTS), "replays": rows,
        "count": len(rows), "prediction_authority": False,
        "prospective_advantage_proven": False,
        "main_champion_unmodified": "NOT_TESTED",
        "result_used_only_after_research_freeze": True,
        "replay_artifacts": "research only",
    })
    _save(out/"SMART_NATIVE_E2E_REPLAY_PROOF.json", proof)
    return proof



def learn_next_epoch(out: Path, *, previous_target: int = 3075) -> dict:
    """Proof that a previously adjudicated N can govern only research N+1."""
    out = _approved_local(out)
    before = _load(out / f"REPLAY_FREEZE_{previous_target}.json")
    after = _load(out / f"REPLAY_FREEZE_{previous_target+1}.json")
    receipts = sorted((out / "ledger").glob(f"REPLAY_{previous_target}_*.json"))
    if len(receipts) != 1:
        raise ValueError("previous-result source must have exactly one adjudication receipt")
    verified = _load(receipts[0])
    proposal = next_epoch_research_weights(
        before["challenger"], verified,
        next_target_contest=previous_target + 1, research_authorized=True,
    )
    rows = [after["contributions"][name] for name in sorted(after["contributions"])]
    revised = build_research_challenger(rows, proposal["weights_effective_next_research"])
    unchanged = after["challenger"]
    numeric = max(abs(revised["scores_by_number"][str(i)] -
                      unchanged["scores_by_number"][str(i)]) for i in range(1,61))
    proof = hash_document({
        "schema": "SMART_NATIVE_RESEARCH_NEXT_EPOCH_CONSUMPTION_V1",
        "phase": "HISTORICAL_REPLAY_LEARNED_AFTER_PREVIOUS_RESULT",
        "previous_target_contest": previous_target,
        "next_target_contest": previous_target + 1,
        "previous_receipt_sha256": verified["sha256"],
        "next_original_freeze_sha256": after["sha256"],
        "next_original_challenger_sha256": unchanged["sha256"],
        "next_research_weight_snapshot": proposal,
        "next_research_challenger": revised,
        "max_abs_score_effect": numeric,
        "next_epoch_result_used": False,
        "official_card_changed": False,
        "production_authority": False,
        "prospective_advantage_proven": False,
    })
    _save(out / f"REPLAY_LEARNED_NEXT_{previous_target+1}.json", proof)
    return {"target": previous_target+1, "score_effect": numeric,
            "previous_receipt_sha256": verified["sha256"],
            "new_challenger_sha256": revised["sha256"],
            "proof_sha256": proof["sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "freeze", "adjudicate", "learn"])
    parser.add_argument("--master", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.phase in {"freeze", "learn"}:
        if args.master is not None:
            parser.error("freeze must never receive future-result source")
        answer = freeze(args.out) if args.phase == "freeze" else learn_next_epoch(args.out)
    else:
        if args.master is None:
            parser.error("historical source required outside freeze phase")
        answer = (prepare(args.master, args.out) if args.phase == "prepare"
                  else adjudicate(args.master, args.out))
    print(json.dumps(answer, ensure_ascii=False, sort_keys=True)[:3000])


if __name__ == "__main__":
    main()

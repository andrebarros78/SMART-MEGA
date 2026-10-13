"""Read-only historical paired comparison; no production promotion authority."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
from smart_v2_engine import load_draws

SCHEMA = "SMART_PREDICTIVE_PAIRED_ARCHIVE_GATE_1"

def _six(v):
    if not isinstance(v, list) or len(v) != 6 or any(type(x) is not int or x < 1 or x > 60 for x in v) or len(set(v)) != 6:
        raise ValueError("invalid frozen six-number prediction or official result")
    return v

def _date(v):
    d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if d.utcoffset() is None: raise ValueError("naive timestamp")
    return d

def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def evaluate(root):
    root = Path(root).resolve()
    ledger_path = root / "SMART_SIGNAL_LEDGER.json"
    history_path = root / "Mega-Sena.xlsx"
    events = json.loads(ledger_path.read_text(encoding="utf-8-sig"))["events"]
    draws, contests = load_draws(history_path)
    official = {int(t): set(map(int, draw)) for t, draw in zip(contests, draws)}
    groups = defaultdict(list)
    for event in events:
        if type(event.get("target_contest")) is int and event.get("event_type") in ("FREEZE", "ADJUDICATION"):
            groups[event["target_contest"]].append(event)
    verified, excluded = [], []
    for contest, rows in sorted(groups.items()):
        adjs = [v for v in rows if v["event_type"] == "ADJUDICATION"]
        if not adjs: continue
        if len(adjs) != 1: raise ValueError("duplicate adjudication")
        adj = adjs[0]
        freeze_sha = adj.get("freeze_sha256")
        matched = [v for v in rows if v["event_type"] == "FREEZE" and v.get("freeze_sha256") == freeze_sha]
        if len(matched) != 1 or not isinstance(freeze_sha, str) or len(freeze_sha) != 64:
            raise ValueError("ambiguous or unbound adjudicated freeze")
        event = matched[0]
        if event.get("frozen_before_result") is not True or event.get("causal_cutoff") is not True or event.get("cutoff_contest") != contest - 1:
            raise ValueError("invalid frozen causal authority")
        if _date(event["created_utc"]) >= _date(adj["created_utc"]):
            raise ValueError("freeze not before adjudication")
        actual = set(_six(adj["actual_numbers"]))
        if actual != official.get(contest): raise ValueError("adjudication disagrees with canonical draw")
        value = event.get("freeze_file")
        if not isinstance(value, str) or not value: raise ValueError("freeze path missing")
        path = root / value
        if path.is_symlink() or not path.resolve().is_relative_to(root): raise ValueError("unsafe frozen path")
        if not path.is_file():
            excluded.append({"contest": contest, "reason": "original_frozen_file_unavailable", "freeze_sha256": freeze_sha})
            continue
        if _sha(path) != freeze_sha: raise ValueError("immutable freeze hash mismatch")
        freeze = json.loads(path.read_text(encoding="utf-8-sig"))
        if (freeze.get("target_contest") != contest or freeze.get("cutoff_contest") != contest-1
                or freeze.get("frozen_before_result") is not True
                or freeze.get("champion_remains_active") is not True):
            raise ValueError("frozen target/cutoff or champion authority mismatch")
        champion = _six(freeze["champion"]["top6"])
        challenger = _six(freeze["challenger"]["top6"])
        if champion != _six(event["champion_top6"]) or challenger != _six(event["challenger_top6"]):
            raise ValueError("frozen card does not match adjudicated ledger")
        signals = freeze["challenger"]["raw_signals"]
        weights = freeze["challenger"]["weights"]
        scores = freeze["challenger"]["aggregate_scores"]
        if (len(weights) != 12 or set(weights) != set(signals) or len(scores) != 60
                or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in weights.values())
                or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12, rel_tol=0)):
            raise ValueError("incomplete causal signal weights")
        for signal in signals.values():
            if (signal.get("cutoff_contest") != contest - 1 or
                    signal.get("target_contest") != contest or signal.get("causal") is not True):
                raise ValueError("invalid signal cutoff or future result contamination")
        err = max(abs(float(scores[str(n)]) - sum(float(weights[k])*float(signals[k]["values"][str(n)]) for k in weights)) for n in range(1, 61))
        if not math.isfinite(err) or err >= 1e-10: raise ValueError("signal weights not consumed")
        verified.append({"contest": contest, "freeze_sha256": freeze_sha,
                         "champion_hits": len(actual & set(champion)),
                         "challenger_hits": len(actual & set(challenger)),
                         "max_score_error": err})
    if not verified: raise ValueError("no archive-backed paired comparisons")
    c = sum(v["champion_hits"] for v in verified)
    h = sum(v["challenger_hits"] for v in verified)
    return {"schema": SCHEMA, "status": "HISTORICAL_ARCHIVAL_COMPARISON_ONLY",
            "source_sha256": {"history": _sha(history_path), "ledger": _sha(ledger_path)},
            "adjudicated_count": len(verified)+len(excluded),
            "verified_count": len(verified), "excluded": excluded, "rows": verified,
            "champion_hits": c, "challenger_hits": h, "challenger_minus_champion_hits": h-c,
            "uniform_expected_hits": 0.6*len(verified), "prospective_e_value_proven": False,
            "all_primary_card_predictions_replayed": False,
            "promotion_authorized": False, "prospective_superiority_proven": False,
            "six_of_six_proven": False,
            "limitations": [f"{len(excluded)} original archived freeze files unavailable" if excluded else "all referenced frozen files are available",
                            "archive availability may be selective",
                            "event earlier than adjudication alone is not independently verified pre-draw publication",
                            "compared champion/challenger heads are not always the final primary card",
                            f"the {len(verified)}-draw historical subset cannot support prospective promotion"]}

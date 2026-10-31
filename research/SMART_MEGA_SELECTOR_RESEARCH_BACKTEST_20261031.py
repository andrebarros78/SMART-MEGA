"""Causal historical, research-only A/B selector evaluation.

This is retrospective after observing 3079 and NOT an untouched prospective test.
All variant rules specified before comparing test outputs in this file.
"""
import argparse
import hashlib
import json
import math
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from smart_primary_card_selector import (
    PrimaryCardSelectorConfig, select_primary_card,
)
from smart_primary_card_selector_research import select_primary_card_research
from smart_v2_engine import load_draws, onehot, precompute_scores, walk_forward, rank_top6
from smart_official_result_validation import validate_official_payload

RESEARCH_VARIANTS = (
    ("A_DEFAULT_18_TOP3", 18, True, None),
    ("B_POOL18_NO_TOP3", 18, False, None),
    ("C_POOL30_NO_TOP3", 30, False, None),
    ("D_POOL60_NO_TOP3", 60, False, None),
    ("E_POOL60_NO_TOP3_FREQ1000_CAP20", 60, False, .20),
    ("F_POOL60_TOP3_CONTROL", 60, True, None),
)
# Explicitly fixed *before* outcomes are inspected inside the evaluation loop.
WINDOWS = ((2600, 2850, "DEVELOPMENT"), (2851, 2950, "SELECTION"), (2951, 3078, "RETROSPECTIVE_EVALUATION"))


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _renormalize_cap(weights, cap):
    if cap is None or weights["freq1000"] <= cap:
        return weights
    original = weights["freq1000"]
    factor = (1 - cap) / (1 - original)
    result = {n: (cap if n == "freq1000" else weight * factor) for n, weight in weights.items()}
    assert abs(sum(result.values()) - 1) < 1e-8
    return result


def _variant_scores(pre, t, names, weights, cap):
    w = _renormalize_cap(weights, cap)
    return sum(w[n] * pre[n][t] for n in names)


def _card(pre, t, names, weights, pool_size, mandatory_top3, cap):
    vector = _variant_scores(pre,t,names,weights,cap)
    top,order = rank_top6(vector)
    rank = [int(n+1) for n in order]
    cfg = PrimaryCardSelectorConfig(candidate_pool_size=pool_size, max_candidate_pool_size=pool_size,
                                     require_top3_presence=mandatory_top3)
    sel = select_primary_card_research({n+1:float(vector[n]) for n in range(60)},rank,cfg)
    assert sel["result_used"] is False and sel["model_promotion_authorized"] is False
    return sel,rank


REFERENCE_3078_HISTORY_CONTENT_SHA256 = "5ec523f29d6177102b4a92006071379f000d63fd2c40b93ec70a4df3b7aadf47"


def append_canonical_result(draws, contests, payload):
    """Append one official 3078 observation after 3077 without changing prior inputs."""
    if int(contests[-1]) != 3077:
        raise ValueError("reconstruction requires the authenticated 3077 cutoff")
    if payload.get("numero") != 3078 or payload.get("numeroConcursoAnterior") != 3077:
        raise ValueError("official contest predecessor does not match frozen data")
    normalized = validate_official_payload(payload,3078)
    if normalized["draw_date_text"] != "29/10/2026":
        raise ValueError("unexpected 3078 draw date")
    import numpy as np
    extended_draws = np.vstack([draws,np.asarray(normalized["numbers"],dtype=int)[None,:]])
    extended_contests = np.append(contests,3078)
    assert len(extended_draws)==len(extended_contests)
    return extended_draws,extended_contests


def load_cutoff_3078(source:Path,extra_result:Path|None):
    draws,contests=load_draws(source)
    raw_sha=None
    if int(contests[-1])==3077 and extra_result is not None:
        payload=json.loads(extra_result.read_text(encoding="utf-8-sig"))
        draws,contests=append_canonical_result(draws,contests,payload)
        raw_sha=hashlib.sha256(extra_result.read_bytes()).hexdigest()
    elif int(contests[-1])!=3078 or extra_result is not None:
        raise ValueError("provide either a complete 3078 workbook, or 3077 with an official 3078 observation")
    content=json.dumps({"contests":contests.tolist(),"draws":draws.tolist()},separators=(",",":")).encode()
    content_sha=hashlib.sha256(content).hexdigest()
    if content_sha!=REFERENCE_3078_HISTORY_CONTENT_SHA256:
        raise ValueError("reconstructed research cutoff differs from independently captured 3078 history")
    return draws,contests,content_sha,raw_sha


def evaluate(source: Path, output: Path, start=1000, extra_result:Path|None=None):
    draws,contests,content_sha,official_extra_sha=load_cutoff_3078(source,extra_result)
    assert int(contests[-1]) == 3078, "research cutoff must remain 3078, never 3079"

    pre = precompute_scores(onehot(draws))
    wf = walk_forward(draws,contests,start=start,pre=pre)
    names = list(pre)
    records = []
    full_matches = 0
    samples_checked = 0
    for row in wf.rows:
        contest = int(row["contest"])
        if not WINDOWS[0][0] <= contest <= WINDOWS[-1][1]:
            continue
        t = contest - int(contests[0])
        assert t > 0 and int(contests[t-1]) == contest-1
        w = dict(row["weights"])
        actual = set(int(x) for x in draws[t])
        picks = {}
        for name,pool,top3,cap in RESEARCH_VARIANTS:
            sel,rank = _card(pre,t,names,w,pool,top3,cap)
            hit = len(actual.intersection(sel["selected_numbers"]))
            recall = len(actual.intersection(rank[:pool]))
            picks[name]={"numbers":sel["selected_numbers"],"hits":hit,
                         "pool_recall":recall,"rank_of_drawn":[rank.index(n)+1 for n in sorted(actual)],
                         "states":sel["evaluated_combinations"]}
        if samples_checked < 16:
            vector=_variant_scores(pre,t,names,w,None)
            rank=sorted(range(1,61),key=lambda n:(-vector[n-1],n))
            cfg=PrimaryCardSelectorConfig()
            expected=select_primary_card({n:float(vector[n-1]) for n in range(1,61)},rank,cfg)
            if picks["A_DEFAULT_18_TOP3"]["numbers"] != expected["selected_numbers"]:
                raise AssertionError(f"original and exact select disagree on contest {contest}")
            full_matches+=1
        samples_checked+=1
        records.append({"contest":contest,"actual":sorted(actual),"variants":picks})
    assert records and full_matches==16

    sections={}
    for low,high,label in WINDOWS:
        data=[r for r in records if low<=r["contest"]<=high]
        assert len(data)==high-low+1
        samples={}
        for name,*_ in RESEARCH_VARIANTS:
            values=[r["variants"][name]["hits"] for r in data]
            baseline=np.array([r["variants"]["A_DEFAULT_18_TOP3"]["hits"] for r in data],dtype=float)
            arr=np.array(values,dtype=float)
            diffs=arr-baseline
            rng=np.random.default_rng(3079+len(name)*97+low)
            idx=rng.integers(0,len(data),size=(2000,len(data)))
            means=diffs[idx].mean(axis=1)
            samples[name]={
                "draws":len(data),
                "total_hits":int(arr.sum()),
                "mean_hits":float(arr.mean()),
                "zero_hit_count":int(np.sum(arr==0)),
                "six_hit_count":int(np.sum(arr==6)),
                "paired_excess_hits":int(arr.sum()-baseline.sum()),
                "paired_mean_hit_difference":float(diffs.mean()),
                "paired_bootstrap95_interval":[float(x) for x in np.quantile(means,[.025,.975])],
                "mean_candidate_pool_recall":float(np.mean([r["variants"][name]["pool_recall"] for r in data])),
            }
        sections[label]={"contests":[low,high],"metrics":samples}
    evidence={
        "schema":"SMART_SELECTOR_EXACT_COMPARATIVE_EVIDENCE_1",
        "status":"RESEARCH_ONLY_NO_PROSPECTIVE_CERTIFICATION",
        "hypotheses_defined_after_known_3079_result":True,
        "not_an_independent_scientific_holdout":True,
        "future_result_in_input":False,
        "target_3079_used_in_parameter_selection":True,
        "data_cutoff":3078,
        "data_file":source.name,
        "historical_content_sha256":content_sha,
        "official_3078_capture_sha256":official_extra_sha,
        "official_3078_capture_file":extra_result.name if extra_result else None,
        "reconstruct_from_remote_3077_plus_official_3078":official_extra_sha is not None,
        "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "backtest_script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "selector_module_sha256":hashlib.sha256((ROOT/"smart_primary_card_selector_research.py").read_bytes()).hexdigest(),
        "champion_selector_sha256":hashlib.sha256((ROOT/"smart_primary_card_selector.py").read_bytes()).hexdigest(),
        "causal_weighting":"walk_forward learned from earlier contests only; fixed research comparisons per t",
        "variants":[{"name":n,"pool":p,"require_top3":t,"effective_freq1000_cap":c} for n,p,t,c in RESEARCH_VARIANTS],
        "windows":[{"start":l,"end":h,"role":tag} for l,h,tag in WINDOWS],
        "exact_solver_equivalence_checked_against_exhaustive_champion":full_matches,
        "sections":sections,
        "promotion_authorized":False,
        "scientific_6_of_6_proven":False,
        "created_utc":datetime.now(timezone.utc).isoformat()
    }
    evidence["sha256"]=_hash(evidence)
    with output.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(evidence,f,ensure_ascii=False,indent=2);f.write("\n")
    return evidence


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--extra-result",help="Raw Caixa response for contest 3078 when --data ends at 3077")
    args=parser.parse_args()
    report=evaluate(Path(args.data),Path(args.out),extra_result=Path(args.extra_result) if args.extra_result else None)
    print(json.dumps({
       "status":report["status"],"source":report["source_sha256"],
       "equivalence_checks":report["exact_solver_equivalence_checked_against_exhaustive_champion"],
       "retrospective_evaluation":report["sections"]["RETROSPECTIVE_EVALUATION"]["metrics"],
       "sha256":report["sha256"]
    },ensure_ascii=False))
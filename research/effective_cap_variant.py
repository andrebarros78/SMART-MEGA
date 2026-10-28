"""Research-only cap adjustment. Never called by the official operator or production consumer.

The certified smart_v2_engine.py remains byte-identical to GitHub main. This
experimental function changes only the allocation order inside each family:
redundancy penalty first, capped simplex projection second.
"""
from __future__ import annotations

import math
import numpy as np
import smart_v2_engine as base


def walk_forward_capped(draws, contests, start=1000, eta=math.log(2),
                        pre=None, allowed=None):
    if pre is None:
        pre = base.precompute_scores(base.onehot(draws))
    names = list(pre) if allowed is None else list(allowed)
    fams = sorted(set(base.family_of(n) for n in names))
    elog = {n: 0.0 for n in names}
    flog = {f: 0.0 for f in fams}
    rows = []
    maxcorr = 0.0
    for t in range(start, len(draws)):
        sc = {n: pre[n][t] for n in names}
        pen, corr = base.redundancy_penalty(sc)
        maxcorr = max(maxcorr, float(np.max(np.abs(corr - np.eye(len(corr))))))
        fw = base.regularize(base.softmax(flog), prior_mix=base.PRIOR_MIX,
                             cap=base.FAMILY_CAP)
        eff = {}
        fam_scores = {}
        for family in fams:
            fn = [n for n in names if base.family_of(n) == family]
            ew = base.regularize(
                base.softmax({n: elog[n] for n in fn}),
                prior_mix=base.PRIOR_MIX, cap=base.EXPERT_CAP_WITHIN_FAMILY,
            )
            adjusted = base.regularize(
                {n: ew[n] * pen[n] for n in fn},
                prior_mix=0.0, cap=base.EXPERT_CAP_WITHIN_FAMILY,
            )
            for name in fn:
                eff[name] = fw[family] * adjusted[name]
            fam_scores[family] = sum(adjusted[n] * sc[n] for n in fn)
        agg = sum(eff[n] * sc[n] for n in names)
        top, _ = base.rank_top6(agg)
        actual = set(draws[t])
        hits = len(set(top) & actual)
        indiv = {}
        for n in names:
            etop, _ = base.rank_top6(sc[n])
            h = len(set(etop) & actual)
            indiv[n] = h
            elog[n] += eta * (h - base.UNIFORM_EXPECTED_HITS)
        fam_hits = {}
        for family in fams:
            ftop, _ = base.rank_top6(fam_scores[family])
            h = len(set(ftop) & actual)
            fam_hits[family] = h
            flog[family] += eta * (h - base.UNIFORM_EXPECTED_HITS)
        rows.append({
            "contest": int(contests[t]), "top6": top, "hits": hits,
            "expert_hits": indiv, "family_hits": fam_hits,
            "weights": eff, "family_weights": fw,
        })
    total = sum(row["hits"] for row in rows)
    expectation = len(rows) * base.UNIFORM_EXPECTED_HITS
    return base.WalkResult(
        rows, rows[-1]["weights"] if rows else {},
        rows[-1]["family_weights"] if rows else {},
        total, expectation, total - expectation, maxcorr,
    )

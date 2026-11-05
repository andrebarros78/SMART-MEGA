# SMART-MEGA selector comparison — research only, 2026-11-05

Status: NOT APPROVED FOR PRODUCTION. Frozen cards, canonical main, and
F11/F12 source and evidence hashes remain unmodified.

## Candidate

Original selector imposes 2–4 low (1–20), 1–3 mid (21–40), 0–2 high
(41–60) numbers, plus balance and concentration terms. The research
candidate removes these restrictions from default selection and retains
historical behavior if the original explicit configuration is supplied.

## Paired causal historical comparison (not prospective evidence)

Policies received identical prefix-only Champion scores using the repo's
online Hedge methods and draw data through contest 3080. Each prediction
used only earlier draws; results were applied only after scoring each
prediction. This isolates the selector, without using Challenger or
feedback-rescue promotion.

| Historical period | N | Legacy hits | Candidate hits | Delta | Changed cards |
|---|---:|---:|---:|---:|---:|
| 2601–2800 | 200 | 137 | 133 | -4 | 84 |
| 2801–3050 | 250 | 150 | 148 | -2 | 77 |
| 3051–3080 | 30 | 16 | 16 | 0 | 7 |
| TOTAL | 480 | 303 | 297 | -6 | 168 |

Paired sign test: candidate won 16 contests, lost 22, tied 442;
two-sided p approximately 0.418. Approximate 95% t interval for the
per-contest hit difference candidate minus legacy is [-0.0377, 0.0127].
Neither model achieved six hits. No superiority was demonstrated.

The evaluation is retrospective, not a prospectively held-out experiment.
The candidate was developed after the historical draws were available.
The contest-level machine-readable file contains cards, hit counts,
methodological fields, data hash and report self-hash.

## Safeguards

- Do not rewrite immutable F11/F12 proofs merely to force PASS.
- F11/F12 intentionally reject changed predictive implementations.
- Candidate is SHADOW/RESEARCH ONLY until new independent prospective
  evidence demonstrates a relevant advantage.
- Under independent uniform lottery draws, no ticket-selection technique
  is known to improve the 1/50,063,860 jackpot probability of one simple
  six-number ticket.

## Independent record-level audit (2026-11-05)

Read-only recomputation of all 480 rows from
`paired_causal_historical.json` at commit `29276341e10930717edccc3671f925e7a53f5616`:
- Contests are sequential 2601–3080; each `cutoff_contest = contest - 1`.
- All cards have six distinct valid numbers; identical cards always have identical hits.
- Recomputed: legacy 303, candidate 297; candidate-minus-legacy -6.
- 168 cards changed; 312 were identical. Hit comparisons: candidate 16 wins,
  legacy 22 wins, 442 ties. Difference histogram: -1 (22), 0 (442), +1 (16).
- Mean paired hit difference -0.0125 per contest; sample-based 95% interval
  approximately [-0.0377, +0.0127]. Exact two-sided paired sign p = 0.417692.
- Hit histograms for 0,1,2,3,4,5,6:
  legacy [242,179,53,6,0,0,0]; candidate [245,177,54,4,0,0,0].

### Uniform-reference diagnostic (not proof of full-model advantage)

Under the explicit null assumption of independent, fair 6-of-60 draws,
a fixed six-number ticket, including one chosen using *only previous draws*,
has mean 0.6 hits per draw and variance 0.4942372881. Over 480 draws the
expected hit total is 288. The upper-tail probabilities from exact
convolution of the 6-of-60 hypergeometric distribution are:
- P(total hits >= 303) = 0.173021 (legacy);
- P(total hits >= 297) = 0.288821 (candidate).

Neither historical count demonstrates a meaningful advantage over uniform.
These calculations audit the **reported card-hit counts**; they do not
independently reproduce the 12-expert/weight pipeline, validate the official
winning draws, or prove that both policies received identical 60-score vectors.

### Reproducibility gap and fail-closed status

The report metadata declares `code_commit`
`7224409d7c0978e75eb2651c38ef65b394e70a73`, but GitHub's
repository commit endpoint returned 422 "No commit found for SHA" when
checked on 2026-11-05. As a result, the code used to produce the historical
rows cannot be reconstructed from this recorded provenance alone.
The row report lacks per-contest score vectors and their common-input hashes.
Treat internal row reconciliation as **VERIFIED** and historical generator
provenance, raw-score equality and independent replay as **UNVERIFIED**.
Do not label this experiment a verified causal proof or scientific 6/6.

### Next scientific comparison (pre-registration requirements)

Keep main unchanged and candidate in research/shadow. For the next *authorized*
future contest, before the cutoff: produce one canonical 60-number score vector
using the unchanged 12-expert pipeline, capture its source/weight/model hashes,
and feed the identical vector to A and B. Record both cards even when equal;
do not force diversity. Freeze the selected cards, scoring probabilities,
cutoff, contestant ID, and the experiment's code/dataset SHA in immutable,
externally timestamped evidence **before** the official draw.
After the official result, score both cards and update only forward-looking
learning state. Keep the selector A/B test separate from the principal
SMART-complete-vs-uniform test: compare frozen 60-number probability forecasts
against a 0.1 marginal uniform reference using predeclared Brier/log-loss
metrics and report the six-hit outcome and ticket cost. Use predeclared
non-regression and held-out criteria before promoting any selector.
Do not mistake in-sample tuning, post-result information, or improved
intermediate metrics for prospective jackpot-probability proof.

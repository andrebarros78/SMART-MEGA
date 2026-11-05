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

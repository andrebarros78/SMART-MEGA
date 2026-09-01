from pathlib import Path
p=Path('smart_signal_weights.py')
s=p.read_text(encoding='utf-8-sig')
old="""def _expert_cap(weights: dict[str, float], cap: float = FINAL_EXPERT_CAP) -> dict[str, float]:

    out = _normalize(dict(weights))

    while True:
"""
new="""def _expert_cap(weights: dict[str, float], cap: float = FINAL_EXPERT_CAP) -> dict[str, float]:

    out = _normalize(dict(weights))
    if not out:
        raise ValueError('weights cannot be empty')
    # A cap below 1/N is mathematically infeasible for normalized weights and
    # previously caused a non-terminating redistribution loop on small helper
    # ensembles. Preserve the configured cap whenever feasible; otherwise use
    # the tightest feasible cap, 1/N.
    cap = max(float(cap), 1.0 / len(out))

    while True:
"""
if old not in s: raise SystemExit('expert cap marker missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from smart_v2_engine import load_draws, onehot

SCHEMA_NULL = "SMART_NULL_UNIVERSE_MANIFEST_V1"
SCHEMA_ATLAS = "SMART_RANDOMNESS_ATLAS_V1"
NUMBERS = np.arange(1, 61, dtype=int)
K = 6
DEFAULT_SEED = 20260904
DEFAULT_REPLICATIONS = 1000
ATLAS_WINDOWS = (1, 2, 3, 5, 10, 25, 50, 100, 250, 500, 1000)


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1048576), b""):
            h.update(b)
    return h.hexdigest()


def _v(draws):
    a = np.sort(np.asarray(draws, dtype=int), axis=1)
    if a.ndim != 2 or a.shape[1] != 6:
        raise ValueError("draws shape")
    if np.any(a < 1) or np.any(a > 60) or np.any(np.diff(a, axis=1) <= 0):
        raise ValueError("invalid draw")
    return a


def _weighted(rng, w):
    w = np.asarray(w, float).copy()
    w = np.where(np.isfinite(w) & (w >= 0), w, 0)
    if w.sum() <= 0:
        w[:] = 1
    if np.count_nonzero(w) < 6:
        raise ValueError("weighted sample requires at least six positive weights")
    # Gumbel-top-k is exactly Plackett-Luce weighted sampling without replacement,
    # equivalent in distribution to successive normalized weighted choice but faster.
    u = np.clip(rng.random(60), np.finfo(float).tiny, 1.0 - np.finfo(float).eps)
    score = np.where(w > 0, np.log(w) - np.log(-np.log(u)), -np.inf)
    selected = np.argpartition(score, -6)[-6:] + 1
    return np.sort(selected.astype(int))


def u0_uniform_iid(n, rng):
    if int(n) < 0:
        raise ValueError("n must be non-negative")
    if int(n) == 0:
        return np.empty((0, 6), dtype=int)
    # Ranking 60 independent continuous uniforms and taking the six smallest
    # is exactly a uniform 6-of-60 sample, with the heavy work vectorized.
    keys = rng.random((int(n), 60))
    chosen = np.argpartition(keys, kth=5, axis=1)[:, :6] + 1
    return np.sort(chosen.astype(int), axis=1)


def u1_temporal_permutation(draws, rng):
    a = _v(draws)
    return a[rng.permutation(len(a))].copy()


def u2_label_permutation(draws, rng):
    a = _v(draws)
    p = rng.permutation(NUMBERS)
    m = np.empty(61, int)
    m[1:] = p
    return np.sort(m[a], axis=1)


def u3_block_shuffle(draws, rng, block_size=25):
    a = _v(draws)
    blocks = [a[i : i + block_size] for i in range(0, len(a), block_size)]
    return np.vstack([blocks[i] for i in rng.permutation(len(blocks))])


def empirical_marginals(draws):
    return onehot(_v(draws)).mean(axis=0)


def _draw_masks_validated(a):
    masks: list[int] = []
    for row in a:
        mask = 0
        for number in row:
            mask |= 1 << (int(number) - 1)
        masks.append(mask)
    return masks


def prepare_u4_marginals(draws):
    """Validate once and return immutable starting bitmasks for U4."""
    return tuple(_draw_masks_validated(_v(draws)))


def _select_set_bit(mask: int, rank: int) -> int:
    if rank < 0 or rank >= mask.bit_count():
        raise ValueError("bit rank out of range")
    value = mask
    for _ in range(rank):
        value &= value - 1
    return value & -value


def _masks_to_draws(masks):
    out = np.empty((len(masks), 6), dtype=int)
    for i, mask in enumerate(masks):
        values: list[int] = []
        value = int(mask)
        while value:
            bit = value & -value
            values.append(bit.bit_length())
            value ^= bit
        if len(values) != 6:
            raise RuntimeError("U4 row cardinality invariant violated")
        out[i] = values
    return out


def u4_marginals_preserved(draws, rng, swap_steps=None, prepared_masks=None):
    """Exact fixed-marginal surrogate using bipartite 2x2 edge swaps.

    Bitmasks preserve the same transition rule as the former 60-column scan:
    choose two rows and uniformly select one exclusive number from each. Every
    accepted swap preserves six numbers per draw and every global marginal.
    """
    a = _v(draws)
    n = len(a)
    if prepared_masks is None:
        masks = _draw_masks_validated(a)
    else:
        if len(prepared_masks) != n:
            raise ValueError("prepared_masks length mismatch")
        masks = [int(value) for value in prepared_masks]
    steps = int(swap_steps or max(1000, 5 * n))
    # Draw all independent proposals in vectorized form; the sequential state
    # transition itself remains unchanged and exact.
    pairs = rng.integers(0, n, size=(steps, 2))
    uniforms = rng.random((steps, 2))
    for pair, uv in zip(pairs, uniforms):
        i = int(pair[0])
        j = int(pair[1])
        if i == j:
            continue
        mi = masks[i]
        mj = masks[j]
        left = mi & ~mj
        right = mj & ~mi
        if left == 0 or right == 0:
            continue
        left_count = left.bit_count()
        right_count = right.bit_count()
        x = _select_set_bit(left, min(int(float(uv[0]) * left_count), left_count - 1))
        y = _select_set_bit(right, min(int(float(uv[1]) * right_count), right_count - 1))
        masks[i] = (mi ^ x) | y
        masks[j] = (mj ^ y) | x
    return _masks_to_draws(masks)


def fit_transition_weights(draws, alpha=1.0):
    a = _v(draws)
    X = onehot(a)
    c = np.full((60, 60), alpha, float)
    d = np.full(60, 2 * alpha, float)
    for t in range(len(X) - 1):
        for i in np.flatnonzero(X[t] > 0):
            c[i] += X[t + 1]
            d[i] += 1
    return c / d[:, None]


def prepare_u5_dynamic(draws):
    """Fit U5 once so Monte Carlo replications reuse the same causal fit."""
    a = _v(draws)
    return fit_transition_weights(a), empirical_marginals(a) + 1e-6


def u5_fitted_dynamic(draws, rng, transition_weights=None, base_marginals=None):
    a = _v(draws)
    tr = fit_transition_weights(a) if transition_weights is None else np.asarray(transition_weights, float)
    base = empirical_marginals(a) + 1e-6 if base_marginals is None else np.asarray(base_marginals, float)
    if tr.shape != (60, 60) or base.shape != (60,):
        raise ValueError("invalid prepared U5 model")
    out = [_weighted(rng, base)]
    for _ in range(1, len(a)):
        prev = np.asarray(out[-1]) - 1
        out.append(_weighted(rng, 0.5 * base + 0.5 * tr[prev].mean(axis=0)))
    return np.asarray(out, int)


def u6_adversarial_controls(n, rng):
    if n < 20:
        raise ValueError("n<20")
    null = u0_uniform_iid(n, rng)
    bw = np.ones(60)
    bw[:10] = 4
    bias = np.asarray([_weighted(rng, bw) for _ in range(n)])
    low = np.r_[np.full(30, 3.0), np.ones(30)]
    high = np.r_[np.ones(30), np.full(30, 3.0)]
    regime = np.asarray([_weighted(rng, low if i < n // 2 else high) for i in range(n)])
    motif = u0_uniform_iid(n, rng)
    motif[::7] = np.array([1, 2, 3, 4, 5, 6])
    return {
        "u6_null_control": null,
        "u6_persistent_bias": bias,
        "u6_regime_switch": regime,
        "u6_repeated_motif": motif,
    }


def _entropy(p):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    return float(np.mean(-(p * np.log2(p) + (1 - p) * np.log2(1 - p))))


def _lz(bits):
    s = "".join("1" if x else "0" for x in np.asarray(bits, np.uint8).ravel())
    D = set()
    i = 0
    c = 0
    while i < len(s):
        j = i + 1
        while j <= len(s) and s[i:j] in D:
            j += 1
        D.add(s[i:j])
        c += 1
        i = j
    return c


def atlas_descriptors(draws):
    a = _v(draws)
    X = onehot(a)
    sums = a.sum(1)
    even = (a % 2 == 0).sum(1)
    spans = a[:, -1] - a[:, 0]
    gaps = np.diff(a, axis=1) - 1
    cons = (np.diff(a, axis=1) == 1).sum(1)
    rep = np.zeros(len(a), int)
    if len(a) > 1:
        rep[1:] = (X[1:] * X[:-1]).sum(1).astype(int)
    marg = X.mean(0)
    pairs = X.T @ X
    np.fill_diagonal(pairs, 0)
    up = pairs[np.triu_indices(60, 1)]
    return {
        "n_draws": int(len(a)),
        "marginal_probability": [float(x) for x in marg],
        "marginal_min": float(marg.min()),
        "marginal_max": float(marg.max()),
        "marginal_std": float(marg.std(ddof=1)),
        "binary_entropy_mean_bits": _entropy(marg),
        "lz_phrase_count": int(_lz(X)),
        "sum": {"mean": float(sums.mean()), "std": float(sums.std(ddof=1)) if len(sums) > 1 else 0.0},
        "even_count": {"mean": float(even.mean()), "distribution": {str(k): int(np.sum(even == k)) for k in range(7)}},
        "span": {"mean": float(spans.mean()), "std": float(spans.std(ddof=1)) if len(spans) > 1 else 0.0},
        "internal_gap_mean": float(gaps.mean()),
        "consecutive_pairs_mean": float(cons.mean()),
        "repeat_from_previous_mean": float(rep[1:].mean()) if len(a) > 1 else 0.0,
        "pair_cooccurrence": {"mean": float(up.mean()), "std": float(up.std(ddof=1)), "max": int(up.max())},
    }


def _stat(draws):
    """Compute only the six Monte Carlo statistics; omit unused LZ/pair work."""
    a = _v(draws)
    X = onehot(a)
    marg = X.mean(axis=0)
    sums = a.sum(axis=1)
    spans = a[:, -1] - a[:, 0]
    cons = (np.diff(a, axis=1) == 1).sum(axis=1)
    repeat = (X[1:] * X[:-1]).sum(axis=1) if len(a) > 1 else np.asarray([], dtype=float)
    return {
        "marginal_std": float(marg.std(ddof=1)),
        "sum_mean": float(sums.mean()),
        "span_mean": float(spans.mean()),
        "repeat_prev_mean": float(repeat.mean()) if len(repeat) else 0.0,
        "consecutive_pairs_mean": float(cons.mean()),
        "entropy": _entropy(marg),
    }


def _compare(obs, vals):
    a = np.asarray(vals, float)
    m = float(a.mean())
    sd = float(a.std(ddof=1)) if len(a) > 1 else 0.0
    z = (obs - m) / sd if sd > 0 else 0.0
    p = float((1 + np.sum(np.abs(a - m) >= abs(obs - m))) / (len(a) + 1))
    return {"observed": float(obs), "null_mean": m, "null_std": sd, "z": float(z), "empirical_two_sided_p": p}


def _windows(draws):
    a = _v(draws)
    out = {}
    for w in ATLAS_WINDOWS:
        if len(a) >= w:
            d = atlas_descriptors(a[-w:])
            out[str(w)] = {
                "sum_mean": d["sum"]["mean"],
                "even_mean": d["even_count"]["mean"],
                "span_mean": d["span"]["mean"],
                "repeat_prev_mean": d["repeat_from_previous_mean"],
                "marginal_std": d["marginal_std"],
            }
    return out


def build_null_manifest(draws, replications=DEFAULT_REPLICATIONS, seed=DEFAULT_SEED, block_size=25):
    a = _v(draws)
    if replications < 20:
        raise ValueError("replications must be >=20")
    return {
        "schema": SCHEMA_NULL,
        "seed": int(seed),
        "replications": int(replications),
        "trajectory_length": int(len(a)),
        "families": {
            "U0": "uniform iid 6-of-60 without replacement",
            "U1": "temporal permutation preserving real draws",
            "U2": "global label permutation 1..60",
            "U3": f"temporal block shuffle block_size={block_size}",
            "U4": "exact fixed-marginal swap surrogate preserving each number total frequency and six numbers per draw",
            "U5": "fitted first-order conditional inclusion generator",
            "U6": "adversarial controls: null, persistent bias, regime switch, repeated motif",
        },
        "seeds_policy": "single master PCG64 seed fixed execution order",
        "monte_carlo_error_policy": "add-one empirical p-value; null std and replication count reported",
        "causal_claim": False,
    }


def build_atlas(draws, contests, replications=DEFAULT_REPLICATIONS, seed=DEFAULT_SEED, block_size=25):
    a = _v(draws)
    contests = np.asarray(contests, int)
    if len(a) != len(contests):
        raise ValueError("contests length mismatch")
    rng = np.random.default_rng(seed)
    obs = _stat(a)
    vals = {u: {k: [] for k in obs} for u in ("U0", "U1", "U2", "U3", "U4", "U5")}
    u4_masks = prepare_u4_marginals(a)
    u5_transition, u5_base = prepare_u5_dynamic(a)
    blocks = [a[i : i + block_size] for i in range(0, len(a), block_size)]
    for _ in range(replications):
        label_perm = rng.permutation(NUMBERS)
        label_map = np.empty(61, int)
        label_map[1:] = label_perm
        us = {
            "U0": u0_uniform_iid(len(a), rng),
            "U1": a[rng.permutation(len(a))].copy(),
            "U2": np.sort(label_map[a], axis=1),
            "U3": np.vstack([blocks[i] for i in rng.permutation(len(blocks))]),
            "U4": u4_marginals_preserved(a, rng, prepared_masks=u4_masks),
            "U5": u5_fitted_dynamic(a, rng, transition_weights=u5_transition, base_marginals=u5_base),
        }
        for name, surrogate in us.items():
            st = _stat(surrogate)
            for key, value in st.items():
                vals[name][key].append(float(value))
    comps = {name: {key: _compare(obs[key], values) for key, values in metrics.items()} for name, metrics in vals.items()}
    u6 = {name: _stat(s) for name, s in u6_adversarial_controls(len(a), rng).items()}
    return {
        "schema": SCHEMA_ATLAS,
        "contest_min": int(contests.min()),
        "contest_max": int(contests.max()),
        "n_draws": int(len(a)),
        "observed": atlas_descriptors(a),
        "windows": _windows(a),
        "null_comparisons": comps,
        "u6_controls": u6,
        "interpretation_guardrail": "diagnostic cartography only; significance does not imply prospective predictability or determinism",
    }


def write_program_artifacts(data_path, manifest_path, atlas_path, replications=DEFAULT_REPLICATIONS, seed=DEFAULT_SEED, expected_max_contest=None):
    data_path = Path(data_path)
    draws, contests = load_draws(data_path)
    if expected_max_contest is not None and int(contests.max()) > int(expected_max_contest):
        raise ValueError("future contest detected beyond expected cutoff")
    manifest = build_null_manifest(draws, replications, seed)
    dh = sha256_file(data_path)
    manifest.update({"data_file": data_path.name, "data_sha256": dh, "cutoff_contest": int(contests.max())})
    atlas = build_atlas(draws, contests, replications, seed)
    atlas.update({"data_file": data_path.name, "data_sha256": dh, "null_manifest_schema": SCHEMA_NULL, "seed": int(seed), "replications": int(replications)})
    Path(manifest_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(atlas_path).write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest, atlas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--manifest", default="SMART_NULL_UNIVERSE_MANIFEST.json")
    ap.add_argument("--atlas", default="SMART_RANDOMNESS_ATLAS.json")
    ap.add_argument("--replications", type=int, default=DEFAULT_REPLICATIONS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--expected-max-contest", type=int, required=True)
    a = ap.parse_args()
    m, r = write_program_artifacts(a.data, a.manifest, a.atlas, a.replications, a.seed, a.expected_max_contest)
    print(json.dumps({"manifest": m["schema"], "atlas": r["schema"], "cutoff": r["contest_max"], "replications": r["replications"]}))


if __name__ == "__main__":
    main()

"""Versioned native Frontier signal path: research only, never a production freeze."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

import smart_v2_engine as engine
from smart_frontier_signal_lab import CANDIDATES, FrontierState, sha256_file
from smart_bounded_online_learning import BoundedOnlineLearningGuard

SIGNAL_SCHEMA = "SMART_NATIVE_SIGNAL_CONTRIBUTION_V1"
WEIGHT_SCHEMA = "SMART_NATIVE_RESEARCH_WEIGHT_SNAPSHOT_V1"
ABLAT_SCHEMA = "SMART_NATIVE_RESEARCH_ABLATION_V1"
ADJ_SCHEMA = "SMART_NATIVE_REPLAY_ADJUDICATION_V1"
RESEARCH_ONLY = True
ALL_NUMBERS = tuple(str(i) for i in range(1, 61))
SOURCE_FILE = Path(__file__).resolve().parent / "smart_frontier_signal_lab.py"

NATIVE_ALIAS_TO_PRODUCER = {
    "aeon": "frontier_gap_hazard",
    "regime-detection": "frontier_transition_markov",
    "networkx": "frontier_cooccurrence_graph",
    "statsmodels": "frontier_weekday_bayes",
    "time-series-forecasting": "frontier_recent_lift",
}


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def canonical_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def hash_document(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("sha256", None)
    result["sha256"] = canonical_hash(result)
    return result


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = val
    return result


def strict_json_loads(raw: str) -> Any:
    def bad_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON token: {value}")
    return json.loads(raw, object_pairs_hook=_reject_duplicate,
                      parse_constant=bad_constant)


def _check_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} requires int, not bool/coercion")
    if value < 1:
        raise ValueError(f"{label} must be positive")
    return value


def _check_scores(scores: Any) -> dict[str, float]:
    if not isinstance(scores, dict) or set(scores) != set(ALL_NUMBERS) or len(scores) != 60:
        raise ValueError("exactly 60 unique string-number score keys required")
    clean = {}
    for name in ALL_NUMBERS:
        value = scores[name]
        if type(value) not in (int, float):
            raise TypeError(f"score {name} must be a real number, not bool/string")
        if not math.isfinite(value) or abs(value) > 1e6:
            raise ValueError(f"score {name} must be finite and bounded")
        clean[name] = float(value)
    return clean


def _approved_local(path: Path) -> Path:
    """Reject path escapes; on PC Casa enforce the exclusive physical development root."""
    observed = Path(path).resolve()
    if os.name == "nt" and platform.node().casefold() == "desktop-jns08pu":
        allowed = Path("C:/New Projet/SMART-MEGA-V6-CANONICAL").resolve()
        if not observed.is_relative_to(allowed):
            raise ValueError("BLOCKED_INVALID_LOCAL_ROOT: outside authorized physical root")
    return observed


def make_contribution(
    producer_id: str, scores: dict[str, float], *,
    data_path: Path, target_contest: int, epoch_id: str,
    source_aliases: Iterable[str] = (),
) -> dict[str, Any]:
    if producer_id not in CANDIDATES:
        raise ValueError("unregistered native producer")
    target = _check_int(target_contest, "target_contest")
    if not isinstance(epoch_id, str) or not epoch_id.strip():
        raise ValueError("epoch_id must be nonempty")
    dataset = _approved_local(Path(data_path))
    if not dataset.is_file():
        raise FileNotFoundError(dataset)
    clean = _check_scores(scores)
    aliases = list(source_aliases)
    if any(not isinstance(alias, str) or not alias for alias in aliases):
        raise ValueError("invalid aliases")
    if len(set(aliases)) != len(aliases):
        raise ValueError("duplicate aliases")
    if any(NATIVE_ALIAS_TO_PRODUCER.get(alias) != producer_id for alias in aliases):
        raise ValueError("source alias is not bound to native producer")
    result = {
        "schema": SIGNAL_SCHEMA,
        "target_contest": target,
        "cutoff_contest": target - 1,
        "epoch_id": epoch_id,
        "producer_id": producer_id,
        "feature_family": CANDIDATES[producer_id],
        "algorithm_sha256": sha256_file(SOURCE_FILE),
        "dataset_sha256": sha256_file(dataset),
        "source_skill_aliases": sorted(aliases),
        "score_kind": "RELATIVE_SIGNAL_NOT_CALIBRATED_PROBABILITY",
        "score_semantics": "finite relative score, bounded [-1e6,1e6], not probability",
        "scores_by_number": clean,
        "quality": {"data_coverage": 1.0, "missing_count": 0},
        "pre_result_only": True,
        "target_result_used": False,
        "production_authority": False,
        "research_only": True,
    }
    return hash_document(result)


def validate_contribution(value: dict[str, Any], data_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("contribution must be an object")
    keys = {"schema", "target_contest", "cutoff_contest", "epoch_id",
            "producer_id", "feature_family", "algorithm_sha256",
            "dataset_sha256", "source_skill_aliases", "score_kind",
            "score_semantics", "scores_by_number", "quality",
            "pre_result_only", "target_result_used", "production_authority",
            "research_only", "sha256"}
    if set(value) != keys:
        raise ValueError("signal contract has missing or extra fields")
    if value["schema"] != SIGNAL_SCHEMA or value["producer_id"] not in CANDIDATES:
        raise ValueError("unknown signal schema/producer")
    target = _check_int(value["target_contest"], "target_contest")
    if type(value["cutoff_contest"]) is not int or value["cutoff_contest"] != target - 1:
        raise ValueError("invalid causal cutoff")
    if not isinstance(value["epoch_id"], str) or not value["epoch_id"].strip():
        raise ValueError("invalid epoch")
    if value["feature_family"] != CANDIDATES[value["producer_id"]]:
        raise ValueError("incorrect signal family")
    if (value["score_kind"] != "RELATIVE_SIGNAL_NOT_CALIBRATED_PROBABILITY"
            or value["score_semantics"] != "finite relative score, bounded [-1e6,1e6], not probability"):
        raise ValueError("uncalibrated scores have wrong declared semantics")
    if (value["pre_result_only"] is not True or value["target_result_used"] is not False
            or value["production_authority"] is not False or value["research_only"] is not True):
        raise ValueError("result or production authority leaked into research")
    if value["algorithm_sha256"] != sha256_file(SOURCE_FILE):
        raise ValueError("algorithm SHA mismatch")
    dataset_sha = value["dataset_sha256"]
    if (not isinstance(dataset_sha, str) or len(dataset_sha) != 64
            or any(ch not in "0123456789abcdef" for ch in dataset_sha)):
        raise ValueError("dataset SHA malformed")
    if data_path is not None and dataset_sha != sha256_file(_approved_local(Path(data_path))):
        raise ValueError("dataset SHA mismatch")
    aliases = value["source_skill_aliases"]
    if not isinstance(aliases, list) or any(not isinstance(x, str) or not x for x in aliases):
        raise ValueError("invalid aliases")
    if sorted(set(aliases)) != aliases:
        raise ValueError("aliases must be sorted and unique")
    if any(NATIVE_ALIAS_TO_PRODUCER.get(alias) != value["producer_id"] for alias in aliases):
        raise ValueError("source alias does not belong to declared producer")
    if value["quality"] != {"data_coverage": 1.0, "missing_count": 0}:
        raise ValueError("quality contract invalid")
    _check_scores(value["scores_by_number"])
    if not isinstance(value["sha256"], str) or value["sha256"] != canonical_hash({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("contribution SHA mismatch")
    return value


def produce_contributions(
    data_path: Path, *, target_contest: int, epoch_id: str,
    target_date: str | None = None, date_source_sha256: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Run actual FrontierState over a physical N-1 snapshot, never full future history."""
    _check_int(target_contest, "target_contest")
    path = _approved_local(Path(data_path))
    draws, contests = engine.load_draws(path)
    if len(contests) < 2 or int(contests[-1]) != target_contest - 1:
        raise ValueError("cutoff: last available contest must equal target-1")
    if (len(np.unique(contests)) != len(contests) or np.any(np.diff(contests) != 1)
            or int(contests[-1]) >= target_contest):
        raise ValueError("cutoff: duplicate, missing or future contests")
    frame = pd.read_excel(path)
    if "Data do Sorteio" not in frame:
        raise ValueError("historical date column absent")
    if len(frame) != len(draws):
        raise ValueError("historical dates/draws length mismatch")
    dates = pd.to_datetime(frame["Data do Sorteio"], dayfirst=True,
                           format="mixed", errors="raise")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError("historical date missing or duplicated")
    if bool((dates.diff().iloc[1:] < pd.Timedelta(0)).any()):
        raise ValueError("historical dates out of order")
    # A date can influence the calendar producer only with a bound verification source.
    if target_date is not None and (
        not isinstance(date_source_sha256, str) or len(date_source_sha256) != 64
        or any(c not in "0123456789abcdef" for c in date_source_sha256)
    ):
        raise ValueError("target calendar date requires verified source hash")
    if target_date is None and date_source_sha256 is not None:
        raise ValueError("calendar source with no target date")
    weekday = None if target_date is None else pd.to_datetime(
        target_date, dayfirst=True, errors="raise").weekday()
    state = FrontierState()
    for pos, draw in enumerate(draws):
        state.update(np.asarray(draw, dtype=int), int(dates.iloc[pos].weekday()))
    raw = state.predict(weekday).document()
    return {
        name: make_contribution(
            name, row["scores"], data_path=path,
            target_contest=target_contest, epoch_id=epoch_id,
            source_aliases=tuple(
            alias for alias, bound_producer in NATIVE_ALIAS_TO_PRODUCER.items()
            if bound_producer == name
        ),
        )
        for name, row in sorted(raw.items())
    }


def _normalized(value: dict[str, Any]) -> np.ndarray:
    raw = np.asarray([value["scores_by_number"][k] for k in ALL_NUMBERS], dtype=float)
    hi, lo = float(raw.max()), float(raw.min())
    if hi - lo <= 1e-12:
        return np.zeros(60, dtype=float)
    return (raw - lo) / (hi - lo)


def build_research_challenger(
    contributions: Iterable[dict[str, Any]],
    weights: dict[str, float],
) -> dict[str, Any]:
    values = list(contributions)
    if not values:
        raise ValueError("at least one native contribution required")
    ids = [c.get("producer_id") for c in values]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate producer / alias must never add a second vote")
    if set(ids) != set(weights):
        raise ValueError("research weights must match producers exactly")
    for item in values:
        validate_contribution(item)
    context = {(c["target_contest"], c["cutoff_contest"], c["epoch_id"], c["dataset_sha256"])
               for c in values}
    if len(context) != 1:
        raise ValueError("different epochs/cutoffs/datasets cannot be aggregated")
    target, cutoff, epoch, dataset_hash = next(iter(context))
    if type(target) is not int or type(cutoff) is not int or cutoff != target - 1:
        raise ValueError("invalid causal cutoff")
    clean_weights = {}
    for name in ids:
        w = weights[name]
        if type(w) not in (int, float) or not math.isfinite(w) or not 0 <= w <= 1:
            raise ValueError("research weight invalid")
        clean_weights[name] = float(w)
    # Different names for the same *effective* signal cannot earn two votes.
    # Compare normalized numeric vectors (not only raw score hashes) so that a
    # rescaled alias is also rejected. Zero-weight or flat vectors carry no
    # influence and do not create false redundancy failures.
    independent_vectors: list[tuple[str, np.ndarray]] = []
    for item in sorted(values, key=lambda c: c["producer_id"]):
        name = item["producer_id"]
        if clean_weights[name] <= 0.0:
            continue
        normalized_vector = _normalized(item)
        if float(np.ptp(normalized_vector)) <= 1e-12:
            continue
        for existing_name, existing_vector in independent_vectors:
            # An affine rescaling can differ by a few IEEE-754 ULPs;
            # comparing raw bytes misses an otherwise exact duplicate.
            if bool(np.allclose(normalized_vector, existing_vector, rtol=0.0, atol=1e-12)):
                raise ValueError(
                    "redundant duplicate normalized signal vectors across producers: "
                    f"{existing_name} and {name}"
                )
        independent_vectors.append((name, normalized_vector))
    aggregate = np.full(60, 0.1, dtype=float)
    ledger = {}
    for item in sorted(values, key=lambda c: c["producer_id"]):
        name = item["producer_id"]
        normalized = _normalized(item)
        w = clean_weights[name]
        aggregate += w * normalized
        ledger[name] = {
            "signal_sha256": item["sha256"],
            "family": item["feature_family"],
            "quality_factor": 1.0,
            "redundancy_penalty": 1.0,  # explicit neutral factor, no unsupported OOS claims
            "context_factor": 1.0,
            "estimated_oos_utility": None,
            "drift_state": "NOT_MEASURED",
            "weight_candidate": w,
            "weight_effective": w,
            "normalized_scores_by_number": {str(i + 1): float(normalized[i]) for i in range(60)},
        }
    ranking = sorted(range(1, 61), key=lambda n: (-float(aggregate[n - 1]), n))
    return hash_document({
        "schema": WEIGHT_SCHEMA,
        "research_only": True, "production_authority": False,
        "target_result_used": False,
        "target_contest": target, "cutoff_contest": cutoff,
        "epoch_id": epoch, "dataset_sha256": dataset_hash,
        "calibration_status": "UNCALIBRATED_RESEARCH_SCORES",
        "aggregate_formula": "uniform_0.1 + sum(predeclared_weight * per_vector_minmax)",
        "weight_eligibility": "RESEARCH_ONLY_NO_PRODUCTION_PROMOTION",
        "signals": ledger,
        "scores_by_number": {str(i + 1): float(aggregate[i]) for i in range(60)},
        "ranking60": ranking, "top6": sorted(ranking[:6]),
    })


def ablate_research(
    contributions: Iterable[dict[str, Any]],
    weights: dict[str, float], *,
    full: dict[str, Any] | None = None,
    champion_top6: list[int] | None = None,
) -> dict[str, Any]:
    values = list(contributions)
    original = build_research_challenger(values, weights)
    if full is not None and full != original:
        raise ValueError("full report mismatches immutable inputs")
    full = original
    def compare(candidate: dict[str, Any]) -> dict[str, Any]:
        lhs = full["scores_by_number"]
        rhs = candidate["scores_by_number"]
        return {
            "max_abs_delta": max(abs(lhs[k] - rhs[k]) for k in ALL_NUMBERS),
            "mean_abs_delta": sum(abs(lhs[k] - rhs[k]) for k in ALL_NUMBERS) / 60,
            "top6_changed": candidate["top6"] != full["top6"],
            "top6_overlap": len(set(candidate["top6"]) & set(full["top6"])),
            "scores60_sha256": candidate["sha256"],
        }
    by_producer = {}
    for name in sorted(weights):
        reduced = dict(weights)
        reduced[name] = 0.0
        by_producer[name] = compare(build_research_challenger(values, reduced))
    by_family = {}
    for family in sorted({c["feature_family"] for c in values}):
        reduced = dict(weights)
        for c in values:
            if c["feature_family"] == family:
                reduced[c["producer_id"]] = 0.0
        by_family[family] = compare(build_research_challenger(values, reduced))
    neutral = build_research_challenger(values, {k: 0.0 for k in weights})
    if champion_top6 is not None and (
        type(champion_top6) is not list or len(champion_top6) != 6
        or len(set(champion_top6)) != 6
        or any(type(n) is not int or not 1 <= n <= 60 for n in champion_top6)
    ):
        raise ValueError("invalid champion Top-6")
    return hash_document({
        "schema": ABLAT_SCHEMA, "research_only": True,
        "production_authority": False, "target_result_used": False,
        "full_sha256": full["sha256"],
        "uniform": compare(neutral),
        "by_producer": by_producer,
        "by_family": by_family,
        "champion_top6": champion_top6 if champion_top6 is not None else "NOT_MEASURED",
        "champion_overlap": len(set(champion_top6) & set(full["top6"]))
                            if champion_top6 is not None else "NOT_MEASURED",
        "effect_on_decision_only": True,
        "predictive_gain_proven": False,
    })


def adjudicate_replay(
    freeze: dict[str, Any], result: dict[str, Any], ledger_dir: Path,
    *, source_path: Path | None = None,
) -> dict[str, Any]:
    """Two-stage historical replay: only this method can see the result."""
    if freeze.get("sha256") != canonical_hash({k: v for k, v in freeze.items() if k != "sha256"}):
        raise ValueError("freeze hash invalid")
    if (freeze.get("schema") != WEIGHT_SCHEMA or freeze.get("research_only") is not True
            or freeze.get("target_result_used") is not False
            or freeze.get("production_authority") is not False):
        raise ValueError("not an immutable pre-result research freeze")
    if set(result) != {"contest", "numbers", "source_sha256", "source_kind"}:
        raise ValueError("result source contract invalid")
    if type(result["contest"]) is not int or result["contest"] != freeze["target_contest"]:
        raise ValueError("adjudication target mismatch")
    numbers = result["numbers"]
    if (type(numbers) is not list or len(numbers) != 6
            or any(type(x) is not int or x < 1 or x > 60 for x in numbers)
            or len(set(numbers)) != 6):
        raise ValueError("result must be six distinct verified integers")
    source = result["source_sha256"]
    if not isinstance(source, str) or len(source) != 64 or any(c not in "0123456789abcdef" for c in source):
        raise ValueError("result source hash invalid")
    if result["source_kind"] != "HISTORICAL_REPLAY":
        raise ValueError("only separately labeled replay accepted; not live prospective proof")
    verified_source = False
    if source_path is not None:
        physical_source = _approved_local(Path(source_path))
        if sha256_file(physical_source) != source:
            raise ValueError("historical replay source dataset hash mismatch")
        source_draws, source_contests = engine.load_draws(physical_source)
        candidates = np.where(source_contests == result["contest"])[0]
        if len(candidates) != 1 or set(source_draws[int(candidates[0])].tolist()) != set(numbers):
            raise ValueError("historical replay result is not bound to source data")
        verified_source = True
    win = set(numbers)
    def hit(six: list[int]) -> int:
        return len(set(six) & win)
    rewards = {name: hit(sorted(
        range(1, 61), key=lambda n: (-row["normalized_scores_by_number"][str(n)], n)
    )[:6]) for name, row in freeze["signals"].items()}
    # The existing bounded guard is reused for a *proposal*; promotion remains separate.
    guard = BoundedOnlineLearningGuard(eta=0.05, baseline_hits=0.6)
    before = {name: 0.0 for name in sorted(freeze["signals"])}
    proposed, audit = guard.update(before, rewards)
    payoff = {
        "schema": ADJ_SCHEMA, "target_contest": freeze["target_contest"],
        "freeze_sha256": freeze["sha256"],
        "research_only": True, "historical_replay": True,
        "prospective_advantage_proven": False,
        "result_source_verified": verified_source,
        "result_sha256": canonical_hash(result), "result_source_sha256": source,
        "result_numbers": sorted(numbers),
        "challenger_hits": hit(freeze["top6"]),
        "per_producer_hits": rewards,
        "learning_update": {
            "from_epoch": freeze["epoch_id"],
            "to_next_epoch": f"AFTER-{freeze['target_contest']}",
            "proposed_centered_logits": proposed,
            "bounded_guard_audit": audit,
            "weights_effective_next": {name: row["weight_effective"] for name, row in freeze["signals"].items()},
            "promotion_authorized": False,
        },
    }
    receipt = hash_document(payoff)
    folder = _approved_local(Path(ledger_dir))
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"REPLAY_{freeze['target_contest']}_{freeze['sha256']}.json"
    if destination.exists():
        observed = strict_json_loads(destination.read_text(encoding="utf-8"))
        if observed != receipt:
            raise ValueError("conflict: replay already adjudicated with different result")
        return observed
    # Publish an fsync'd complete temp inode with an atomic create-if-absent link.
    # os.replace() is unsafe here: two concurrent writers can both pass exists()
    # and the second can silently overwrite the first receipt.
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=folder,
        prefix=f".{destination.name}.", suffix=".tmp", delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        try:
            os.link(temporary, destination)
        except FileExistsError:
            existing = strict_json_loads(destination.read_text(encoding="utf-8"))
            if existing != receipt:
                raise ValueError("conflict: replay already adjudicated with different result")
            return existing
    finally:
        temporary.unlink(missing_ok=True)
    return receipt


# Preregistered experimental coefficients: fixed without observing the held-out result.
# Never infer production eligibility or OOS utility from these research-only values.
DEFAULT_RESEARCH_WEIGHTS = {
    "frontier_gap_hazard": 0.05,
    "frontier_transition_markov": 0.0,
    "frontier_cooccurrence_graph": 0.0,
    "frontier_weekday_bayes": 0.0,
    "frontier_recent_lift": 0.1,
}


def build_native_pre_freeze_package(
    data_path: Path, *, target_contest: int, epoch_id: str,
) -> dict[str, Any]:
    """Calculate five true Frontier contributions from *only* the physical N-1 snapshot."""
    contributions = produce_contributions(
        data_path, target_contest=target_contest, epoch_id=epoch_id
    )
    ordered = [contributions[name] for name in sorted(contributions)]
    for contribution in ordered:
        validate_contribution(contribution, data_path)
    challenger = build_research_challenger(ordered, DEFAULT_RESEARCH_WEIGHTS)
    ablation = ablate_research(ordered, DEFAULT_RESEARCH_WEIGHTS, full=challenger)
    return hash_document({
        "schema": "SMART_NATIVE_PRE_FREEZE_RESEARCH_PACKAGE_V1",
        "target_contest": target_contest, "cutoff_contest": target_contest - 1,
        "epoch_id": epoch_id, "data_sha256": sha256_file(_approved_local(Path(data_path))),
        "weights_preregistered": DEFAULT_RESEARCH_WEIGHTS,
        "contributions": contributions,
        "challenger": challenger,
        "ablation": ablation,
        "result_used": False, "production_authority": False,
        "research_only": True, "predictive_advantage_proven": False,
    })


def next_epoch_research_weights(
    previous_freeze: dict[str, Any],
    adjudication: dict[str, Any],
    *, next_target_contest: int, research_authorized: bool,
) -> dict[str, Any]:
    """Consume an adjudicated result for N+1 in research ONLY; never change N."""
    if research_authorized is not True:
        raise PermissionError("explicit research next-epoch authorization required")
    _check_int(next_target_contest, "next_target_contest")
    if next_target_contest != previous_freeze.get("target_contest", -2) + 1:
        raise ValueError("next epoch must be exactly one contest after adjudication")
    for value, label in ((previous_freeze, "freeze"), (adjudication, "adjudication")):
        if (not isinstance(value, dict) or not isinstance(value.get("sha256"), str)
                or value["sha256"] != canonical_hash({k: v for k, v in value.items() if k != "sha256"})):
            raise ValueError(f"invalid {label} hash")
    if (previous_freeze.get("schema") != WEIGHT_SCHEMA
            or previous_freeze.get("research_only") is not True
            or previous_freeze.get("production_authority") is not False
            or previous_freeze.get("target_result_used") is not False):
        raise ValueError("previous freeze lacked research-only pre-result boundary")
    if (adjudication.get("schema") != ADJ_SCHEMA
            or adjudication.get("historical_replay") is not True
            or adjudication.get("research_only") is not True
            or adjudication.get("result_source_verified") is not True
            or adjudication.get("target_contest") != previous_freeze["target_contest"]
            or adjudication.get("freeze_sha256") != previous_freeze["sha256"]):
        raise ValueError("no verified result bound to the previous freeze")
    update = adjudication.get("learning_update")
    if (not isinstance(update, dict)
            or update.get("from_epoch") != previous_freeze["epoch_id"]
            or update.get("to_next_epoch") != f"AFTER-{previous_freeze['target_contest']}"
            or update.get("promotion_authorized") is not False):
        raise ValueError("invalid learning update or promotion authority")
    before = {name: row["weight_effective"]
              for name, row in previous_freeze["signals"].items()}
    logits = update.get("proposed_centered_logits")
    if not isinstance(logits, dict) or set(logits) != set(before):
        raise ValueError("learning logits do not match producer identity")
    if update.get("weights_effective_next") != before:
        raise ValueError("learning receipt disagrees with frozen input weights")
    for name, logit in logits.items():
        if type(logit) not in (int, float) or not math.isfinite(logit) or abs(logit) > 100:
            raise ValueError(f"unsafe learning logit {name}")
    active = [name for name in sorted(before) if before[name] > 0]
    if not active or any(type(before[n]) not in (int, float)
                         or not math.isfinite(before[n]) or not 0 <= before[n] <= 1 for n in before):
        raise ValueError("invalid frozen research weights")
    budget = float(sum(before.values()))
    if budget > 0.15 + 1e-12:
        raise ValueError("research-only global influence budget exceeded")
    raw = {name: before[name] * math.exp(float(logits[name])) for name in active}
    total = float(sum(raw.values()))
    if not math.isfinite(total) or total <= 0:
        raise ValueError("new research weights degenerate")
    proposed = {name: (float(budget * raw[name] / total) if name in active else 0.0)
                for name in sorted(before)}
    if max(proposed.values()) > 0.15 + 1e-12:
        raise ValueError("bounded research weight exceeded")
    return hash_document({
        "schema": "SMART_NATIVE_RESEARCH_NEXT_EPOCH_WEIGHTS_V1",
        "previous_target_contest": previous_freeze["target_contest"],
        "next_target_contest": next_target_contest,
        "previous_freeze_sha256": previous_freeze["sha256"],
        "adjudication_sha256": adjudication["sha256"],
        "weights_before": before,
        "weights_effective_next_research": proposed,
        "global_research_budget": budget,
        "only_previously_active_producers_can_receive_weight": True,
        "learning_evidence_source": "PREVIOUS_CONTEST_VERIFIED_HISTORICAL_REPLAY",
        "research_only": True, "production_authority": False,
        "prospective_advantage_proven": False,
    })

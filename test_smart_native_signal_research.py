"""TDD: independent native research path. Does not authorize Champion mutation."""
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from smart_native_signal_research import (
    ablate_research,
    build_research_challenger,
    make_contribution,
    produce_contributions,
    strict_json_loads,
    validate_contribution,
    adjudicate_replay,
)

NAMES = ["frontier_gap_hazard", "frontier_transition_markov",
         "frontier_cooccurrence_graph", "frontier_weekday_bayes",
         "frontier_recent_lift"]


def example(tmp_path, *, name=NAMES[0], scores=None):
    dataset = tmp_path / "cutoff.json"
    dataset.write_bytes(b"immutable historical snapshot")
    if scores is None:
        scores = {str(i): float(i / 60) for i in range(1, 61)}
    c = make_contribution(name, scores, data_path=dataset,
                          target_contest=3082, epoch_id="REPLAY-3082",
                          source_aliases=("aeon",))
    return c, dataset


@pytest.mark.parametrize("invalid", [
    lambda c: c["scores_by_number"].pop("60"),
    lambda c: c["scores_by_number"].update({"61": 0.4}),
    lambda c: c["scores_by_number"].update({"20": "0.3"}),
    lambda c: c["scores_by_number"].update({"20": True}),
    lambda c: c["scores_by_number"].update({"20": float("nan")}),
    lambda c: c.update({"cutoff_contest": 3082}),
    lambda c: c.update({"target_result_used": True}),
    lambda c: c.update({"production_authority": True}),
    lambda c: c.update({"dataset_sha256": "0"*64}),
    lambda c: c.update({"algorithm_sha256": "invalid"}),
])
def test_fail_closed_invalid_signal_contract(tmp_path, invalid):
    value, dataset = example(tmp_path)
    invalid(value)
    with pytest.raises((ValueError, TypeError)):
        validate_contribution(value, dataset)


def test_canonical_json_detects_duplicate_keys_and_nan():
    with pytest.raises(ValueError, match="duplicate"):
        strict_json_loads('{"1": 1, "1": 2}')
    with pytest.raises(ValueError):
        strict_json_loads('{"1": NaN}')


def test_contribution_reproducible_and_bound_to_exact_file(tmp_path):
    c, data = example(tmp_path)
    assert validate_contribution(c, data) == c
    assert make_contribution(c["producer_id"], c["scores_by_number"],
                             data_path=data, target_contest=3082,
                             epoch_id="REPLAY-3082",
                             source_aliases=("aeon",)) == c
    data.write_bytes(b"changed")
    with pytest.raises(ValueError, match="dataset"):
        validate_contribution(c, data)


def test_research_consumer_propagates_real_numeric_effect_and_deduplicates(tmp_path):
    a, data = example(tmp_path)
    other = copy.deepcopy(a)
    other["source_skill_aliases"] = ["another-alias"]
    # Aliases must never multiply a producer's independent votes.
    weights = {a["producer_id"]: 0.2}
    result = build_research_challenger([a], weights)
    with pytest.raises(ValueError, match="duplicate"):
        build_research_challenger([a, other], weights)
    assert result["research_only"] is True
    assert result["production_authority"] is False
    assert len(result["ranking60"]) == 60
    assert len(result["top6"]) == 6
    assert result["scores_by_number"]["60"] > result["scores_by_number"]["1"]
    assert result == build_research_challenger([a], weights)
    ablation = ablate_research([a], weights, full=result)
    assert ablation["by_producer"][a["producer_id"]]["max_abs_delta"] > 0


def test_zero_weight_and_flat_signal_are_neutral(tmp_path):
    flat, _ = example(tmp_path, scores={str(i): 0.0 for i in range(1, 61)})
    result = build_research_challenger([flat], {flat["producer_id"]: 0.3})
    assert len(set(result["scores_by_number"].values())) == 1
    result_zero = build_research_challenger([flat], {flat["producer_id"]: 0.0})
    assert result_zero["scores_by_number"] == result["scores_by_number"]


def test_real_data_producers_without_calendar_proof(root_data):
    dataset, target = root_data
    rows = produce_contributions(dataset, target_contest=target,
                                 epoch_id=f"REPLAY-{target}")
    assert set(rows) == set(NAMES)
    assert all(len(row["scores_by_number"]) == 60 for row in rows.values())
    assert all(validate_contribution(row, dataset) == row for row in rows.values())
    assert len(set(rows.keys())) == 5
    assert max(rows["frontier_weekday_bayes"]["scores_by_number"].values()) == 0.0
    assert rows == produce_contributions(dataset, target_contest=target,
                                         epoch_id=f"REPLAY-{target}")


@pytest.fixture(scope="module")
def root_data():
    from smart_v2_engine import load_draws
    base = Path(__file__).resolve().parent / "Mega-Sena.xlsx"
    _draws, contests = load_draws(base)
    return base, int(contests[-1]) + 1


def test_real_data_rejects_future_result(root_data):
    path, target = root_data
    with pytest.raises(ValueError, match="cutoff"):
        produce_contributions(path, target_contest=target - 1,
                              epoch_id=f"REPLAY-{target-1}")


def test_controlled_signal_changes_top6(tmp_path):
    spike = {str(i): (10.0 if i == 60 else 0.0) for i in range(1, 61)}
    a, data = example(tmp_path, scores=spike)
    out = build_research_challenger([a], {a["producer_id"]: 1.0})
    assert 60 in out["top6"]


def test_adjudication_idempotent_freeze_immutable(tmp_path):
    a, data = example(tmp_path)
    frozen = build_research_challenger([a], {a["producer_id"]: 0.2})
    frozen["epoch_id"] = a["epoch_id"]
    frozen["target_contest"] = a["target_contest"]
    frozen["cutoff_contest"] = a["cutoff_contest"]
    before = copy.deepcopy(frozen)
    result = {"contest": 3082, "numbers": [1, 2, 3, 4, 5, 6],
              "source_sha256": hashlib.sha256(b"authenticated replay draw").hexdigest(),
              "source_kind": "HISTORICAL_REPLAY"}
    first = adjudicate_replay(frozen, result, tmp_path / "ledger")
    second = adjudicate_replay(frozen, result, tmp_path / "ledger")
    assert first == second
    assert frozen == before
    assert first["target_contest"] == 3082
    assert first["research_only"] is True
    with pytest.raises(ValueError, match="conflict"):
        adulterated = dict(result, numbers=[7, 8, 9, 10, 11, 12])
        adjudicate_replay(frozen, adulterated, tmp_path / "ledger")


def test_capability_catalog_accounts_for_aliases_and_quarantine():
    from smart_native_signal_catalog import classify_capabilities
    from pathlib import Path
    root = Path(__file__).resolve().parent
    catalogue = classify_capabilities(root)
    assert catalogue["counts"]["registered"] == 41
    assert catalogue["counts"]["probe_adapters"] == 37
    assert catalogue["counts"]["quarantined"] == 4
    assert catalogue["counts"]["native_producer_bindings"] == 5
    assert sum(x["role"] == "SIGNAL_PRODUCER" for x in catalogue["capabilities"]) == 5
    assert not any(x["direct_external_code_executed"] for x in catalogue["capabilities"])


def test_physical_pc_casa_root_preflight_fail_closed(monkeypatch):
    import os
    import platform
    from pathlib import Path
    import smart_native_signal_research as native
    if os.name != "nt" or platform.node().casefold() != "desktop-jns08pu":
        pytest.skip("T21 requires the verified physical PC Casa")
    root = Path(r"C:\New Projet\SMART-MEGA-V6-CANONICAL").resolve()
    assert native._approved_local(root / "_worktrees" / "native-signals-G00-G08") == (root / "_worktrees" / "native-signals-G00-G08").resolve()
    for blocked in [
        Path(r"C:\Windows\Temp\smart-native"),
        Path(r"C:\New Projet\SMART-MEGA-V6-CANONICAL-copy"),
        root / ".." / "SMART-MEGA-V6-CANONICAL-copy",
    ]:
        with pytest.raises(ValueError, match="BLOCKED_INVALID_LOCAL_ROOT"):
            native._approved_local(blocked)
    monkeypatch.setenv("SMART_CANONICAL_ROOT", r"C:\Windows\Temp")
    with pytest.raises(ValueError, match="BLOCKED_INVALID_LOCAL_ROOT"):
        native._approved_local(Path(r"C:\Windows\Temp"))


def test_native_pre_freeze_package_consumes_real_signals(root_data):
    from smart_native_signal_research import build_native_pre_freeze_package
    dataset, target = root_data
    package = build_native_pre_freeze_package(dataset, target_contest=target, epoch_id=f"REPLAY-{target}")
    assert package["result_used"] is False
    assert package["production_authority"] is False
    assert len(package["contributions"]) == 5
    assert package["challenger"]["research_only"] is True
    assert package["ablation"]["predictive_gain_proven"] is False
    assert package["sha256"] == hashlib.sha256(json.dumps({k: v for k, v in package.items() if k != "sha256"}, sort_keys=True, ensure_ascii=False, separators=(",",":"), allow_nan=False).encode()).hexdigest()



def test_consumer_rejects_rehashed_forged_source_and_schema(tmp_path):
    """A self-recomputed JSON hash is not sufficient evidence of a real producer."""
    import copy
    from smart_native_signal_research import canonical_hash
    original, _ = example(tmp_path)
    for key, forged in (
        ("algorithm_sha256", "0" * 64),
        ("schema", "FORGED_SCHEMA"),
        ("producer_id", "foreign_unregistered"),
        ("target_result_used", True),
        ("pre_result_only", False),
    ):
        candidate = copy.deepcopy(original)
        candidate[key] = forged
        candidate["sha256"] = canonical_hash({
            k: v for k, v in candidate.items() if k != "sha256"
        })
        with pytest.raises((ValueError, TypeError)):
            build_research_challenger([candidate], {candidate["producer_id"]: 0.1})


def test_t21_exclusive_root_denies_external_and_lookalike_paths(monkeypatch):
    import platform
    from smart_native_signal_research import _approved_local
    if platform.system() != "Windows" or platform.node().casefold() != "desktop-jns08pu":
        pytest.skip("physical PC Casa boundary can only be tested on PC Casa")
    base = Path("C:/New Projet/SMART-MEGA-V6-CANONICAL").resolve()
    good = base / "_worktrees" / "native-signals-G00-G08"
    assert _approved_local(good) == good.resolve()
    for external in (
        Path("C:/Windows/Temp"),
        base.parent / "SMART-MEGA-V6-CANONICAL-OTHER",
        base / ".." / ".." / "Windows",
    ):
        with pytest.raises(ValueError, match="BLOCKED_INVALID_LOCAL_ROOT"):
            _approved_local(external)
    monkeypatch.setenv("SMART_CANONICAL_ROOT", "C:/Windows/Temp")
    with pytest.raises(ValueError, match="BLOCKED_INVALID_LOCAL_ROOT"):
        _approved_local(Path("C:/Windows/Temp"))


def test_real_frontier_provenance_matches_capability_aliases(root_data):
    """Every real Frontier output must carry the methodology alias bound in the catalog."""
    from smart_native_signal_catalog import ALIAS_TO_PRODUCER

    dataset, target = root_data
    signals = produce_contributions(dataset, target_contest=target,
                                    epoch_id=f"REPLAY-{target}")
    for alias, producer_id in sorted(ALIAS_TO_PRODUCER.items()):
        assert signals[producer_id]["source_skill_aliases"] == [alias], (
            producer_id, signals[producer_id]["source_skill_aliases"], alias
        )


def test_rehashed_wrong_skill_alias_is_rejected(tmp_path):
    """A valid hash must not authenticate an alias belonging to another producer."""
    from smart_native_signal_research import canonical_hash

    contribution, dataset = example(tmp_path)
    counterfeit = copy.deepcopy(contribution)
    counterfeit["source_skill_aliases"] = ["statsmodels"]
    counterfeit["sha256"] = canonical_hash({
        key: value for key, value in counterfeit.items() if key != "sha256"
    })
    with pytest.raises(ValueError, match="alias"):
        validate_contribution(counterfeit, dataset)

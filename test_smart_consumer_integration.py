"""Consumer-to-card proof tests use the already immutable 3070 freeze as a fixture."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from smart_consumer_integration import evaluate


@pytest.fixture
def specimen() -> dict:
    root = Path(__file__).resolve().parent
    epoch = next(root.glob("runtime/learning_epochs/operator-3070-*/SMART_3070_PRIMARY_CARD.json")).parent
    card = json.loads((epoch / "SMART_3070_PRIMARY_CARD.json").read_text(encoding="utf-8"))
    return {
        "root": root,
        "target": 3070,
        "epoch_id": card["run_id"],
        "freeze_path": root / card["freeze_file"],
        "portfolio_path": root / card["portfolio_file"],
        "primary_card": card,
        "pre_gate": json.loads((epoch / "PRE_FREEZE_TOTAL_INTEGRATION.json").read_text(encoding="utf-8")),
        "post_gate": json.loads((epoch / "POST_FREEZE_TOTAL_INTEGRATION.json").read_text(encoding="utf-8")),
    }


def test_real_frozen_3070_consumer_chain_passes(specimen):
    result = evaluate(**specimen)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["card_numbers"] == [10, 11, 27, 38, 43, 53]
    assert result["effective_decision_head"] == "champion"
    assert result["challenger_weight_role"] == "SHADOW_UNLESS_EVIDENCE_PROMOTED"
    assert result["predictive_advantage_proven"] is False


def test_altered_primary_card_fails_closed(specimen):
    changed = {**specimen, "primary_card": copy.deepcopy(specimen["primary_card"])}
    changed["primary_card"]["numbers"][0] = 2
    with pytest.raises(RuntimeError, match="six_numbers_exactly_from_selector_and_portfolio"):
        evaluate(**changed)


def test_quarantined_external_claim_fails_closed(specimen):
    changed = {**specimen, "post_gate": copy.deepcopy(specimen["post_gate"])}
    changed["post_gate"]["skill_inventory"][0]["external_skill_source_executed"] = True
    with pytest.raises(RuntimeError, match="external_third_party_code_quarantined"):
        evaluate(**changed)


def test_tampered_challenger_weight_fails_closed(specimen, tmp_path):
    changed = dict(specimen)
    freeze = json.loads(specimen["freeze_path"].read_text(encoding="utf-8"))
    freeze["challenger"]["weights"]["freq25"] = 100.0
    fp = tmp_path / "freeze.json"
    pp = tmp_path / "portfolio.json"
    fp.write_text(json.dumps(freeze), encoding="utf-8")
    shutil.copyfile(specimen["portfolio_path"], pp)
    changed.update(root=tmp_path, freeze_path=fp, portfolio_path=pp)
    with pytest.raises(RuntimeError, match="twelve_valid_challenger_signal_weights"):
        evaluate(**changed)

def _frozen(specimen):
    return json.loads(specimen["freeze_path"].read_text(encoding="utf-8"))


def _replay(specimen, freeze):
    from smart_consumer_integration import _replay
    return _replay(specimen["root"], specimen["target"], specimen["freeze_path"], freeze,
        json.loads(specimen["portfolio_path"].read_text(encoding="utf-8")),
        specimen["primary_card"], (specimen["pre_gate"], specimen["post_gate"]))


def test_raw_signal_tampering_rejected_even_with_recomputed_hash(specimen):
    from smart_consumer_integration import _sha256_json
    freeze = _frozen(specimen)
    row = freeze["challenger"]["raw_signals"]["freq25"]
    row["values"]["1"] += 0.01
    row["values_sha256"] = _sha256_json(row["values"])
    with pytest.raises(RuntimeError, match="raw_signals_recomputed_from_history"):
        _replay(specimen, freeze)


def test_normalized_but_unconsumed_challenger_weights_rejected(specimen):
    freeze = _frozen(specimen)
    weights = freeze["challenger"]["weights"]
    weights["freq25"] += 0.001
    weights["freq50"] -= 0.001
    with pytest.raises(RuntimeError, match="dynamic_weights_recomputed_from_quality"):
        _replay(specimen, freeze)


def test_river_drift_quality_must_reach_weight_input(specimen):
    freeze = _frozen(specimen)
    freeze["challenger"]["river_state"]["freq25"]["quality"] = 0.0
    with pytest.raises(RuntimeError, match="river_quality_consumed_by_dynamic_weights"):
        _replay(specimen, freeze)


def test_champion_weights_must_reproduce_effective_scores(specimen):
    freeze = _frozen(specimen)
    weights = freeze["champion"]["expert_weights"]
    weights["freq25"] += 0.001
    weights["freq50"] -= 0.001
    with pytest.raises(RuntimeError, match="champion_scores_recomputed"):
        _replay(specimen, freeze)


def test_target_leakage_in_raw_signal_rejected(specimen):
    freeze = _frozen(specimen)
    freeze["challenger"]["raw_signals"]["freq25"]["cutoff_contest"] = 3070
    with pytest.raises(RuntimeError, match="all_raw_signals_causal_and_complete"):
        _replay(specimen, freeze)


def test_missing_skill_consumer_and_broken_gate_rejected(specimen):
    changed = {**specimen, "post_gate": copy.deepcopy(specimen["post_gate"])}
    changed["post_gate"]["native_invocations"].pop()
    with pytest.raises(RuntimeError, match="37_native_skill_aliases_invoked"):
        evaluate(**changed)


def test_missing_runtime_sdk_is_not_declared_consumed(specimen, monkeypatch):
    import smart_consumer_integration as consumer
    original = consumer.metadata.version
    def version(name):
        if name == "river":
            raise consumer.metadata.PackageNotFoundError(name)
        return original(name)
    monkeypatch.setattr(consumer.metadata, "version", version)
    with pytest.raises(RuntimeError, match="five_consumed_sdk_packages_installed"):
        evaluate(**specimen)


@pytest.fixture
def persistent_specimen(specimen, tmp_path):
    root = specimen["root"]
    epoch = specimen["freeze_path"].parent.relative_to(root)
    shutil.copytree(root / epoch, tmp_path / epoch)
    shutil.copytree(root / "runtime/procedural_sources", tmp_path / "runtime/procedural_sources")
    for name in ("Mega-Sena.xlsx", "SMART_MEGA_SENA_DRAW_TIME_POLICY.json"):
        shutil.copyfile(root / name, tmp_path / name)
    proof = json.loads((tmp_path / epoch / "FULL_PROCESS_PROOF.json").read_text(encoding="utf-8"))
    return tmp_path, tmp_path / epoch, proof


def test_operator_consumes_real_frozen_chain_persists_and_replays(persistent_specimen, monkeypatch):
    import hashlib
    import smart_operator as op
    from smart_consumer_integration import audit_generation
    root, epoch, proof = persistent_specimen
    frozen_before = {p.relative_to(epoch).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in epoch.rglob("*") if p.is_file()}
    generator = op._card_consumption_checked(lambda root, target: {"proof": proof})
    first = generator(root, 3070)["consumer_integration"]
    artifact = root / first["file"]
    first_bytes, first_time = artifact.read_bytes(), artifact.stat().st_mtime_ns
    # A process retry consumes the persisted freeze without regenerating it.
    result = op._card_consumption_checked(lambda root, target: {
        "schema": "SMART_FREEZE_OPERATION_1", "idempotent_replay": True,
        "freeze_file": proof["freeze_file"]})(root, 3070)
    assert result["consumer_integration"] == first
    assert artifact.read_bytes() == first_bytes
    assert artifact.stat().st_mtime_ns == first_time
    observed = json.loads(first_bytes)
    assert observed["consumption_replay"]["signals_recomputed"] == 12
    rows = observed["consumption_replay"]["signal_ablations"]
    assert len(rows) == 24
    assert all(r["max_score_delta_without_signal"] > 0 for r in rows)
    assert all(r["effective_primary_card_weight"] == 0 for r in rows if r["head"] == "challenger")
    assert observed["card_numbers"] == [10, 11, 27, 38, 43, 53]
    assert observed["predictive_advantage_proven"] is False
    assert frozen_before == {p.relative_to(epoch).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in epoch.rglob("*") if p.is_file()}
    artifact.write_bytes(b'{"broken":')
    assert audit_generation(root, proof) == first
    assert artifact.read_bytes() == first_bytes
    invalid = copy.deepcopy(proof)
    invalid["primary_card_sha256"] = "0" * 64
    from smart_consumer_integration import _sha256_json
    invalid["sha256"] = _sha256_json({k: v for k, v in invalid.items() if k != "sha256"})
    with pytest.raises(RuntimeError, match="full_process_artifacts_bound"):
        audit_generation(root, invalid)
    assert artifact.read_bytes() == first_bytes


def test_failed_consumer_cannot_be_bypassed_by_cached_generation(specimen, monkeypatch):
    import smart_operator as op
    proof = {"target_contest": 3070}
    cached_generator = op._card_consumption_checked(lambda root, target: {"proof": proof})
    calls = []
    def audit(root, generation):
        calls.append(generation)
        raise RuntimeError("simulated invalid consumption")
    monkeypatch.setattr(op, "audit_generation", audit)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="simulated invalid consumption"):
            cached_generator(specimen["root"], 3070)
    assert calls == [proof, proof]


def test_missing_generation_proof_fails_closed(specimen):
    import smart_operator as op
    with pytest.raises(RuntimeError, match="requires this target"):
        op._card_consumption_checked(lambda root, target: {"status": "PASS"})(specimen["root"], 3070)

@pytest.mark.parametrize("fault", ["non_object", "non_finite"])
def test_malformed_generation_proof_rejected_before_any_write(specimen, tmp_path, fault):
    from smart_consumer_integration import audit_generation
    epoch = specimen["freeze_path"].parent
    proof = json.loads((epoch / "FULL_PROCESS_PROOF.json").read_text(encoding="utf-8"))
    if fault == "non_object":
        proof = None
    else:
        proof["untrusted_measurement"] = float("nan")
    with pytest.raises(RuntimeError, match="full_process_proof_valid"):
        audit_generation(tmp_path, proof)
    assert list(tmp_path.iterdir()) == []

"""Adversarial tests for research-only cap-60 card integration."""
from __future__ import annotations

import json
import shutil
import hashlib

import pandas as pd
from pathlib import Path

import pytest

from smart_cap60_parallel import produce
import smart_operator as operator


def sandbox(root: Path, tmp_path: Path) -> tuple[Path, str]:
    src = next(root.glob("runtime/learning_epochs/operator-3071-*/SMART_3071_CHAMPION_CHALLENGER_FREEZE.json"))
    frozen = json.loads(src.read_text(encoding="utf-8"))
    for name in ("freeze_next_research.py", "smart_cap60_experiment_engine.py"):
        shutil.copy2(root / name, tmp_path / name)
    dest = tmp_path / src.relative_to(root)
    dest.parent.mkdir(parents=True)
    shutil.copy2(src, dest)
    data_src = root / frozen["data_file"]
    data_dest = tmp_path / frozen["data_file"]
    data_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(data_src, data_dest)
    return tmp_path, str(src.relative_to(root))


def synthetic_sandbox(root: Path, tmp_path: Path) -> tuple[Path, str]:
    """Construct a clearly synthetic freeze for compatibility and cache tests.

    NEVER rewrite the authoritative 3071 freeze or claim that newly built
    material existed before its real draw. Uses deterministic non-Caixa draws.
    """
    import freeze_next_research as champion_engine
    from smart_v2_engine import load_draws

    for name in ("freeze_next_research.py", "smart_cap60_experiment_engine.py"):
        shutil.copy2(root / name, tmp_path / name)
    dataset = Path("synthetic_test_only.xlsx")
    rows = []
    for i in range(1002):
        vals = sorted(1 + (i * 7 + 11 * j) % 60 for j in range(6))
        rows.append([5001 + i, *vals])
    pd.DataFrame(rows, columns=["Concurso"] + [f"Bola{j}" for j in range(1, 7)]).to_excel(
        tmp_path / dataset, index=False
    )
    draws, contests = load_draws(tmp_path / dataset)
    assert int(contests[-1]) == 6002
    champion = champion_engine.current_policy(draws, start=1000)
    source_hash = hashlib.sha256(
        (tmp_path / "freeze_next_research.py").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    data_hash = hashlib.sha256((tmp_path / dataset).read_bytes()).hexdigest()
    relative = Path("runtime/learning_epochs/SYNTHETIC_ONLY/SMART_6003_CHAMPION_CHALLENGER_FREEZE.json")
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    freeze = {
        "schema": "SYNTHETIC_TEST_FREEZE_NOT_OFFICIAL",
        "synthetic_test_only": True,
        "target_contest": 6003,
        "cutoff_contest": 6002,
        "start_index": 1000,
        "frozen_before_result": True,
        "champion_remains_active": True,
        "production_switch_performed": False,
        "data_file": str(dataset),
        "data_sha256": data_hash,
        "champion_engine_sha256": source_hash,
        "champion": {"top6": champion["top6"]},
    }
    target.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")
    return tmp_path, str(relative).replace("\\", "/")


def test_authentic_3071_freeze_rejects_changed_champion_source_without_mutation(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, rel = sandbox(root, tmp_path)
    frozen = isolated / rel
    before = frozen.read_bytes()
    assert json.loads(before)["target_contest"] == 3071
    with pytest.raises(ValueError, match="champion source differs from frozen champion source"):
        produce(isolated, rel)
    assert frozen.read_bytes() == before
    assert not (frozen.parent / "SMART_3071_CAP60_PARALLEL_CARD.json").exists()


def test_parallel_card_synthetic_is_read_only_and_idempotent(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, rel = synthetic_sandbox(root, tmp_path)
    src = isolated / rel
    original_bytes = src.read_bytes()
    frozen = json.loads(original_bytes)
    first = produce(isolated, rel)
    doc = json.loads((isolated / first["file"]).read_text(encoding="utf-8"))
    assert first["status"] == "FROZEN_SHADOW_ONLY"
    assert len(doc["experimental_card"]) == len(set(doc["experimental_card"])) == 6
    assert doc["champion_card"] == sorted(frozen["champion"]["top6"])
    assert doc["same_card"] == (doc["experimental_card"] == doc["champion_card"])
    assert max(doc["family_max_expert_share"].values()) <= 0.6 + 1e-10
    assert doc["production_authority"] is False
    assert doc["material_weight"] == 0
    assert doc["result_used"] is False
    assert doc["production_switch_performed"] is False
    assert doc["prospective_promotion_authority"] is False
    assert src.read_bytes() == original_bytes
    assert produce(isolated, rel)["status"] == "ALREADY_FROZEN_SHADOW"
    assert src.read_bytes() == original_bytes
    assert frozen["synthetic_test_only"] is True


def test_shadow_tampering_fails_closed(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, rel = synthetic_sandbox(root, tmp_path)
    first = produce(isolated, rel)
    shadow = isolated / first["file"]
    record = json.loads(shadow.read_text())
    record["experimental_card"] = [1, 2, 3, 4, 5, 6]
    shadow.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="self-hash"):
        produce(isolated, rel)


def test_invalid_causal_cutoff_fails_closed(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, rel = sandbox(root, tmp_path)
    frozen_path = isolated / rel
    f = json.loads(frozen_path.read_text())
    f["cutoff_contest"] = f["target_contest"]
    frozen_path.write_text(json.dumps(f))
    with pytest.raises(ValueError, match="pre-result"):
        produce(isolated, rel)


def test_operator_auto_hook_does_not_change_primary_result(monkeypatch):
    import smart_cap60_parallel
    monkeypatch.setattr(operator, "audit_generation", lambda root, proof: {"status": "PASS"})
    monkeypatch.setattr(smart_cap60_parallel, "produce",
                        lambda root, f: {"status": "FROZEN_SHADOW_ONLY", "production_authority": False,
                                         "file": "experimental.json"})
    primary = {"proof": {"target_contest": 4000, "freeze_file": "frozen.json"},
               "primary_card": {"numbers": [1, 2, 3, 4, 5, 6]}}
    @operator._card_consumption_checked
    def fake(root, target):
        return primary
    result = fake(".", 4000)
    assert result["primary_card"] == primary["primary_card"]
    assert result["cap60_parallel"]["status"] == "FROZEN_SHADOW_ONLY"
    assert result["consumer_integration"]["status"] == "PASS"


def test_shadow_failure_cannot_block_audited_productive_card(monkeypatch):
    import smart_cap60_parallel
    monkeypatch.setattr(operator, "audit_generation", lambda root, proof: {"status": "PASS"})
    def fail(*args):
        raise ValueError("experiment invalid")
    monkeypatch.setattr(smart_cap60_parallel, "produce", fail)
    @operator._card_consumption_checked
    def fake(root, target):
        return {"proof": {"target_contest": target, "freeze_file": "frozen.json"},
                "primary_card": {"numbers": [1, 2, 3, 4, 5, 6]}}
    result = fake(".", 4000)
    assert result["primary_card"]["numbers"] == [1, 2, 3, 4, 5, 6]
    assert result["cap60_parallel"]["status"] == "SHADOW_UNAVAILABLE"
    assert result["cap60_parallel"]["production_authority"] is False

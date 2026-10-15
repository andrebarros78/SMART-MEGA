"""Adversarial tests for research-only cap-60 card integration."""
from __future__ import annotations

import json
import shutil
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


def test_parallel_card_real_3071_is_read_only_and_idempotent(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, rel = sandbox(root, tmp_path)
    src = isolated / rel
    original_bytes = src.read_bytes()
    frozen = json.loads(original_bytes)
    first = produce(isolated, rel)
    doc = json.loads((isolated / first["file"]).read_text(encoding="utf-8"))
    assert first["status"] == "FROZEN_SHADOW_ONLY"
    assert doc["experimental_card"] == [10, 11, 27, 38, 43, 53]
    assert doc["champion_card"] == [10, 11, 27, 38, 43, 53]
    assert doc["same_card"] is True
    assert max(doc["family_max_expert_share"].values()) <= 0.6 + 1e-10
    assert doc["production_authority"] is False
    assert doc["material_weight"] == 0
    assert doc["result_used"] is False
    assert doc["production_switch_performed"] is False
    assert doc["prospective_promotion_authority"] is False
    assert src.read_bytes() == original_bytes
    assert produce(isolated, rel)["status"] == "ALREADY_FROZEN_SHADOW"
    assert src.read_bytes() == original_bytes
    assert frozen["champion"]["top6"] == [11, 10, 43, 27, 38, 53]


def test_shadow_tampering_fails_closed(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, rel = sandbox(root, tmp_path)
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

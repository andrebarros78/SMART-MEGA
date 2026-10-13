from __future__ import annotations

import json
from pathlib import Path

from smart_component_reachability import build_registry as build_reachability
from smart_canonical_component_registry import build_registry as build_canonical

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "SMART_F08_PARALLEL_DISPOSITIONS.json"


def _audit():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reach = build_reachability(ROOT)
    canonical = build_canonical(ROOT)
    assert reach["gate"]["status"] == "PASS"
    assert canonical["gate"]["status"] == "PASS"
    groups = manifest["groups"]
    paths = [p for members in groups.values() for p in members]
    assert len(paths) == len(set(paths))
    assert len(paths) == 49
    observed = {
        r["source_file"]
        for r in reach["components"]
        if "/" not in r["source_file"]
        and r["source_file"].endswith(".py")
        and not r["source_file"].startswith("test_")
        and r["source_file"] != "conftest.py"
        and r["role"] not in {"TEST", "PRODUCTION"}
    }
    assert observed == set(paths), (sorted(observed - set(paths)), sorted(set(paths) - observed))
    return manifest, reach, canonical


def test_f08_all_parallel_root_components_are_explicitly_triaged():
    manifest, reach, canonical = _audit()
    by_path = {r["source_file"]: r for r in reach["components"]}
    active_by_path = {r["implementation"]: r for r in canonical["components"]}
    for disposition, paths in manifest["groups"].items():
        assert disposition in manifest["reasoning"]
        for path in paths:
            item = by_path[path]
            active = active_by_path[path]
            assert item["production_reachable"] is False, path
            assert active["state"] != "ACTIVE", path
            assert active["predictive_authority"] == "NONE", path
            assert active["weight_authority"] == "NONE", path
            assert active["freeze_authority"] == "NONE", path
            if disposition == "SHADOW_ONLY":
                assert item["role"] == "SHADOW", path


def test_f08_parallel_scientific_boundaries_are_preserved():
    manifest, reach, _ = _audit()
    groups = manifest["groups"]
    assert "smart_3054_terminal_executor.py" in groups["RETIRED_FROM_PRODUCTION"]
    assert "smart_causal_shadow_runner.py" in groups["SHADOW_ONLY"]
    assert {"smart_rag_excel.py", "smart_procedural_signal_intake.py"} <= set(groups["RESEARCH_ISOLATED"])
    assert {"smart_50_round_simulation.py", "smart_signal_50_round_simulation.py",
            "smart_signal_2000_simulation.py", "smart_portfolio_backtest.py"} <= set(groups["VALIDATION_ONLY"])
    assert all(manifest["rules"].values())
    standalone = set(reach["known_debt_observations"]["independent_entrypoints"])
    assert len(standalone & set(sum(groups.values(), []))) >= 38

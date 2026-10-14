"""Read-only provenance gate connecting frozen card consumers to native agents, skills and SDKs.

This gate does not promote challenger scores or execute quarantined third-party code.
"""
from __future__ import annotations

import hashlib
import json
import math
from importlib import metadata
from pathlib import Path
from typing import Any

SCHEMA = "SMART_CONSUMER_INTEGRATION_V1"
RUNTIME_SDK_ROLES = {
    "pandas": "CANONICAL_HISTORY_INGESTION",
    "river": "CHALLENGER_DRIFT_DIAGNOSTICS",
    "ortools": "AUXILIARY_PORTFOLIO_OPTIMIZER",
    "pydantic": "AGENT_HANDOFF_CONTRACTS",
    "pypdf": "OFFICIAL_DRAW_SCHEDULE",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def _valid_self_hash(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    content = dict(value)
    claimed = content.pop("sha256", None)
    return isinstance(claimed, str) and claimed == _sha256_json(content)


def evaluate(
    *, root: str | Path, target: int, epoch_id: str,
    freeze_path: str | Path, portfolio_path: str | Path,
    primary_card: dict[str, Any], pre_gate: dict[str, Any],
    post_gate: dict[str, Any],
) -> dict[str, Any]:
    """Prove the effective consumer head, preserving evidence-only authorities."""
    root = Path(root).resolve()
    freeze_path = Path(freeze_path).resolve()
    portfolio_path = Path(portfolio_path).resolve()
    freeze_path.relative_to(root)
    portfolio_path.relative_to(root)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    package = json.loads(portfolio_path.read_text(encoding="utf-8-sig"))
    champion, challenger = freeze.get("champion", {}), freeze.get("challenger", {})
    agents = post_gate.get("agent_inventory", [])
    skills = post_gate.get("skill_inventory", [])
    invocations = post_gate.get("native_invocations", [])
    native = [r for r in skills if r.get("pertinent") is True]
    reference_only = [r for r in skills if r.get("pertinent") is False]
    weights = challenger.get("weights", {})
    scores = champion.get("aggregate_scores", {})
    sdk = []
    for name, role in RUNTIME_SDK_ROLES.items():
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = None
        sdk.append({"name": name, "version": version, "installed": version is not None,
                    "role": role, "runtime_installation_is_not_predictive_evidence": True})
    names = {"freq25", "freq50", "freq100", "freq250", "freq500", "freq1000",
             "freq_global", "ewma10", "ewma25", "ewma50", "ewma100", "ewma250"}
    def finite_number(value: Any) -> bool:
        return type(value) in (int, float) and math.isfinite(value)
    numbers = primary_card.get("numbers", [])
    selected = (primary_card.get("selector") or {}).get("selected_numbers")
    package_card = package.get("primary_card", {})
    pre_reg = pre_gate.get("skill_adapter_registry_sha256")
    post_reg = post_gate.get("skill_adapter_registry_sha256")
    checks = {
        "gate_evidence_hashes_valid": _valid_self_hash(pre_gate) and _valid_self_hash(post_gate),
        "primary_card_hash_valid": _valid_self_hash(primary_card),
        "epoch_identity_matches_card": isinstance(epoch_id, str) and epoch_id == primary_card.get("run_id"),
        "pre_and_post_execution_gates_pass": (
            pre_gate.get("status"), pre_gate.get("phase"),
            post_gate.get("status"), post_gate.get("phase"),
        ) == ("PASS", "PRE_FREEZE", "PASS", "POST_FREEZE"),
        "nine_distinct_native_agents": len(agents) == 9
            and len({r.get("name") for r in agents}) == 9
            and all(r.get("probe_result", {}).get("pass") is True for r in agents),
        "37_native_skill_aliases_invoked": len(native) == len(invocations) == 37
            and len({r.get("capability") for r in native}) == 37
            and {r.get("capability") for r in native} == {r.get("capability") for r in invocations}
            and len({r.get("capability") for r in invocations}) == 37
            and all(r.get("agent_owner") in {a.get("name") for a in agents}
                    and r.get("status") == "PASS"
                    and r.get("direct_named_skill_execution") is False
                    and r.get("predictive_weight_authorized") is False for r in invocations),
        "four_reference_only_not_executed": len(reference_only) == 4
            and all(r.get("alias_invocation") is None for r in reference_only),
        "external_third_party_code_quarantined": all(
            r.get("external_skill_source_executed") is False
            and r.get("direct_named_skill_execution") is False for r in skills),
        "five_declared_runtime_sdk_packages_present": all(row["installed"] for row in sdk),
        "adapter_registry_consistent": isinstance(pre_reg, str) and pre_reg == post_reg,
        "twelve_valid_challenger_signal_weights": isinstance(weights, dict)
            and set(weights) == names
            and all(finite_number(v) and v >= 0 for v in weights.values())
            and abs(sum(weights.values()) - 1.0) <= 1e-8,
        "champion_scores_cover_universe": isinstance(scores, dict)
            and set(scores) == {str(i) for i in range(1, 61)}
            and all(finite_number(v) for v in scores.values()),
        "target_result_not_consumed": freeze.get("target_contest") == target
            and freeze.get("cutoff_contest") == target - 1
            and package.get("target_contest") == primary_card.get("target_contest") == target
            and primary_card.get("cutoff_contest") == target - 1
            and freeze.get("frozen_before_result") is True
            and primary_card.get("result_used") is False,
        "primary_consumes_champion_head": primary_card.get("source_head") == "champion"
            and package_card.get("source_head") == "champion"
            and primary_card.get("source_top6_ordered") == champion.get("top6"),
        "six_numbers_exactly_from_selector_and_portfolio": isinstance(numbers, list)
            and numbers == selected == package_card.get("numbers")
            and len(numbers) == len(set(numbers)) == 6
            and all(type(n) is int and 1 <= n <= 60 for n in numbers),
        "freeze_and_portfolio_byte_hashes_bound": primary_card.get("freeze_sha256") == _sha256_file(freeze_path)
            and primary_card.get("portfolio_sha256") == _sha256_file(portfolio_path),
    }
    doc = {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "target_contest": target, "epoch_id": epoch_id,
        "freeze_file": str(freeze_path.relative_to(root)).replace("\\", "/"),
        "freeze_sha256": _sha256_file(freeze_path),
        "portfolio_file": str(portfolio_path.relative_to(root)).replace("\\", "/"),
        "portfolio_sha256": _sha256_file(portfolio_path),
        "card_numbers": list(numbers),
        "effective_decision_head": "champion",
        "challenger_weight_role": "SHADOW_UNLESS_EVIDENCE_PROMOTED",
        "native_agents_executed": len(agents),
        "native_skill_aliases_invoked": len(invocations),
        "external_skill_source_executions": 0,
        "external_llm_provider_calls": 0,
        "sdk": sdk,
        "checks": checks,
        "result_used": False,
        "predictive_advantage_proven": False,
        "claim_boundary": "Native role probes and methodology aliases provide validation evidence, not direct third-party skill execution or decision weight. Five runtime packages verified installed do not imply they individually changed the final card. Primary card scores come from the champion head; challenger weights are not automatically promoted.",
    }
    doc["sha256"] = _sha256_json(doc)
    if doc["status"] != "PASS":
        raise RuntimeError(f"consumer integration failed closed: {checks}")
    return doc


def write(root: str | Path, path: str | Path, **kwargs: Any) -> dict[str, Any]:
    root, path = Path(root).resolve(), Path(path).resolve()
    path.relative_to(root)
    doc = evaluate(root=root, **kwargs)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc

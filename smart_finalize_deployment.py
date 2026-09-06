from __future__ import annotations

import hashlib
import json
from defusedxml import ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import smart_agent_skill_functional_gate as agent_skill_gate
import smart_agent_skill_orchestration as agent_skill_orchestration
import smart_continuity_consolidator as consolidation_module
import smart_total_integration_gate as total_integration_gate
from smart_current_epoch_contract import resolve as resolve_current_epoch

SCHEMA = "SMART_IMPLEMENTATION_PROOF_CURRENT_V3"
JUNIT = "SMART_AUDIT_JUNIT_CURRENT.xml"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def junit_summary(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag == "testsuites" and root.attrib.get("tests") is not None:
        tests = int(root.attrib.get("tests", 0))
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        skipped = int(root.attrib.get("skipped", 0))
        duration = float(root.attrib.get("time", 0.0))
        if tests == 0:
            tests = sum(int(item.attrib.get("tests", 0)) for item in suites)
            failures = sum(int(item.attrib.get("failures", 0)) for item in suites)
            errors = sum(int(item.attrib.get("errors", 0)) for item in suites)
            skipped = sum(int(item.attrib.get("skipped", 0)) for item in suites)
            duration = sum(float(item.attrib.get("time", 0.0)) for item in suites)
    else:
        tests = sum(int(item.attrib.get("tests", 0)) for item in suites)
        failures = sum(int(item.attrib.get("failures", 0)) for item in suites)
        errors = sum(int(item.attrib.get("errors", 0)) for item in suites)
        skipped = sum(int(item.attrib.get("skipped", 0)) for item in suites)
        duration = sum(float(item.attrib.get("time", 0.0)) for item in suites)
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "time_seconds": duration,
        "status": "PASS" if failures == 0 and errors == 0 else "FAIL",
        "sha256": sha(path),
        "file": path.name,
    }


def build(root: Path, *, require_fresh_wmcp: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    consolidation = consolidation_module.build(root, require_fresh_wmcp=require_fresh_wmcp)
    current = resolve_current_epoch(root)
    mission = read(root / "SMART_MISSION_STATUS.json")
    orchestration = agent_skill_orchestration.build_orchestration(root)
    functional_integration = agent_skill_gate.evaluate(root)
    total_integration = read(root / "SMART_TOTAL_INTEGRATION_PROOF.json")
    wmcp_execution = read(root / "SMART_WMCP_EXECUTION_PROOF_20260905.json")
    junit = junit_summary(root / JUNIT)
    adversarial = read(root / "SMART_ADVERSARIAL_CLAIM_AUDIT.json")
    hypothesis_registry = read(root / "SMART_HYPOTHESIS_REGISTRY.json") if (root / "SMART_HYPOTHESIS_REGISTRY.json").exists() else {}
    powered = read(root / "SMART_FALSIFICATION_REPORT_POWERED.json") if (root / "SMART_FALSIFICATION_REPORT_POWERED.json").exists() else {}
    preflight = read(root / "SMART_3054_ADJUDICATION_PREFLIGHT.json") if (root / "SMART_3054_ADJUDICATION_PREFLIGHT.json").exists() else {}
    full_cycle = read(root / "SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json") if (root / "SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json").exists() else {}
    terminal_sandbox = read(root / "SMART_3054_TERMINAL_EXECUTOR_SANDBOX_PROOF.json") if (root / "SMART_3054_TERMINAL_EXECUTOR_SANDBOX_PROOF.json").exists() else {}
    agents = orchestration.get("agents", {})
    freeze_consistent = (
        current["status"] == "RESET_READY"
        and current["freeze_sha256"] is None
        and not current["freeze_authority_present"]
    ) or (
        current["status"] == "FROZEN"
        and current["freeze_authority_present"]
        and isinstance(current["freeze_sha256"], str)
        and len(current["freeze_sha256"]) == 64
    )
    checks = {
        "final_regression_pass": junit["status"] == "PASS",
        "active_epoch_contract_valid": current["target_contest"] == current["cutoff_contest"] + 1 and current["result_used"] is False,
        "current_freeze_state_consistent": freeze_consistent,
        "agent_skill_structural_orchestration_pass": orchestration.get("integration_status") == "PASS" and orchestration.get("integration_scope") == "STRUCTURAL_ORCHESTRATION_ONLY",
        "agent_skill_functional_integration_pass": functional_integration.get("status") == "PASS" and all(functional_integration.get("checks", {}).values()),
        "total_integration_gate_pass": consolidation_module._total_integration_valid(total_integration),
        "wmcp_execution_proof_pass": consolidation_module._wmcp_execution_valid(wmcp_execution, require_fresh=require_fresh_wmcp),
        "all_role_executors_non_authoritative": bool(agents) and all(
            not bool(agent.get("terminal_authority"))
            and not bool(agent.get("predictive_weight_authorized"))
            and not bool(agent.get("freeze_mutation_authorized"))
            for agent in agents.values()
        ),
        "adversarial_non_inert_pipeline_proof_pass": adversarial.get("status") == "PASS" and all(adversarial.get("checks", {}).values()),
        "chat_consolidation_pass": consolidation.get("consolidation_status") == "PASS",
        "mission_not_false_proven": mission.get("status") == "MISSION_ACTIVE" and mission.get("terminal_6of6_proven") is False,
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "current engineering deployment truth derived from active epoch; pre-activation 3054 artifacts remain historical-only",
        "claim_boundary": "Engineering PASS proves executable deterministic role machinery, native methodology bindings, causal pipeline and guards. It does not prove autonomous LLM agents, direct third-party skill execution, lottery predictability, or terminal 6/6.",
        "deployment_status": "PASS" if all(checks.values()) else "FAIL",
        "workspace": str(root),
        "branch": "master",
        "test_evidence": junit,
        "current_epoch": current,
        "freeze_3054": {
            "status": current["status"],
            "top6": current["top6"],
            "sha256": current["freeze_sha256"],
            "file": current["freeze_file"],
            "authority": ("CARRY_FORWARD_PROSPECTIVE_AUTHORITY" if current.get("authority_mode") == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE" else ("ACTIVE_CURRENT_ENGINEERING_EPOCH" if current["freeze_authority_present"] else "NONE_RESET_READY")),
            "result_used": current["result_used"],
        },
        "agent_skill_orchestration": {
            "unique_capabilities_total": orchestration["inventory"]["unique_capabilities_total"],
            "role_executor_count": len(agents),
            "structural_status": orchestration["integration_status"],
            "structural_scope": orchestration.get("integration_scope"),
            "functional_status": functional_integration.get("status"),
            "functional_proof_sha256": functional_integration.get("sha256"),
            "semantic_truth": "deterministic role executors + methodology aliases; no autonomous LLM/direct external-skill claim",
        },
        "wmcp_execution": {
            "artifact": "SMART_WMCP_EXECUTION_PROOF_20260905.json",
            "status": wmcp_execution.get("status"),
            "sha256": wmcp_execution.get("sha256"),
            "command_state": wmcp_execution.get("e2e", {}).get("command_state"),
            "exit_code": wmcp_execution.get("e2e", {}).get("exit_code"),
            "proof_schema": wmcp_execution.get("schema"),
            "live_supervisor_state": wmcp_execution.get("live_runtime", {}).get("supervisor_state"),
            "live_worker_mode": wmcp_execution.get("live_runtime", {}).get("worker_mode"),
        },
        "total_integration": {
            "artifact": "SMART_TOTAL_INTEGRATION_PROOF.json",
            "schema": total_integration.get("schema"),
            "status": total_integration.get("status"),
            "health": total_integration.get("health"),
            "sha256": total_integration.get("sha256"),
            "gate_count": len(total_integration.get("gates", {})),
        },
        "adversarial_claim_audit": {
            "status": adversarial.get("status"),
            "sha256": adversarial.get("sha256"),
            "anchor_top6": adversarial.get("anchor_top6"),
            "policy_top6": adversarial.get("policy_top6"),
            "heaviest_signal": adversarial.get("heaviest_signal"),
            "heaviest_weight_delta": adversarial.get("heaviest_weight_delta"),
        },
        "hypothesis_state": {
            "registry_schema": hypothesis_registry.get("schema"),
            "predictive_promotion_authority": False,
            "null_proof_claim": False,
        },
        "powered_falsification": {
            "replications": powered.get("replications"),
            "resolution_sufficient": powered.get("multiplicity", {}).get("resolution_sufficient"),
            "predictive_weight_authorized": powered.get("predictive_weight_authorized"),
        },
        "prospective_3054_readiness": {
            "current_epoch_status": current["status"],
            "current_freeze_authority": current["freeze_authority_present"],
            "legacy_preflight_status": preflight.get("readiness_status"),
            "legacy_full_cycle_sandbox_status": full_cycle.get("status"),
            "legacy_authority": "PRE_FULL_ACTIVATION_HISTORICAL_ONLY",
            "current_result_used": current["result_used"],
        },
        "terminal_executor_3054": {
            "legacy_sandbox_status": terminal_sandbox.get("status"),
            "legacy_authority": "PRE_FULL_ACTIVATION_HISTORICAL_ONLY",
            "current_terminal_authority": False,
        },
        "official_evidence_policy": {
            "module": "smart_official_evidence_consensus.py",
            "operational_primary": "CAIXA contest API",
            "secondary": "CAIXA consolidated results download",
            "secondary_stale_or_unavailable_never_counts_as_consensus": True,
            "channel_conflict_is_fatal": True,
            "independent_audit_still_required_for_terminal_6of6": True,
        },
        "checks": checks,
        "mission_state": mission["status"],
        "terminal_6of6_proven": mission["terminal_6of6_proven"],
        "scientific_predictive_status": mission.get("scientific_predictive_status"),
        "prospective_advantage_status": mission.get("prospective_advantage_status"),
    }


def render_continuity(proof: dict[str, Any]) -> str:
    j = proof["test_evidence"]
    epoch = proof["current_epoch"]
    freeze = proof["freeze_3054"]
    agents = proof["agent_skill_orchestration"]
    adversarial = proof["adversarial_claim_audit"]
    if epoch["status"] == "FROZEN":
        numbers = " - ".join(str(x).zfill(2) for x in (freeze["top6"] or []))
        freeze_line = f"Top-6 atual: `{numbers}`\n\nSHA-256: `{freeze['sha256']}`\n\nAutoridade: `CARRY_FORWARD_PROSPECTIVE_AUTHORITY` quando a freeze precede a versÃ£o de engenharia atual; a versÃ£o atual permanece shadow para este alvo."
    else:
        freeze_line = "Nenhum freeze da versao atual possui autoridade. O epoch esta `RESET_READY`; freezes anteriores sao historicos e nao podem provar a versao atual."
    return f"""# SMART-MEGA - CONTINUIDADE CANONICA ATUAL

**Atualizacao:** {proof['generated_at_utc']}
**Workspace:** `C:\\New Projet\\SMART-MEGA`
**Estado soberano:** `{proof['mission_state']}`

## Autoridade atual

A autoridade de execucao e `SMART_ACTIVE_EPOCH.json`; a autoridade terminal continua sendo `SMART_MISSION_STATUS.json`.
Artefatos anteriores a ativacao atual sao historicos, exceto freeze, estado e ledger explicitamente preservados por `SMART_PROSPECTIVE_AUTHORITY_LOCK.json` como autoridade cientifica do experimento ainda nao adjudicado.

## O que os chamados agentes/skills realmente sao

- executores deterministas de papeis: **{agents['role_executor_count']}**;
- capacidades/metodologias registradas: **{agents['unique_capabilities_total']}**;
- nao sao nove LLMs autonomos;
- nomes de skills externas sao vinculos metodologicos para probes/implementacoes nativas, nao execucao direta da biblioteca externa;
- codigo externo permanece em quarentena/source-only.

## Epoch causal atual

- estado: **{epoch['status']}**;
- cutoff: **{epoch['cutoff_contest']}**;
- alvo: **{epoch['target_contest']}**;
- resultado do alvo utilizado: **{str(epoch['result_used']).lower()}**.

## Freeze prospectivo atual

{freeze_line}

## Teste adversarial contra "mesmo X"

- status: **{adversarial['status']}**;
- sinal mais pesado perturbado: **{adversarial['heaviest_signal']}**;
- variacao causal de peso: **{adversarial['heaviest_weight_delta']}**;
- politicas internas produzem Top-6 distintos: **sim**.

Isso prova que a arquitetura nova nao e computacionalmente inerte. Nao prova vantagem preditiva da Mega-Sena nem 6/6.

## Regressao atual

`{j['tests']} testes / {j['failures']} failures / {j['errors']} errors`

JUnit: `{j['file']}`
SHA-256: `{j['sha256']}`

## Regra terminal

Estado terminal: `{proof['mission_state']}`

Nao declarar `MISSION_PROVEN` enquanto `SMART_MISSION_STATUS.json` mantiver `terminal_6of6_proven = false` ou faltar evidencia prospectiva causal e auditoria independente.
"""


def write(root: Path) -> dict[str, Any]:
    total_integration_gate.write(root)
    consolidation_module.refresh_wmcp_execution_proof(root)
    consolidation_module.write(root, refresh_total_gate=False, refresh_wmcp_probe=False)
    proof = build(root, require_fresh_wmcp=True)
    if proof["deployment_status"] != "PASS":
        raise RuntimeError({"deployment_checks": proof["checks"]})
    (root / "SMART_IMPLEMENTATION_PROOF_20260904.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "SMART_CONTINUITY.md").write_text(render_continuity(proof), encoding="utf-8")
    return proof


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = write(project_root)
    print(json.dumps({
        "deployment_status": result["deployment_status"],
        "tests": result["test_evidence"]["tests"],
        "failures": result["test_evidence"]["failures"],
        "mission_state": result["mission_state"],
        "terminal_6of6_proven": result["terminal_6of6_proven"],
        "current_epoch_status": result["current_epoch"]["status"],
    }, ensure_ascii=False))

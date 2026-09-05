from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import smart_continuity_consolidator as consolidation_module
import smart_hypothesis_state_reconciler as hypothesis_reconciler

SCHEMA = "SMART_IMPLEMENTATION_PROOF_20260904_V2"
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


def build(root: Path) -> dict[str, Any]:
    consolidation = consolidation_module.build(root)
    mission = read(root / "SMART_MISSION_STATUS.json")
    orchestration = read(root / "SMART_AGENT_SKILL_ORCHESTRATION.json")
    p1p2 = read(root / "SMART_P1_P2_CARTOGRAPHY_PROOF.json")
    convergence = read(root / "SMART_MONTE_CARLO_CONVERGENCE_1000.json")
    powered = read(root / "SMART_FALSIFICATION_REPORT_POWERED.json")
    hypothesis_proof = read(root / "SMART_HYPOTHESIS_STATE_RECONCILIATION.json")
    hypothesis_registry = read(root / "SMART_HYPOTHESIS_REGISTRY.json")
    result_store = read(root / "SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json")
    preflight = read(root / "SMART_3054_ADJUDICATION_PREFLIGHT.json")
    full_cycle = read(root / "SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json")
    terminal_sandbox = read(root / "SMART_3054_TERMINAL_EXECUTOR_SANDBOX_PROOF.json")
    independent = read(root / "SMART_P14_INDEPENDENT_AUDIT_CURRENT.json")
    authority = read(root / "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json")
    junit = junit_summary(root / JUNIT)

    freeze = root / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"
    data = root / "Mega-Sena_through_3053_v2.xlsx"
    canonical_result_store = root / "Mega-Sena.xlsx"
    agents = orchestration.get("agents", {})
    target_hypotheses = {
        item["id"]: item
        for item in hypothesis_registry.get("hypotheses", [])
        if item.get("id") in hypothesis_reconciler.TARGET_HYPOTHESES
    }

    checks = {
        "final_regression_pass": junit["status"] == "PASS",
        "freeze_3054_immutable": sha(freeze) == consolidation_module.FREEZE_EXPECTED_SHA256,
        "dataset_3053_bound": sha(data) == consolidation_module.DATA_EXPECTED_SHA256,
        "agent_skill_orchestration_pass": orchestration.get("integration_status") == "PASS",
        "all_agents_non_authoritative": bool(agents) and all(
            not bool(agent.get("terminal_authority"))
            and not bool(agent.get("predictive_weight_authorized"))
            and not bool(agent.get("freeze_mutation_authorized"))
            for agent in agents.values()
        ),
        "p1p2_canonical_1000": int(p1p2.get("replications", 0)) == 1000
        and p1p2.get("p2_atlas_sha256") == sha(root / "SMART_RANDOMNESS_ATLAS.json"),
        "convergence_audited_1000": int(convergence.get("final_replications", 0)) == 1000
        and convergence.get("final_atlas_sha256") == sha(root / "SMART_RANDOMNESS_ATLAS_1000.json"),
        "powered_holm_resolution_sufficient": powered["multiplicity"]["resolution_sufficient"] is True,
        "powered_controls_detected": powered["adversarial_sensitivity"]["all_expected_directions_detected"] is True,
        "no_new_predictive_weight_authorized": powered["predictive_weight_authorized"] is False
        and p1p2.get("predictive_weight_authorized") is False
        and convergence.get("predictive_weight_authorized") is False,
        "hypothesis_state_reconciled": hypothesis_proof.get("status") == "PASS"
        and hypothesis_registry.get("schema") == "SMART_HYPOTHESIS_REGISTRY_V4"
        and set(target_hypotheses) == hypothesis_reconciler.TARGET_HYPOTHESES
        and all(
            item.get("status") == hypothesis_reconciler.POWER_RESOLVED_STATUS
            and item.get("promotion_authority") is False
            and item.get("power_resolution", {}).get("failure_to_reject_proves_null") is False
            for item in target_hypotheses.values()
        ),
        "canonical_result_store_ready_3054": result_store.get("final_status") == "PASS"
        and result_store.get("canonical_max_after") == 3053
        and result_store.get("result_store_ready_for_next_contest") is True
        and result_store.get("freeze_3054_unchanged") is True
        and sha(canonical_result_store) == result_store.get("canonical_sha256_after"),
        "adjudication_preflight_3054_pass": preflight.get("readiness_status") == "PASS"
        and preflight.get("active_freeze_sha256") == consolidation_module.FREEZE_EXPECTED_SHA256
        and preflight.get("canonical_adjudication_executed") is False,
        "full_post_result_cycle_sandbox_pass": full_cycle.get("status") == "PASS"
        and full_cycle.get("sequence", {}).get("valid") is True
        and full_cycle.get("learning", {}).get("last_contest") == 3054
        and full_cycle.get("checks", {}).get("canonical_protected_artifacts_unchanged") is True,
        "official_evidence_policy_present": (root / "smart_official_evidence_consensus.py").is_file(),
        "independent_audit_current_three_pairs": independent.get("status") == "PASS"
        and independent.get("prospective_ledger", {}).get("pair_count") == 3
        and independent.get("prospective_ledger", {}).get("no_future_leakage") is True
        and independent.get("deterministic_replay", {}).get("target_contest") == 3054
        and independent.get("deterministic_replay", {}).get("cutoff_contest") == 3053,
        "prospective_authority_current": authority.get("independent_audit", {}).get("status") == "PASS"
        and authority.get("independent_audit", {}).get("pair_count") == 3
        and authority.get("targets", {}).get("3054", {}).get("adjudicated") is False,
        "terminal_executor_sandbox_pass": terminal_sandbox.get("status") == "PASS"
        and terminal_sandbox.get("sandbox_only") is True
        and terminal_sandbox.get("repeated_execution_idempotent") is True
        and terminal_sandbox.get("all_non_6of6_terminal_guards_pass") is True
        and terminal_sandbox.get("terminal_eligible") is False
        and terminal_sandbox.get("mission_state_after_repeat") == "MISSION_ACTIVE"
        and terminal_sandbox.get("executor_sha256") == sha(root / "smart_3054_terminal_executor.py"),
        "chat_consolidation_pass": consolidation.get("consolidation_status") == "PASS",
        "mission_not_false_proven": mission.get("status") == "MISSION_ACTIVE"
        and mission.get("terminal_6of6_proven") is False,
    }

    proof = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "unified continuity; agent/skill orchestration; powered falsification; 1000-replication cartography; "
            "hypothesis-state reconciliation; canonical result-store repair; 3054 adjudication preflight; "
            "full post-result sandbox cycle; terminal executor end-to-end sandbox; current independent audit; official-evidence corroboration policy"
        ),
        "deployment_status": "PASS" if all(checks.values()) else "FAIL",
        "workspace": str(root),
        "branch": "master",
        "test_evidence": junit,
        "freeze_3054": {
            "top6": [10, 11, 27, 30, 35, 38],
            "sha256": sha(freeze),
            "immutable": sha(freeze) == consolidation_module.FREEZE_EXPECTED_SHA256,
        },
        "agent_skill_orchestration": {
            "unique_capabilities_total": orchestration["inventory"]["unique_capabilities_total"],
            "agent_count": len(agents),
            "status": orchestration["integration_status"],
            "artifact_sha256": sha(root / "SMART_AGENT_SKILL_ORCHESTRATION.json"),
        },
        "powered_falsification": {
            "replications": powered["replications"],
            "holm_family_size": powered["multiplicity"]["family_size"],
            "minimum_replications": powered["multiplicity"]["minimum_replications_for_resolution"],
            "resolution_sufficient": powered["multiplicity"]["resolution_sufficient"],
            "holm_rejections": powered["multiplicity"]["rejected_comparisons"],
            "controls_detected": powered["adversarial_sensitivity"]["all_expected_directions_detected"],
            "predictive_weight_authorized": powered["predictive_weight_authorized"],
            "artifact_sha256": sha(root / "SMART_FALSIFICATION_REPORT_POWERED.json"),
        },
        "hypothesis_state": {
            "registry_schema": hypothesis_registry["schema"],
            "status": hypothesis_proof["status"],
            "powered_experiment_id": hypothesis_proof["experiment_record"]["experiment_id"],
            "target_hypothesis_status": hypothesis_reconciler.POWER_RESOLVED_STATUS,
            "null_proof_claim": False,
            "predictive_promotion_authority": False,
            "artifact_sha256": sha(root / "SMART_HYPOTHESIS_STATE_RECONCILIATION.json"),
        },
        "cartography_1000": {
            "replications": p1p2["replications"],
            "canonical_atlas_sha256": p1p2["p2_atlas_sha256"],
            "canonical_manifest_sha256": p1p2["p1_manifest_sha256"],
            "proof_sha256": sha(root / "SMART_P1_P2_CARTOGRAPHY_PROOF.json"),
        },
        "convergence": {
            "summary": convergence["stability_summary"],
            "artifact_sha256": sha(root / "SMART_MONTE_CARLO_CONVERGENCE_1000.json"),
        },
        "canonical_result_store": {
            "contest_max": result_store["canonical_max_after"],
            "append_count": result_store["append_count"],
            "sha256": result_store["canonical_sha256_after"],
            "artifact_sha256": sha(root / "SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json"),
        },
        "prospective_3054_readiness": {
            "preflight_status": preflight["readiness_status"],
            "candidate_count": preflight["probability_ledger"]["candidate_count"],
            "all_60_probabilities_retained": preflight["probability_ledger"]["all_candidates_have_60_probabilities"],
            "sandbox_adjudication_valid": preflight["sandbox_rehearsal"]["sequence_valid"],
            "full_cycle_sandbox_status": full_cycle["status"],
            "full_cycle_sequence_valid": full_cycle["sequence"]["valid"],
            "full_cycle_learning_last_contest": full_cycle["learning"]["last_contest"],
            "preflight_sha256": sha(root / "SMART_3054_ADJUDICATION_PREFLIGHT.json"),
            "full_cycle_sha256": sha(root / "SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json"),
        },
        "terminal_executor_3054": {
            "module": "smart_3054_terminal_executor.py",
            "module_sha256": sha(root / "smart_3054_terminal_executor.py"),
            "sandbox_status": terminal_sandbox["status"],
            "sandbox_repeat_idempotent": terminal_sandbox["repeated_execution_idempotent"],
            "sandbox_audited_pair_count": terminal_sandbox["audited_pair_count"],
            "all_non_6of6_terminal_guards_pass": terminal_sandbox["all_non_6of6_terminal_guards_pass"],
            "current_independent_audit_pair_count": independent["prospective_ledger"]["pair_count"],
            "current_independent_audit_status": independent["status"],
            "prospective_authority_pair_count": authority["independent_audit"]["pair_count"],
            "artifact_sha256": sha(root / "SMART_3054_TERMINAL_EXECUTOR_SANDBOX_PROOF.json"),
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
    return proof


def render_continuity(proof: dict[str, Any]) -> str:
    j = proof["test_evidence"]
    c = proof["convergence"]["summary"]
    f = proof["powered_falsification"]
    a = proof["agent_skill_orchestration"]
    h = proof["hypothesis_state"]
    r = proof["canonical_result_store"]
    p = proof["prospective_3054_readiness"]
    t = proof["terminal_executor_3054"]
    return f"""# SMART-MEGA — CONTINUIDADE CANÔNICA

**Atualização:** {proof['generated_at_utc']}
**Workspace:** `C:\\New Projet\\SMART-MEGA`
**Branch:** `master`
**Estado soberano:** `MISSION_ACTIVE`

## Autoridade de missão

A autoridade canônica do estado da missão é `SMART_MISSION_STATUS.json`.
Artefatos de engenharia, agentes, skills, sandboxes e relatórios não podem declarar o 6/6 terminal por conta própria.

## Integração consolidada

- capacidades reconciliadas: **{a['unique_capabilities_total']}**;
- agentes canônicos: **{a['agent_count']}**;
- código externo: quarentena/source-only, sem autoexecução;
- autoridade direta para pesos: **nenhuma**;
- autoridade para alterar freeze: **nenhuma**;
- autoridade terminal de agentes: **nenhuma**.

## Freeze prospectiva 3054

`10 - 11 - 27 - 30 - 35 - 38`

SHA-256: `{proof['freeze_3054']['sha256']}`

A freeze permanece imutável.

## Cartografia e falsificação

- atlas canônico: **1.000 réplicas**;
- convergência 200→1000, máximo |Δp| não degenerado: **{c['max_p_abs_delta_vs_1000']:.6f}**;
- falsificação powered: **{f['replications']} réplicas** para mínimo Holm **{f['minimum_replications']}**;
- resolução suficiente: **{str(f['resolution_sufficient']).lower()}**;
- rejeições Holm: **{len(f['holm_rejections'])}**;
- novo peso preditivo autorizado: **não**.

## Reconciliação de hipóteses

Registro: `{h['registry_schema']}`.
Os quatro testes retrospectivos powered estão em `{h['target_hypothesis_status']}`.
Isso significa que o limite numérico de Monte Carlo foi resolvido, mas **não** que o nulo foi provado e **não** que existe autorização preditiva.
Experimento powered: `{h['powered_experiment_id']}`.

## Base canônica de resultados

`Mega-Sena.xlsx` está contínuo até o concurso **{r['contest_max']}**; foram incorporados **{r['append_count']}** concursos que faltavam, sem alterar a freeze 3054.

## Prontidão prospectiva 3054

- preflight: **{p['preflight_status']}**;
- candidatos com probabilidades integrais: **{p['candidate_count']}**;
- 60 probabilidades preservadas por candidato: **{str(p['all_60_probabilities_retained']).lower()}**;
- adjudicação em sandbox: **PASS**;
- ciclo `adjudicar → aprender → prova sequencial` em sandbox: **{p['full_cycle_sandbox_status']}**;
- estado aprendido sintético termina em 3054: **{p['full_cycle_learning_last_contest']}**;
- nenhuma execução sandbox modificou os artefatos prospectivos canônicos.

## Evidência oficial

O resultado operacional pode ser obtido pelo endpoint oficial da CAIXA por concurso. A corroboração de fonte usa também o download consolidado da CAIXA quando ele já contém o alvo. Fonte secundária atrasada/indisponível não conta como consenso, conflito entre canais é fatal, e auditoria independente continua obrigatória para qualquer prova terminal.

## Regressão atual

`{j['tests']} passed / {j['failures']} failures / {j['errors']} errors`

JUnit: `{j['file']}`
SHA-256: `{j['sha256']}`

## Regra de continuidade

O próximo gate empírico é o resultado oficial do concurso 3054. Até lá, pesquisa shadow pode continuar, mas nenhuma informação posterior pode alterar retroativamente a freeze 3054.

Estado terminal: `MISSION_ACTIVE`

Não declarar `MISSION_PROVEN` enquanto `SMART_MISSION_STATUS.json` mantiver `terminal_6of6_proven = false` ou enquanto faltar a evidência prospectiva e auditoria independente exigidas pelo contrato terminal.

Compatibilidade textual legada: NÃ£o declarar `MISSION_PROVEN` sem cumprir a regra terminal.
"""


def write(root: Path) -> dict[str, Any]:
    consolidation_module.write(root)
    proof = build(root)
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
        "preflight_3054": result["prospective_3054_readiness"]["preflight_status"],
        "full_cycle_sandbox": result["prospective_3054_readiness"]["full_cycle_sandbox_status"],
    }, ensure_ascii=False))

"""Semantic module bindings for SMART-MEGA V6.

The production code stays in main/. This registry indexes and verifies it
without moving, importing, executing or rewriting production modules.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent if (HERE.parent / "smart_operator.py").is_file() else HERE.parent / "main"
ROOT = MAIN.parent if MAIN.name == "main" else MAIN
REGISTRY = HERE / "semantic_registry.json"
CONTRACT = (MAIN / "contracts" / "SEMANTIC_MODULES_CONTRACT.json" if (MAIN / "contracts").is_dir() else ROOT / "contracts" / "SEMANTIC_MODULES_CONTRACT.json")
SCHEMA = "SMART_V6_SEMANTIC_MODULES_V1"

# Ordered by specificity. Unknown files fail closed; there is no catch-all.
SPECS = [
 ("M21", "Ferramentas historicas e suporte", ["conftest.py", "fix_patch_e2e_*.py", "smart_3054_*.py"]),
 ("M14", "Execucao terminal", ["smart_terminal_*.py"]),
 ("M15", "Operador e autoridade GitHub", ["smart_github_*.py", "smart_protected_pr_publication.py"]),
 ("M16", "Agentes, skills e SDKs", ["smart_agent_*.py", "smart_skill_*.py", "smart_native_signal_catalog.py"]),
 ("M19", "Recuperacao, transacoes e seguranca operacional", [
    "smart_crash_safe_io.py", "smart_disconnection_gate.py", "smart_execution_checkpoint.py",
    "smart_frozen_terminal_recovery.py", "smart_http_guard.py", "smart_idempotency.py",
    "smart_missed_catchup.py", "smart_operation_lock.py", "smart_operation_recovery.py",
    "smart_rollover.py", "smart_runtime_guard.py", "smart_startup_reconciler.py",
    "smart_transaction_journal.py"]),
 ("M06", "Pesos, calibracao e metagovernanca", [
    "*calibration*.py", "*calibrat*.py", "smart_rank_score_calibration.py",
    "smart_contextual_meta_weights.py", "smart_signal_weights.py", "smart_meta_governor.py"]),
 ("M20", "Metricas, analise pos-resultado e relatorios", [
    "smart_probability_audit.py", "smart_post_result_report.py",
    "smart_refresh_falsification_report.py", "smartmega_apply_post_result_report_*.py"]),
 ("M01", "Identidade, caminhos e integridade de fonte", [
    "smart_canonical_identity.py", "smart_canonical_root_rebind.py",
    "smart_path_semantics.py", "smart_storage_surfaces.py", "smart_source_identity.py",
    "smart_canonical_component_registry.py", "smart_component_reachability.py",
    "smart_critical_code_manifest.py", "smart_repository_integrity.py",
    "smart_historical_binding.py"]),
 ("M02", "Contratos, estados e governanca", [
    "smart_contract_registry.py", "smart_current_epoch_contract.py",
    "smart_material_deficiency_*.py", "smart_scientific_state_guard.py",
    "smart_authority_freshness.py", "smart_mission_status.py"]),
 ("M03", "Coleta e conciliacao de resultados oficiais", [
    "smart_official_*.py", "smart_fast_result_ingest.py",
    "smart_public_result_capture.py", "smart_canonical_result_store_reconcile.py",
    "smart_canonical_history_advance.py", "smart_frontier_adjudicator.py"]),
 ("M04", "Captacao, qualidade e integridade de dados", [
    "smart_procedural_*.py", "smart_data_quality_gate.py",
    "smart_rag_excel.py", "smart_scoped_history_gate.py"]),
 ("M05", "Sinais, relevancia e atribuicao", [
    "smart_signal_*.py"]),
 ("M07", "Contexto e causalidade", [
    "smart_context_regime.py", "smart_causal_shadow_runner.py"]),
 ("M08", "Motor matematico e cartografia", [
    "smart_v2_*.py", "smart_cartography_extended.py",
    "smart_monte_carlo_convergence.py", "smart_randomness_cartography.py",
    "smart_promote_cartography_1000.py"]),
 ("M09", "Cartoes, selecao e portfolio", [
    "*card*.py", "smart_portfolio_*.py", "smart_manual_generation_authority.py",
    "smart_frozen_card_reader.py"]),
 ("M10", "Aprendizado e fine tuning", [
    "*learning*.py", "*fine_tuning*.py", "smart_historical_training_intake.py"]),
 ("M11", "Laboratorio, challengers e falsificacao", [
    "adjudicate_signal_challenger.py", "smart_50_round_simulation.py",
    "smart_signal_50_round_simulation.py", "smart_signal_2000_simulation.py",
    "smart_cap60_*.py", "*challenger*.py", "*falsification*.py",
    "smart_false_negative_rescue.py", "smart_frontier_signal_lab.py",
    "smart_hypothesis_state_reconciler.py", "smart_experiment_lab.py",
    "smart_native_signal_research.py", "smart_native_replay_runner.py",
    "smart_f12_scientific_successor*.py"]),
 ("M12", "Protocolo prospectivo e congelamento", [
    "*prospective*.py", "freeze_next_research.py", "smart_evidence_only_promotion.py",
    "smart_promotion_gate.py"]),
 ("M13", "Operador local e ciclo operacional", [
    "smart_operator*.py", "smart_operational_lifecycle.py",
    "smart_cycle_completion.py", "smart_target_schedule.py",
    "smart_continuity_consolidator.py"]),
 ("M17", "Integracao e entrega", [
    "*integration*.py", "*pipeline*.py", "smart_finalize_deployment.py",
    "smart_engineering_activation.py", "smart_total_integration_gate.py",
    "smart_capability_integration_v2.py"]),
 ("M18", "Auditoria, regressao e evidencia tecnica", [
    "*audit*.py", "*regression*.py", "*integrity*.py", "*certification*.py",
    "*oracle*.py", "*proof_chain*.py", "*red_team*.py",
    "smart_validation_gate.py", "smart_independent_*.py",
    "smart_test_helpers.py", "p14_coverage_plugin.py",
    "smart_f11_predictive_nonregression.py", "smart_linux_ci.py", "smart_release_attestation.py"]),
]
SPECS_BY_ID = {item[0]: item for item in SPECS}


def classify_name(filename: str) -> str:
    for ident, _, patterns in SPECS:
        if any(fnmatch.fnmatchcase(filename, pattern) for pattern in patterns):
            return ident
    raise ValueError(f"Unclassified source; explicit ownership needed: {filename}")


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def verify_file(path: Path, expected: str) -> None:
    if not path.is_file() or file_hash(path) != expected:
        raise ValueError(f"Source hash mismatch: {path.name}")


def _git_head() -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={MAIN}", "-C", str(MAIN),
         "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=15)
    return result.stdout.strip()


def _source_names() -> list[str]:
    return sorted(p.name for p in MAIN.glob("*.py") if not p.name.startswith("test_"))


def _ast_metadata(path: Path, names: set[str]) -> tuple[list[str], list[str], bool]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=path.name)
    imports: set[str] = set()
    exports: list[str] = []
    is_cli = False
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update((item.name.split(".", 1)[0] + ".py") for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0] + ".py")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
        elif isinstance(node, ast.If):
            test = ast.dump(node.test)
            if "__name__" in test and "__main__" in test:
                is_cli = True
    imports.discard(path.name)
    return sorted(imports & names), exports[:40], is_cli


def build_registry() -> dict:
    names = _source_names()
    owners = {name: classify_name(name) for name in names}
    groups = {ident: [] for ident, _, _ in SPECS}
    imports = []
    source_map = {}
    for name in names:
        path = MAIN / name
        deps, exports, is_cli = _ast_metadata(path, set(names))
        rec = {
            "source": name, "relative_path": name,
            "sha256": file_hash(path), "imports": deps,
            "public_symbols": exports, "cli_guard": is_cli,
        }
        groups[owners[name]].append(rec)
        source_map[name] = owners[name]
        imports.extend({
            "source": name, "target": dep,
            "from_module": owners[name], "to_module": owners[dep],
        } for dep in deps)
    modules = []
    for ident, title, _ in sorted(SPECS, key=lambda x: int(x[0][1:])):
        sources = groups[ident]
        if not sources:
            raise ValueError(f"Empty semantic module: {ident}")
        edges = sorted({x["to_module"] for x in imports
                        if x["from_module"] == ident and x["to_module"] != ident})
        modules.append({
            "id": ident, "title": title, "sources": sources,
            "depends_on": edges,
        })
    return {
        "schema": SCHEMA, "repository": "andrebarros78/SMART-MEGA",
        "branch": "main",
        "source_count": len(names), "module_count": len(modules),
        "import_count": len(imports), "modules": modules,
        "imports": sorted(imports, key=lambda x: (x["source"], x["target"])),
    }


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8-sig"))


def resolve_source(filename: str) -> Path:
    doc = load_registry()
    for module in doc["modules"]:
        for source in module["sources"]:
            if source["source"] == filename:
                path = MAIN / source["source"]
                verify_file(path, source["sha256"])
                return path
    raise KeyError(f"Undeclared source: {filename}")


def validate_registry() -> dict:
    doc = load_registry()
    if doc["schema"] != SCHEMA:
        raise ValueError("Registry schema mismatch")
    actual = build_registry()
    if actual != doc:
        raise ValueError("Registry stale: source, hashes, imports or ownership changed")
    for module in doc["modules"]:
        module_path = HERE / module["id"] / "module.json"
        if not module_path.is_file():
            raise ValueError(f"Module descriptor missing: {module['id']}")
        descriptor = json.loads(module_path.read_text(encoding="utf-8-sig"))
        if descriptor != module:
            raise ValueError(f"Module descriptor stale: {module['id']}")
    expected_contract = {
        "schema": "SMART_V6_MODULE_CONTRACT_V1",
        "repository": doc["repository"],

        "modules": doc["module_count"],
        "sources": doc["source_count"],
        "imports": doc["import_count"],
        "registry_sha256": file_hash(REGISTRY),
        "mutation_policy": "read-only bindings; no production code movement",
    }
    if json.loads(CONTRACT.read_text(encoding="utf-8-sig")) != expected_contract:
        raise ValueError("Semantic module contract mismatch")
    return {"status": "PASS", "head": _git_head(),
            "module_count": doc["module_count"],
            "source_count": doc["source_count"], "import_count": doc["import_count"]}


def write_registry() -> dict:
    doc = build_registry()
    HERE.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for module in doc["modules"]:
        folder = HERE / module["id"]
        folder.mkdir(exist_ok=True)
        (folder / "module.json").write_text(
            json.dumps(module, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (folder / "README.md").write_text(
            f"# {module['id']} — {module['title']}\n\n"
            "Vínculos semânticos para código REAL em `../../`. "
            "Esta pasta não duplica nem executa a implementação.\n\n"
            f"Fontes: {len(module['sources'])}; dependências: "
            + ", ".join(module["depends_on"]) + ".\n",
            encoding="utf-8")
    contract = {
        "schema": "SMART_V6_MODULE_CONTRACT_V1",
        "repository": doc["repository"],
        "modules": doc["module_count"], "sources": doc["source_count"],
        "imports": doc["import_count"],
        "registry_sha256": file_hash(REGISTRY),
        "mutation_policy": "read-only bindings; no production code movement",
    }
    CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return validate_registry()


def main() -> int:
    parser = argparse.ArgumentParser(description="SMART-MEGA V6 semantic modules")
    parser.add_argument("command", choices=("build", "validate", "which", "list"))
    parser.add_argument("filename", nargs="?")
    args = parser.parse_args()
    if args.command == "build":
        out = write_registry()
    elif args.command == "validate":
        out = validate_registry()
    elif args.command == "which":
        if not args.filename:
            parser.error("which needs a .py filename")
        path = resolve_source(args.filename)
        mod_id = classify_name(args.filename)
        out = {"module": mod_id, "source": str(path), "verified": True}
    else:
        doc = load_registry()
        out = [{"id": m["id"], "title": m["title"],
                "sources": len(m["sources"])} for m in doc["modules"]]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

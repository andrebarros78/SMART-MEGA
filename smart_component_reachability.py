from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable

SCHEMA = "SMART_COMPONENT_REACHABILITY_REGISTRY_V1"
EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", ".tox", "node_modules"}
ARCHIVE_PREFIXES = ("archive/", "SMART_STATE_ARCHIVE/", "portable_evidence/", "release_evidence/")
QUARANTINE_PREFIXES = (".external_",)
VALIDATION_TOKENS = (
    "audit", "certif", "integrity", "validation", "proof", "red_team", "falsification",
    "simulation", "backtest", "experiment", "coverage", "reconcile", "report", "sandbox",
    "promote", "finalize", "repair", "test_helper",
)
REQUIRED_PRODUCTION_FILES = {
    "smart_github_operator.py",
    "smart_fast_result_ingest.py",
    "smart_operator.py",
    "smart_full_process_pipeline.py",
    "smart_champion_challenger.py",
    "smart_signal_agent.py",
    "smart_portfolio_pipeline.py",
    "smart_primary_card_selector.py",
    "smart_terminal_executor.py",
    "smart_terminal_engine.py",
}
KNOWN_OPERATOR_PIPELINE_CYCLE = {"smart_operator.py", "smart_full_process_pipeline.py"}


def _python_files(root: Path) -> list[Path]:
    out = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        out.append(path)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_imports(tree: ast.AST, current: str, known: set[str], is_package: bool) -> set[str]:
    edges: set[str] = set()
    package = current if is_package else current.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                candidate = alias.name
                while candidate:
                    if candidate in known:
                        edges.add(candidate)
                        break
                    candidate = candidate.rpartition(".")[0]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package_parts = package.split(".") if package else []
                cut = max(0, len(package_parts) - (node.level - 1))
                prefix = package_parts[:cut]
                target = ".".join(prefix + ([base] if base else []))
            else:
                target = base
            candidates = [target] if target else []
            for alias in node.names:
                if alias.name != "*":
                    candidates.append(".".join(x for x in (target, alias.name) if x))
            for candidate in candidates:
                probe = candidate
                while probe:
                    if probe in known:
                        edges.add(probe)
                        break
                    probe = probe.rpartition(".")[0]
    edges.discard(current)
    return edges


def _declared_execution_paths(tree: ast.AST) -> list[str]:
    values: list[str] = []
    for node in getattr(tree, "body", []):
        value = None
        matched = False
        if isinstance(node, ast.Assign):
            matched = any(isinstance(target, ast.Name) and target.id == "STATIC_EXECUTION_DEPENDENCIES" for target in node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            matched = isinstance(node.target, ast.Name) and node.target.id == "STATIC_EXECUTION_DEPENDENCIES"
            value = node.value
        if not matched or value is None:
            continue
        elements = value.elts if isinstance(value, (ast.Tuple, ast.List, ast.Set)) else [value]
        for element in elements:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                raise ValueError("STATIC_EXECUTION_DEPENDENCIES must contain only literal string paths")
            normalized = element.value.replace("\\", "/").lstrip("./")
            if not normalized.endswith(".py"):
                raise ValueError("STATIC_EXECUTION_DEPENDENCIES entries must be Python file paths")
            values.append(normalized)
    return sorted(set(values))


def _has_main_guard(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        try:
            left = node.test.left
            comparators = node.test.comparators
            if (
                isinstance(node.test, ast.Compare)
                and isinstance(left, ast.Name)
                and left.id == "__name__"
                and comparators
                and isinstance(comparators[0], ast.Constant)
                and comparators[0].value == "__main__"
            ):
                return True
        except AttributeError:
            pass
    return False


# Legacy registry key "workflow_entrypoints" is retained for schema compatibility.
# Entry points now belong to the canonical GitHub source, NOT GitHub Actions.
EXTERNAL_EXECUTION_ENTRYPOINTS = (
    "smart_canonical_component_registry.py",
    "smart_component_reachability.py",
    "smart_disconnection_gate.py",
    "smart_f12_scientific_successor.py",
    "smart_github_certify.py",
    "smart_github_operator.py",
    "smart_fast_result_ingest.py",
    "smart_github_native_policy.py",
    "smart_linux_ci.py",
    "smart_repository_integrity.py",
    "smart_skill_adapter_registry.py",
)
EXTERNAL_EXECUTION_POLICY = "SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021"


def _workflow_entrypoints(root: Path, known_by_path: dict[str, str]) -> dict[str, list[str]]:
    """Resolve explicitly supported external entrypoints, never workflow YAML."""
    workflows = root / ".github" / "workflows"
    if workflows.is_symlink():
        raise ValueError("GitHub Actions workflow directory is forbidden")
    active = (
        sorted(p for p in workflows.rglob("*") if p.is_file() and p.suffix.lower() in {".yml", ".yaml"})
        if workflows.is_dir() else []
    )
    if active:
        raise ValueError("GitHub Actions is forbidden: runnable workflow manifests found")
    return {
        path: [f"EXTERNAL_EXECUTOR:{EXTERNAL_EXECUTION_POLICY}"]
        for path in EXTERNAL_EXECUTION_ENTRYPOINTS
        if path in known_by_path
    }


def _reachable(graph: dict[str, set[str]], roots: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    q = deque(roots)
    while q:
        node = q.popleft()
        if node in seen:
            continue
        seen.add(node)
        q.extend(sorted(graph.get(node, ())))
    return seen


def _root_reachability(graph: dict[str, set[str]], roots: Iterable[str]) -> dict[str, list[str]]:
    by_node: dict[str, list[str]] = defaultdict(list)
    for root in sorted(roots):
        for node in _reachable(graph, [root]):
            by_node[node].append(root)
    return {k: sorted(v) for k, v in by_node.items()}


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    comps: list[list[str]] = []

    def visit(v: str) -> None:
        nonlocal index
        indices[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(graph.get(v, ())):
            if w not in indices:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                comps.append(sorted(comp))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(comps)


def _classify(path: str, reachable: bool) -> tuple[str, str]:
    name = Path(path).name.lower()
    if path.startswith(ARCHIVE_PREFIXES):
        return "ARCHIVE", "historical/evidence namespace"
    if path.startswith(QUARANTINE_PREFIXES):
        return "QUARANTINE", "external source quarantine namespace"
    if path.startswith("tests/") or name.startswith("test_") or name == "conftest.py":
        return "TEST", "test namespace"
    if reachable:
        return "PRODUCTION", "statically reachable from approved external entrypoint with GitHub canonical source"
    if "shadow" in name:
        return "SHADOW", "unreachable shadow-labelled component"
    if any(token in name for token in VALIDATION_TOKENS):
        return "VALIDATION", "unreachable validation/diagnostic component"
    return "DIAGNOSTIC", "not reachable from canonical production entrypoints; retained for F08 reconciliation"


def build_registry(root: Path) -> dict:
    root = root.resolve()
    files = _python_files(root)
    by_module: dict[str, Path] = {}
    by_path: dict[str, str] = {}
    parse_errors: list[dict[str, str]] = []
    parsed: dict[str, ast.AST] = {}
    main_guards: dict[str, bool] = {}
    content_hashes: dict[str, str] = {}
    execution_paths: dict[str, list[str]] = {}
    execution_dependency_errors: list[dict[str, str]] = []

    for path in files:
        rel = path.relative_to(root).as_posix()
        module = _module_name(root, path)
        if not module:
            continue
        by_module[module] = path
        by_path[rel] = module
        raw = path.read_bytes()
        # Normalize text checkout EOL for the code-identity graph, not media
        # or checkpoint payloads. Windows checkout rules must not change F01.
        content_hashes[rel] = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        try:
            tree = ast.parse(raw.decode("utf-8-sig"), filename=rel)
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue
        parsed[module] = tree
        main_guards[module] = _has_main_guard(tree)

    known = set(by_module)
    graph: dict[str, set[str]] = {m: set() for m in known}
    for module, tree in parsed.items():
        imports = _resolve_imports(
            tree,
            module,
            known,
            by_module[module].name == "__init__.py",
        )
        try:
            declared_paths = _declared_execution_paths(tree)
        except ValueError as exc:
            declared_paths = []
            execution_dependency_errors.append({
                "path": by_module[module].relative_to(root).as_posix(),
                "error": str(exc),
            })
        execution_paths[module] = declared_paths
        execution_edges: set[str] = set()
        for declared in declared_paths:
            target = by_path.get(declared)
            if target is None:
                execution_dependency_errors.append({
                    "path": by_module[module].relative_to(root).as_posix(),
                    "error": f"declared execution dependency missing: {declared}",
                })
            else:
                execution_edges.add(target)
        graph[module] = imports | execution_edges

    workflow_paths = _workflow_entrypoints(root, by_path)
    roots = sorted(by_path[p] for p in workflow_paths)
    reachable = _reachable(graph, roots)
    roots_by_node = _root_reachability(graph, roots)
    consumers: dict[str, set[str]] = defaultdict(set)
    for source, targets in graph.items():
        for target in targets:
            consumers[target].add(source)

    cycles = _strongly_connected_components(graph)
    cycle_ids: dict[str, list[int]] = defaultdict(list)
    for idx, comp in enumerate(cycles, start=1):
        for module in comp:
            cycle_ids[module].append(idx)

    components = []
    for rel, module in sorted(by_path.items()):
        cls, reason = _classify(rel, module in reachable)
        components.append({
            "component_id": module,
            "source_file": rel,
            "role": cls,
            "classification_reason": reason,
            "entrypoints": roots_by_node.get(module, []),
            "producers": sorted(graph.get(module, ())),
            "declared_execution_dependencies": execution_paths.get(module, []),
            "consumers": sorted(consumers.get(module, ())),
            "reachable": module in reachable,
            "production_reachable": cls == "PRODUCTION" and module in reachable,
            "runtime_executed": None,
            "runtime_execution_scope": "STATIC_REACHABILITY_ONLY_F01",
            "decision_effect": "NOT_ESTABLISHED_BY_STATIC_REACHABILITY",
            "predictive_authority": "NOT_ESTABLISHED_BY_STATIC_REACHABILITY",
            "has_main_guard": bool(main_guards.get(module, False)),
            "cycle_ids": cycle_ids.get(module, []),
            "sha256": content_hashes.get(rel),
        })

    independent_entrypoints = [
        c["source_file"] for c in components
        if c["has_main_guard"] and not c["reachable"] and c["role"] not in {"TEST", "ARCHIVE", "QUARANTINE"}
    ]
    unclassified = [c["source_file"] for c in components if c["role"] == "UNCLASSIFIED"]
    production_unreachable = [
        c["source_file"] for c in components if c["role"] == "PRODUCTION" and not c["reachable"]
    ]
    required_missing = sorted(REQUIRED_PRODUCTION_FILES - set(by_path))
    required_unreachable = sorted(
        path for path in REQUIRED_PRODUCTION_FILES
        if path in by_path and by_path[path] not in reachable
    )
    known_cycle_detected = any(
        KNOWN_OPERATOR_PIPELINE_CYCLE.issubset({by_module[m].relative_to(root).as_posix() for m in comp})
        for comp in cycles
    )
    legacy_3054_reachable = (
        "smart_3054_terminal_executor.py" in by_path
        and by_path["smart_3054_terminal_executor.py"] in reachable
    )
    terminal_engine_reachable = (
        "smart_terminal_engine.py" in by_path
        and by_path["smart_terminal_engine.py"] in reachable
    )
    inventory_material = "\n".join(
        f"{path}:{content_hashes[path]}" for path in sorted(content_hashes)
    ).encode("utf-8")
    gate_pass = not (
        parse_errors or execution_dependency_errors or unclassified or production_unreachable or required_missing or required_unreachable
    )

    return {
        "schema": SCHEMA,
        "scope": "STATIC_PYTHON_REACHABILITY_FROM_GITHUB_CANONICAL_EXTERNAL_ENTRYPOINTS",
        "classification_policy": {
            "allowed_roles": [
                "PRODUCTION", "SHADOW", "DIAGNOSTIC", "VALIDATION",
                "TEST", "ARCHIVE", "QUARANTINE", "UNCLASSIFIED"
            ],
            "production_definition": "Python module statically reachable from an approved external executor entrypoint using the canonical GitHub source",
            "unreachable_default": "DIAGNOSTIC pending F08 reconciliation",
            "runtime_execution_claimed": False,
            "python_source_sha256_normalization": "CRLF_TO_LF_BEFORE_HASHING",
        },
        "workflow_entrypoints": workflow_paths,
        "entrypoint_authority": EXTERNAL_EXECUTION_POLICY,
        "required_production_files": sorted(REQUIRED_PRODUCTION_FILES),
        "inventory_sha256": hashlib.sha256(inventory_material).hexdigest(),
        "summary": {
            "python_components": len(components),
            "workflow_entrypoints": len(roots),
            "production_components": sum(c["role"] == "PRODUCTION" for c in components),
            "shadow_components": sum(c["role"] == "SHADOW" for c in components),
            "diagnostic_components": sum(c["role"] == "DIAGNOSTIC" for c in components),
            "validation_components": sum(c["role"] == "VALIDATION" for c in components),
            "test_components": sum(c["role"] == "TEST" for c in components),
            "archive_components": sum(c["role"] == "ARCHIVE" for c in components),
            "quarantine_components": sum(c["role"] == "QUARANTINE" for c in components),
            "unclassified_components": len(unclassified),
            "production_unreachable": len(production_unreachable),
            "independent_entrypoints": len(independent_entrypoints),
            "import_cycles": len(cycles),
            "parse_errors": len(parse_errors),
            "declared_execution_dependencies": sum(len(v) for v in execution_paths.values()),
            "execution_dependency_errors": len(execution_dependency_errors),
        },
        "gate": {
            "status": "PASS" if gate_pass else "FAIL",
            "parse_errors": parse_errors,
            "execution_dependency_errors": execution_dependency_errors,
            "unclassified": unclassified,
            "production_unreachable": production_unreachable,
            "required_production_missing": required_missing,
            "required_production_unreachable": required_unreachable,
        },
        "known_debt_observations": {
            "operator_pipeline_cycle_detected": known_cycle_detected,
            "legacy_3054_terminal_executor_reachable": legacy_3054_reachable,
            "generic_terminal_engine_reachable": terminal_engine_reachable,
            "independent_entrypoints": sorted(independent_entrypoints),
        },
        "import_cycles": [
            [
                by_module[module].relative_to(root).as_posix()
                for module in comp
            ]
            for comp in cycles
        ],
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/check SMART-MEGA static component reachability registry.")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    registry = build_registry(root)
    payload = json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    if args.write:
        target = args.write if args.write.is_absolute() else root / args.write
        target.write_text(payload, encoding="utf-8")
    if args.check:
        target = args.check if args.check.is_absolute() else root / args.check
        if not target.exists() or target.read_text(encoding="utf-8") != payload:
            raise SystemExit("reachability registry is stale or missing")
    if registry["gate"]["status"] != "PASS":
        print(json.dumps(registry["gate"], indent=2, ensure_ascii=False))
        return 2
    print(json.dumps({
        "schema": registry["schema"],
        "summary": registry["summary"],
        "known_debt_observations": registry["known_debt_observations"],
        "gate": registry["gate"]["status"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

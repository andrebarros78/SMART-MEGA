from __future__ import annotations

import hashlib
import json
from defusedxml import ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

from smart_source_identity import sha256_source_file

from smart_material_deficiency_registry import load_registry as load_material_deficiency_registry
from smart_critical_code_manifest import build as build_critical_code_manifest

SCHEMA = 'SMART_GLOBAL_INTEGRITY_PROOF_1'
POLICY_SCHEMA = 'SMART_GLOBAL_INTEGRITY_POLICY_1'
GATE_SCHEMA = 'SMART_3052_IMPLEMENTATION_GATE_1'
P14_SCHEMA = 'SMART_INDEPENDENT_AUDIT_1'
DEFAULT_PROOF_PATH = Path('SMART_GLOBAL_INTEGRITY_PROOF.json')
DEFAULT_P14_PATH = Path('SMART_P14_INDEPENDENT_AUDIT_CURRENT.json')
DEFAULT_RED_TEAM_PATH = Path('SMART_P09_RED_TEAM_LATEST.json')
DEFAULT_DEFICIENCY_REGISTRY_PATH = Path('SMART_MATERIAL_DEFICIENCY_REGISTRY.json')

EXPECTED_GATE_IDS = (
    'P01_COUNTERFACTUAL_ATTRIBUTION', 'P02_MARGINAL_SIGNAL_UTILITY',
    'P03_FALSE_CONSENSUS_REDUNDANCY', 'P04_SIGNAL_INTERACTIONS',
    'P05_CONTEXTUAL_META_WEIGHTS', 'P06_RANK_SCORE_CALIBRATION',
    'P07_MULTI_CHALLENGERS', 'P08_META_GOVERNOR', 'P09_CONTINUOUS_RED_TEAM',
    'P10_BOUNDED_ONLINE_LEARNING', 'P11_SIGNAL_EXPANSION_GOVERNANCE',
    'P12_SEQUENTIAL_PROSPECTIVE_PROOF', 'P13_PROMOTION_GATE',
    'P14_INDEPENDENT_AUDIT_NONREGRESSION', 'P15_EVIDENCE_ONLY_PROMOTION',
)
REQUIRED_GATE_GOVERNANCE = (
    'no_partial_success', 'five_of_six_not_acceptable',
    'retroactive_optimization_prohibited', 'future_leakage_prohibited',
    'champion_remains_active_until_prospective_promotion',
    'historical_or_synthetic_improvement_not_equal_prospective_proof',
)
REQUIRED_P14_CHECKS = (
    'coverage_lines_and_branches', 'hash_integrity', 'deterministic_replay',
    'future_leakage_absent', 'full_champion_comparison',
    'promotion_lineage_recomputed', 'independence_no_forbidden_dependencies', 'independent_freeze_decision_oracle',
)
REQUIRED_P14_COVERAGE_SOURCES = (
    'smart_independent_audit.py', 'smart_champion_challenger.py',
    'smart_promotion_gate.py', 'smart_evidence_only_promotion.py',
)
REQUIRED_GLOBAL_COVERAGE_SOURCES = (
    'smart_bounded_online_learning.py', 'smart_signal_expansion_governance.py',
    'smart_sequential_prospective_proof.py', 'smart_promotion_gate.py',
    'smart_independent_audit.py', 'smart_evidence_only_promotion.py',
    'smart_continuous_red_team.py', 'smart_global_integrity.py',
    'smart_champion_challenger.py', 'adjudicate_signal_challenger.py',
    'smart_v2_production.py', 'smart_portfolio_optimizer.py', 'smart_portfolio_pipeline.py',
    'smart_agent_skill_orchestration.py', 'smart_agent_runtime.py', 'smart_agent_skill_functional_gate.py',
    'smart_learning_activation_gate.py', 'smart_learning_activation_authority.py',
    'smart_data_quality_gate.py', 'smart_independent_oracle.py', 'smart_material_deficiency_registry.py',
    'smart_operator.py', 'smart_canonical_history_advance.py',
)
CRITICAL_SOURCE_FILES = (
    'smart_v2_engine.py', 'smart_v2_production.py', 'freeze_next_research.py',
    'smart_signal_quality.py', 'smart_signal_weights.py', 'smart_context_regime.py',
    'smart_signal_marginal_utility.py', 'smart_signal_redundancy_consensus.py',
    'smart_signal_interactions.py', 'smart_contextual_meta_weights.py',
    'smart_rank_score_calibration.py', 'smart_multi_challengers.py', 'smart_meta_governor.py',
    'smart_bounded_online_learning.py', 'smart_signal_expansion_governance.py',
    'smart_sequential_prospective_proof.py', 'smart_promotion_gate.py',
    'smart_independent_audit.py', 'smart_evidence_only_promotion.py',
    'smart_signal_agent.py', 'smart_data_quality_gate.py', 'smart_champion_challenger.py', 'adjudicate_signal_challenger.py',
    'smart_continuous_red_team.py', 'smart_global_integrity.py',
    'smart_portfolio_optimizer.py', 'smart_portfolio_pipeline.py',
    'smart_agent_skill_orchestration.py', 'smart_agent_runtime.py', 'smart_agent_skill_functional_gate.py',
    'smart_learning_activation_gate.py', 'smart_learning_activation_authority.py', 'smart_ai_fine_tuning.py', 'smart_independent_oracle.py',
    'smart_material_deficiency_registry.py', 'smart_continuity_consolidator.py', 'smart_finalize_deployment.py',
    'smart_operator.py', 'smart_canonical_history_advance.py',
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError(f'JSON object required: {path}')
    return obj


def policy_snapshot() -> dict[str, Any]:
    payload = {
        'schema': POLICY_SCHEMA,
        'all_15_gate_items_proven_required': True,
        'exact_gate_contract_required': True,
        'gate_freeze_allowed_required': True,
        'critical_source_hashes_required': True,
        'current_red_team_required': True,
        'current_independent_audit_required': True,
        'zero_material_deficiencies_required': True,
        'material_deficiency_registry_required': True,
        'exact_current_coverage_set_required': list(REQUIRED_GLOBAL_COVERAGE_SOURCES),
        'full_regression_junit_required': True,
        'proof_self_hash_required': True,
        'any_critical_source_change_invalidates_proof': True,
    }
    payload['sha256'] = sha256_json(payload)
    return payload


def gate_state_document(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        'schema': gate.get('schema'),
        'target_contest': gate.get('target_contest'),
        'mandatory_before_freeze': gate.get('mandatory_before_freeze'),
        'freeze_allowed': gate.get('freeze_allowed'),
        'completion_rule': gate.get('completion_rule'),
        'governance': gate.get('governance'),
        'items': gate.get('items'),
        'notes': gate.get('notes'),
        'progress': gate.get('progress'),
    }


def gate_state_sha256(gate: dict[str, Any]) -> str:
    return sha256_json(gate_state_document(gate))


def validate_gate_state(gate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(gate, dict) or gate.get('schema') != GATE_SCHEMA:
        raise ValueError('global integrity gate schema invalid')
    if int(gate.get('target_contest', -1)) != 3052:
        raise ValueError('global integrity gate target must be contest 3052')
    if gate.get('mandatory_before_freeze') is not True:
        raise ValueError('global integrity gate must be mandatory before freeze')
    if gate.get('completion_rule') != 'ALL_15_ITEMS_STATUS_PROVEN_WITH_EVIDENCE':
        raise ValueError('global integrity gate completion rule invalid')
    governance = gate.get('governance')
    if not isinstance(governance, dict) or any(governance.get(k) is not True for k in REQUIRED_GATE_GOVERNANCE):
        raise ValueError('global integrity gate governance flags invalid')
    items = gate.get('items')
    if not isinstance(items, list) or len(items) != 15:
        raise ValueError('global integrity requires exactly 15 gate items')
    priorities = [item.get('priority') if isinstance(item, dict) else None for item in items]
    if priorities != list(range(1, 16)):
        raise ValueError('global integrity gate priorities invalid')
    ids = tuple(str(item.get('id')) for item in items)
    if ids != EXPECTED_GATE_IDS:
        raise ValueError('global integrity gate IDs/order invalid')
    pending = []
    for item in items:
        evidence = item.get('evidence')
        if item.get('status') != 'PROVEN' or not isinstance(evidence, list) or not evidence or any(not isinstance(row, dict) for row in evidence):
            pending.append(str(item.get('id')))
    if pending:
        raise ValueError(f'global integrity gate has pending items: {pending}')
    if gate.get('freeze_allowed') is not True:
        raise ValueError('global integrity requires freeze_allowed=true')
    progress = gate.get('progress')
    if not isinstance(progress, dict) or progress.get('proven_items') != 15 or progress.get('total_items') != 15 or progress.get('remaining_items') != 0:
        raise ValueError('global integrity gate progress is inconsistent')
    remaining_ids = progress.get('remaining_ids', [])
    if remaining_ids not in ([], None):
        raise ValueError('global integrity gate remaining IDs are inconsistent')
    return {'status': 'PASS', 'item_count': 15, 'pending': [], 'freeze_allowed': True, 'contract_exact': True}


def current_source_hashes(root: Path) -> dict[str, str]:
    root = Path(root)
    out = {}
    for name in CRITICAL_SOURCE_FILES:
        p = root / name
        if not p.is_file():
            raise ValueError(f'critical SMART source missing: {name}')
        out[name] = sha256_source_file(p)
    return out


def coverage_summary(root: Path, report_file: str, source_key: str) -> dict[str, Any]:
    path = Path(root) / report_file
    if not path.is_file():
        raise ValueError(f'coverage report missing: {report_file}')
    report = _load_json(path)
    if report.get('meta', {}).get('branch_coverage') is not True:
        raise ValueError(f'branch coverage disabled: {report_file}')
    row = report.get('files', {}).get(source_key)
    if not isinstance(row, dict):
        raise ValueError(f'coverage source missing: {source_key}')
    s = row.get('summary', {})
    if int(s.get('missing_lines', -1)) != 0 or int(s.get('missing_branches', -1)) != 0:
        raise ValueError(f'incomplete line/branch coverage: {source_key}')
    if int(s.get('covered_lines', -1)) != int(s.get('num_statements', -2)):
        raise ValueError(f'incomplete line coverage: {source_key}')
    if int(s.get('covered_branches', -1)) != int(s.get('num_branches', -2)):
        raise ValueError(f'incomplete branch coverage: {source_key}')
    return {
        'report_file': report_file, 'report_sha256': sha256_file(path), 'source_key': source_key,
        'covered_lines': int(s['covered_lines']), 'statements': int(s['num_statements']),
        'covered_branches': int(s['covered_branches']), 'branches': int(s['num_branches']),
    }


def _validate_coverage_set(rows: list[dict[str, Any]]) -> None:
    sources = [str(row.get('source_key')) for row in rows]
    if len(sources) != len(set(sources)):
        raise ValueError('global integrity coverage contains duplicate sources')
    if set(sources) != set(REQUIRED_GLOBAL_COVERAGE_SOURCES):
        raise ValueError('global integrity coverage set is incomplete or unexpected')


def junit_summary(path: Path) -> dict[str, int]:
    path = Path(path)
    if not path.is_file():
        raise ValueError('full regression JUnit file missing')
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError('full regression JUnit XML is malformed') from exc
    suites = [root] if root.tag == 'testsuite' else list(root.findall('testsuite'))
    if not suites:
        raise ValueError('JUnit contains no test suites')
    out = {k: sum(int(float(s.attrib.get(k, 0))) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    if out['tests'] <= 0 or out['failures'] != 0 or out['errors'] != 0:
        raise ValueError(f'full regression JUnit not clean: {out}')
    return out


def validate_p14_report(root: Path, path: Path = DEFAULT_P14_PATH) -> dict[str, Any]:
    p = Path(root) / path
    if not p.is_file():
        raise ValueError('current independent audit report missing')
    report = _load_json(p)
    if report.get('schema') != P14_SCHEMA or report.get('status') != 'PASS':
        raise ValueError('current independent audit report is not PASS')
    observed = report.get('sha256')
    canonical = dict(report); canonical.pop('sha256', None)
    if not isinstance(observed, str) or observed.lower() != sha256_json(canonical):
        raise ValueError('current independent audit self-hash invalid')
    if report.get('promotion_authority') is not False or report.get('independent_of_promotion_decision') is not True:
        raise ValueError('current independent audit authority/independence flags invalid')
    deficiency_registry = load_material_deficiency_registry(root=root)
    if report.get('material_deficiency_registry') != deficiency_registry:
        raise ValueError('current independent audit material deficiency registry is stale')
    if report.get('material_deficiencies') != deficiency_registry['open_deficiencies']:
        raise ValueError('current independent audit material deficiency list mismatch')
    if deficiency_registry['open_count'] != 0:
        raise ValueError('current independent audit has material deficiencies')
    checks = report.get('checks')
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED_P14_CHECKS) or any(checks.get(k) is not True for k in REQUIRED_P14_CHECKS):
        raise ValueError('current independent audit checks are incomplete')
    independence = report.get('independence')
    if not isinstance(independence, dict) or independence.get('status') != 'PASS' or independence.get('independent') is not True or independence.get('static_import_scan') is not True or independence.get('forbidden_dependencies_found') != []:
        raise ValueError('current independent audit independence evidence invalid')
    coverage = report.get('coverage')
    bindings = coverage.get('bindings') if isinstance(coverage, dict) else None
    if not isinstance(coverage, dict) or coverage.get('status') != 'PASS' or not isinstance(bindings, list):
        raise ValueError('current independent audit coverage evidence invalid')
    coverage_sources = [str(row.get('source_file')) for row in bindings if isinstance(row, dict)]
    if len(coverage_sources) != len(bindings) or set(coverage_sources) != set(REQUIRED_P14_COVERAGE_SOURCES) or len(coverage_sources) != len(REQUIRED_P14_COVERAGE_SOURCES):
        raise ValueError('current independent audit coverage sources incomplete')
    if any(row.get('status') != 'PASS' for row in bindings):
        raise ValueError('current independent audit coverage binding not PASS')
    ledger = report.get('prospective_ledger')
    if not isinstance(ledger, dict) or ledger.get('status') != 'PASS' or ledger.get('no_future_leakage') is not True or ledger.get('hash_integrity') is not True or ledger.get('e_process_recomputed') is not True:
        raise ValueError('current independent audit ledger evidence invalid')
    full = ledger.get('full_champion_comparison')
    lineage = ledger.get('promotion_lineage_comparison')
    if not isinstance(full, dict) or full.get('all_pairs_recomputed') is not True:
        raise ValueError('current independent audit Champion comparison invalid')
    if not isinstance(lineage, dict) or lineage.get('lineage_recomputed_independently') is not True or lineage.get('lineage_pairs_recomputed') is not True:
        raise ValueError('current independent audit promotion lineage invalid')
    replay = report.get('deterministic_replay')
    if not isinstance(replay, dict) or replay.get('status') != 'PASS' or replay.get('deterministic') is not True or replay.get('causal_cutoff_verified') is not True:
        raise ValueError('current independent audit deterministic replay invalid')
    oracle = replay.get('independent_decision_oracle')
    if not isinstance(oracle, dict) or oracle.get('verified') is not True or oracle.get('production_engine_imported') is not False:
        raise ValueError('current independent audit decision oracle invalid')
    return {'status': 'PASS', 'file': p.name, 'file_sha256': sha256_file(p), 'report_sha256': observed, 'material_deficiency_registry': deficiency_registry, 'material_deficiencies': list(deficiency_registry['open_deficiencies'])}


def build_global_integrity_proof(root: Path, gate: dict[str, Any], junit_path: Path,
                                 coverage_specs: Iterable[tuple[str, str]]) -> dict[str, Any]:
    root = Path(root).resolve()
    gate_check = validate_gate_state(gate)
    sources = current_source_hashes(root)
    from smart_continuous_red_team import verify_latest_report
    red = verify_latest_report(root / DEFAULT_RED_TEAM_PATH, root)
    p14 = validate_p14_report(root)
    deficiency_registry = load_material_deficiency_registry(root=root)
    if deficiency_registry['open_count'] != 0:
        raise ValueError('global integrity blocked by material deficiencies')
    coverages = [coverage_summary(root, report, source) for report, source in coverage_specs]
    _validate_coverage_set(coverages)
    junit = junit_summary(junit_path)
    proof = {
        'schema': SCHEMA,
        'status': 'PASS',
        'policy': policy_snapshot(),
        'gate_state_sha256': gate_state_sha256(gate),
        'gate_check': gate_check,
        'critical_source_hashes': sources,
        'critical_code_manifest': build_critical_code_manifest(root),
        'coverage': coverages,
        'red_team': {**red, 'file': DEFAULT_RED_TEAM_PATH.name, 'file_sha256': sha256_file(root / DEFAULT_RED_TEAM_PATH)},
        'independent_audit': p14,
        'material_deficiency_registry': deficiency_registry,
        'full_regression': {'junit_file': Path(junit_path).name, 'junit_sha256': sha256_file(junit_path), **junit},
        'material_deficiencies': list(deficiency_registry['open_deficiencies']),
    }
    proof['sha256'] = sha256_json(proof)
    return proof


def verify_global_integrity(root: Path, gate_path: Path, proof_path: Path = DEFAULT_PROOF_PATH) -> dict[str, Any]:
    root = Path(root).resolve(); gate_path = Path(gate_path).resolve()
    proof_path = proof_path if Path(proof_path).is_absolute() else root / proof_path
    gate = _load_json(gate_path); validate_gate_state(gate)
    if not proof_path.is_file():
        raise ValueError('global integrity proof missing')
    proof = _load_json(proof_path)
    if proof.get('schema') != SCHEMA or proof.get('status') != 'PASS' or proof.get('material_deficiencies') != []:
        raise ValueError('global integrity proof is not PASS')
    observed = proof.get('sha256'); canonical = dict(proof); canonical.pop('sha256', None)
    if not isinstance(observed, str) or observed.lower() != sha256_json(canonical):
        raise ValueError('global integrity proof self-hash invalid')
    if proof.get('gate_state_sha256') != gate_state_sha256(gate):
        raise ValueError('global integrity gate state changed after proof')
    deficiency_registry = load_material_deficiency_registry(root=root)
    if deficiency_registry['open_count'] != 0:
        raise ValueError('global integrity material deficiency registry has open items')
    if proof.get('material_deficiency_registry') != deficiency_registry or proof.get('material_deficiencies') != deficiency_registry['open_deficiencies']:
        raise ValueError('global integrity material deficiency registry is stale')
    if proof.get('critical_source_hashes') != current_source_hashes(root):
        raise ValueError('global integrity critical source hashes are stale')
    if proof.get('critical_code_manifest') != build_critical_code_manifest(root):
        raise ValueError('global integrity critical code manifest is stale')
    coverage_rows = proof.get('coverage')
    if not isinstance(coverage_rows, list):
        raise ValueError('global integrity coverage evidence missing')
    _validate_coverage_set(coverage_rows)
    for row in coverage_rows:
        current = coverage_summary(root, str(row.get('report_file')), str(row.get('source_key')))
        if row != current:
            raise ValueError('global integrity coverage evidence is stale')
    from smart_continuous_red_team import verify_latest_report
    red = verify_latest_report(root / DEFAULT_RED_TEAM_PATH, root)
    if proof.get('red_team', {}).get('file_sha256') != sha256_file(root / DEFAULT_RED_TEAM_PATH) or proof.get('red_team', {}).get('report_sha256') != red.get('report_sha256'):
        raise ValueError('global integrity Red Team evidence is stale')
    p14 = validate_p14_report(root)
    if proof.get('independent_audit') != p14:
        raise ValueError('global integrity independent audit evidence is stale')
    junit_file = root / str(proof.get('full_regression', {}).get('junit_file', ''))
    junit = junit_summary(junit_file)
    if proof.get('full_regression', {}).get('junit_sha256') != sha256_file(junit_file):
        raise ValueError('global integrity regression evidence is stale')
    for key, value in junit.items():
        if proof.get('full_regression', {}).get(key) != value:
            raise ValueError('global integrity regression summary mismatch')
    gate_ref = gate.get('global_integrity')
    if not isinstance(gate_ref, dict) or gate_ref.get('file') != proof_path.name or gate_ref.get('sha256') != sha256_file(proof_path):
        raise ValueError('gate does not bind the current global integrity proof')
    return {'status': 'PASS', 'proof_file': proof_path.name, 'proof_file_sha256': sha256_file(proof_path),
            'critical_source_hashes_current': True, 'coverage_current': True, 'red_team_current': True,
            'independent_audit_current': True, 'full_regression_current': True, 'material_deficiency_registry_current': True, 'material_deficiencies': list(deficiency_registry['open_deficiencies'])}


from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

POLICY_SCHEMA = 'SMART_EVIDENCE_ONLY_PROMOTION_POLICY_1'
AUTHORIZATION_SCHEMA = 'SMART_EVIDENCE_ONLY_PROMOTION_AUTHORIZATION_1'
IMPLEMENTATION_GATE_SCHEMA = 'SMART_3052_IMPLEMENTATION_GATE_1'
INDEPENDENT_AUDIT_SCHEMA = 'SMART_INDEPENDENT_AUDIT_1'
P13_PROMOTE_DECISION = 'PROMOTE_SIGNAL_INTELLIGENCE_CHALLENGER'
FINAL_PROMOTE_DECISION = 'PROMOTE_SIGNAL_INTELLIGENCE_CHALLENGER'
KEEP_DECISION = 'KEEP_CHAMPION'
REQUIRED_AUDIT_CHECKS = (
    'coverage_lines_and_branches',
    'hash_integrity',
    'deterministic_replay',
    'future_leakage_absent',
    'full_champion_comparison',
    'promotion_lineage_recomputed',
    'independence_no_forbidden_dependencies',
    'independent_freeze_decision_oracle',
)


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def policy_snapshot() -> dict[str, Any]:
    payload = {
        'schema': POLICY_SCHEMA,
        'p13_statistical_eligibility_required': True,
        'p14_independent_audit_pass_required': True,
        'all_15_implementation_items_proven_required': True,
        'implementation_gate_exact_contract_required': True,
        'implementation_gate_freeze_allowed_required': True,
        'current_global_integrity_proof_required': True,
        'audit_report_self_hash_required': True,
        'audit_promotion_authority_must_be_false': True,
        'audit_independence_flag_required': True,
        'audit_coverage_lines_and_branches_required': True,
        'audit_hash_integrity_required': True,
        'audit_deterministic_replay_required': True,
        'audit_future_leakage_absent_required': True,
        'audit_full_champion_comparison_required': True,
        'p13_p14_metric_identity_required': True,
        'known_material_deficiency_count_must_be_zero': True,
        'missing_or_invalid_evidence_keeps_champion': True,
        'manual_override_prohibited': True,
        'historical_or_synthetic_evidence_cannot_authorize_real_promotion': True,
        'production_switch_requires_explicit_p15_authorization': True,
        'required_audit_checks': list(REQUIRED_AUDIT_CHECKS),
    }
    payload['sha256'] = sha256_json(payload)
    return payload


def _validated_p13(p13: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(p13, dict):
        raise ValueError('P13 status must be an object')
    eligible = p13.get('eligible')
    if not isinstance(eligible, bool):
        raise ValueError('P13 eligible flag must be boolean')
    decision = p13.get('decision')
    if eligible and decision != P13_PROMOTE_DECISION:
        raise ValueError('P13 eligible status must carry the promotion eligibility decision')
    if not eligible and decision != KEEP_DECISION:
        raise ValueError('P13 ineligible status must keep Champion')
    integer_fields = ('n', 'challenger_hits', 'champion_hits', 'advantage_hits', 'cumulative_regret')
    for field in integer_fields:
        value = p13.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f'P13 field {field} must be integer evidence')
    e_value = p13.get('e_value')
    if isinstance(e_value, bool) or not isinstance(e_value, (int, float)) or not math.isfinite(float(e_value)) or float(e_value) < 0.0:
        raise ValueError('P13 field e_value must be finite non-negative numeric evidence')
    if p13['n'] < 0 or p13['challenger_hits'] < 0 or p13['champion_hits'] < 0:
        raise ValueError('P13 counts must be non-negative')
    if p13['advantage_hits'] != p13['challenger_hits'] - p13['champion_hits']:
        raise ValueError('P13 advantage_hits is internally inconsistent')
    if p13['cumulative_regret'] != p13['champion_hits'] - p13['challenger_hits']:
        raise ValueError('P13 cumulative_regret is internally inconsistent')
    if eligible:
        fingerprint = p13.get('candidate_fingerprint')
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError('P13 eligible status must be bound to a 64-hex candidate fingerprint')
        try:
            int(fingerprint, 16)
        except ValueError as exc:
            raise ValueError('P13 eligible candidate fingerprint must be hexadecimal') from exc
        lineage_pair_count = p13.get('lineage_pair_count')
        if isinstance(lineage_pair_count, bool) or not isinstance(lineage_pair_count, int) or lineage_pair_count != p13['n']:
            raise ValueError('P13 eligible lineage pair count must equal n')
    return p13


def _gate_evidence(gate: dict[str, Any] | None) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    summary: dict[str, Any] = {'available': isinstance(gate, dict)}
    if not isinstance(gate, dict):
        blockers.append('implementation_gate_missing')
        return blockers, summary
    if gate.get('schema') != IMPLEMENTATION_GATE_SCHEMA:
        blockers.append('implementation_gate_schema_invalid')
        return blockers, summary
    from smart_global_integrity import EXPECTED_GATE_IDS, REQUIRED_GATE_GOVERNANCE
    target = gate.get('target_contest')
    if isinstance(target, bool) or not isinstance(target, int) or target != 3052:
        blockers.append('implementation_gate_target_invalid')
    if gate.get('mandatory_before_freeze') is not True:
        blockers.append('implementation_gate_mandatory_flag_invalid')
    if gate.get('completion_rule') != 'ALL_15_ITEMS_STATUS_PROVEN_WITH_EVIDENCE':
        blockers.append('implementation_gate_completion_rule_invalid')
    governance = gate.get('governance')
    if not isinstance(governance, dict) or any(governance.get(k) is not True for k in REQUIRED_GATE_GOVERNANCE):
        blockers.append('implementation_gate_governance_invalid')
    items = gate.get('items')
    if not isinstance(items, list) or len(items) != 15:
        blockers.append('implementation_gate_items_invalid')
        return blockers, summary
    priorities = [item.get('priority') if isinstance(item, dict) else None for item in items]
    if priorities != list(range(1, 16)):
        blockers.append('implementation_gate_priorities_invalid')
    ids = tuple(str(item.get('id')) for item in items if isinstance(item, dict))
    if len(ids) != 15 or ids != EXPECTED_GATE_IDS:
        blockers.append('implementation_gate_ids_invalid')
    pending = []
    for item in items:
        if not isinstance(item, dict):
            pending.append('INVALID_ITEM')
            continue
        evidence = item.get('evidence')
        if item.get('status') != 'PROVEN' or not isinstance(evidence, list) or not evidence or any(not isinstance(row, dict) for row in evidence):
            pending.append(str(item.get('id')))
    if pending:
        blockers.append('implementation_gate_not_15_of_15_proven')
    if gate.get('freeze_allowed') is not True:
        blockers.append('implementation_gate_freeze_not_allowed')
    progress = gate.get('progress')
    if not isinstance(progress, dict) or progress.get('proven_items') != 15 or progress.get('total_items') != 15 or progress.get('remaining_items') != 0:
        blockers.append('implementation_gate_progress_invalid')
    by_id = {str(item.get('id')): item for item in items if isinstance(item, dict)}
    if by_id.get('P14_INDEPENDENT_AUDIT_NONREGRESSION', {}).get('status') != 'PROVEN':
        blockers.append('p14_not_proven_in_implementation_gate')
    if by_id.get('P15_EVIDENCE_ONLY_PROMOTION', {}).get('status') != 'PROVEN':
        blockers.append('p15_not_proven_in_implementation_gate')
    summary.update({
        'schema': gate.get('schema'),
        'target_contest': gate.get('target_contest'),
        'contract_exact': not any(b.startswith('implementation_gate_') and b not in {'implementation_gate_not_15_of_15_proven','implementation_gate_freeze_not_allowed'} for b in blockers),
        'proven_items': 15 - len(pending),
        'pending_items': pending,
        'freeze_allowed': gate.get('freeze_allowed') is True,
    })
    return blockers, summary


def _global_integrity_evidence(status: dict[str, Any] | None) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    summary: dict[str, Any] = {'available': isinstance(status, dict), 'verified': False}
    if not isinstance(status, dict):
        blockers.append('global_integrity_missing_or_unverified')
        return blockers, summary
    required_true = (
        'critical_source_hashes_current', 'coverage_current', 'red_team_current',
        'independent_audit_current', 'full_regression_current',
    )
    if status.get('status') != 'PASS':
        blockers.append('global_integrity_not_pass')
    if status.get('material_deficiencies') != []:
        blockers.append('global_integrity_material_deficiencies_present')
    if any(status.get(k) is not True for k in required_true):
        blockers.append('global_integrity_current_evidence_incomplete')
    proof_hash = status.get('proof_file_sha256')
    if not isinstance(proof_hash, str) or len(proof_hash) != 64:
        blockers.append('global_integrity_proof_hash_missing')
    else:
        try:
            int(proof_hash, 16)
        except ValueError:
            blockers.append('global_integrity_proof_hash_invalid')
    verified = not blockers
    summary.update({
        'status': status.get('status'), 'verified': verified,
        'proof_file': status.get('proof_file'), 'proof_file_sha256': status.get('proof_file_sha256'),
        **{k: status.get(k) for k in required_true},
        'material_deficiencies': status.get('material_deficiencies'),
    })
    return blockers, summary


def _audit_self_hash_valid(audit: dict[str, Any]) -> bool:
    observed = audit.get('sha256')
    if not isinstance(observed, str) or len(observed) != 64:
        return False
    canonical = dict(audit)
    canonical.pop('sha256', None)
    return observed == sha256_json(canonical)


def _audit_evidence(audit: dict[str, Any] | None, p13: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    summary: dict[str, Any] = {'available': isinstance(audit, dict)}
    if not isinstance(audit, dict):
        blockers.append('independent_audit_missing')
        return blockers, summary
    if audit.get('schema') != INDEPENDENT_AUDIT_SCHEMA:
        blockers.append('independent_audit_schema_invalid')
        return blockers, summary
    if audit.get('status') != 'PASS':
        blockers.append('independent_audit_not_pass')
    if not _audit_self_hash_valid(audit):
        blockers.append('independent_audit_self_hash_invalid')
    if audit.get('promotion_authority') is not False:
        blockers.append('independent_audit_has_promotion_authority')
    if audit.get('independent_of_promotion_decision') is not True:
        blockers.append('independent_audit_independence_not_proven')
    checks = audit.get('checks')
    if not isinstance(checks, dict):
        blockers.append('independent_audit_checks_missing')
        checks = {}
    failed_checks = [name for name in REQUIRED_AUDIT_CHECKS if checks.get(name) is not True]
    if failed_checks:
        blockers.append('independent_audit_required_checks_failed')

    ledger = audit.get('prospective_ledger')
    if not isinstance(ledger, dict):
        blockers.append('independent_audit_ledger_evidence_missing')
        ledger = {}
    else:
        if ledger.get('status') != 'PASS':
            blockers.append('independent_audit_ledger_not_pass')
        if ledger.get('no_future_leakage') is not True:
            blockers.append('independent_audit_future_leakage_not_cleared')
        if ledger.get('hash_integrity') is not True:
            blockers.append('independent_audit_hash_integrity_not_cleared')
        if ledger.get('e_process_recomputed') is not True:
            blockers.append('independent_audit_e_process_not_recomputed')

    replay = audit.get('deterministic_replay')
    if not isinstance(replay, dict):
        blockers.append('independent_audit_replay_missing')
        replay = {}
    else:
        if replay.get('status') != 'PASS' or replay.get('deterministic') is not True:
            blockers.append('independent_audit_replay_not_deterministic')
        if replay.get('causal_cutoff_verified') is not True:
            blockers.append('independent_audit_replay_causal_cutoff_not_verified')
        oracle = replay.get('independent_decision_oracle')
        if not isinstance(oracle, dict) or oracle.get('verified') is not True or oracle.get('production_engine_imported') is not False:
            blockers.append('independent_audit_decision_oracle_not_verified')

    coverage = audit.get('coverage')
    if not isinstance(coverage, dict) or coverage.get('status') != 'PASS':
        blockers.append('independent_audit_coverage_not_pass')

    global_comparison = ledger.get('full_champion_comparison') if isinstance(ledger, dict) else None
    if not isinstance(global_comparison, dict):
        blockers.append('independent_audit_champion_comparison_missing')
    elif global_comparison.get('all_pairs_recomputed') is not True:
        blockers.append('independent_audit_not_all_pairs_recomputed')

    comparison = ledger.get('promotion_lineage_comparison') if isinstance(ledger, dict) else None
    if not isinstance(comparison, dict):
        blockers.append('independent_audit_promotion_lineage_comparison_missing')
        comparison = {}
    else:
        expected = {
            'adjudicated_contests': int(p13['n']),
            'champion_hits': int(p13['champion_hits']),
            'challenger_hits': int(p13['challenger_hits']),
            'advantage_hits': int(p13['advantage_hits']),
            'cumulative_regret': int(p13['cumulative_regret']),
        }
        for field, value in expected.items():
            if comparison.get(field) != value:
                blockers.append(f'p13_p14_metric_mismatch_{field}')
        if comparison.get('adjudicated_contests') != int(p13['n']):
            blockers.append('p13_p14_pair_count_mismatch')
        if comparison.get('candidate_fingerprint') != p13.get('candidate_fingerprint'):
            blockers.append('p13_p14_lineage_fingerprint_mismatch')
        if comparison.get('lineage_recomputed_independently') is not True or comparison.get('lineage_pairs_recomputed') is not True:
            blockers.append('independent_audit_promotion_lineage_not_recomputed')
        observed_lineage_e = comparison.get('e_value')
        if not isinstance(observed_lineage_e, (int, float)) or isinstance(observed_lineage_e, bool) or not math.isfinite(float(observed_lineage_e)) or not math.isclose(float(observed_lineage_e), float(p13['e_value']), rel_tol=1e-12, abs_tol=1e-12):
            blockers.append('p13_p14_lineage_e_value_mismatch')

    if 'material_deficiencies' not in audit:
        blockers.append('independent_audit_material_deficiencies_missing')
        material = ['missing_material_deficiency_registry']
    else:
        material = audit.get('material_deficiencies')
        if not isinstance(material, list):
            blockers.append('independent_audit_material_deficiencies_invalid')
            material = ['invalid_material_deficiency_registry']
    if material:
        blockers.append('known_material_deficiencies_present')

    independence = audit.get('independence')
    if not isinstance(independence, dict):
        blockers.append('independent_audit_independence_evidence_missing')
    elif (independence.get('status') != 'PASS' or independence.get('independent') is not True
          or independence.get('static_import_scan') is not True
          or independence.get('forbidden_dependencies_found') != []):
        blockers.append('independent_audit_independence_evidence_invalid')

    summary.update({
        'schema': audit.get('schema'),
        'status': audit.get('status'),
        'self_hash_valid': _audit_self_hash_valid(audit),
        'failed_required_checks': failed_checks,
        'pair_count': ledger.get('pair_count') if isinstance(ledger, dict) else None,
        'material_deficiencies': material,
        'deterministic_replay': replay.get('deterministic') if isinstance(replay, dict) else None,
    })
    return blockers, summary


def assess_evidence_only_promotion(
    p13_status: dict[str, Any],
    implementation_gate: dict[str, Any] | None = None,
    independent_audit: dict[str, Any] | None = None,
    global_integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p13 = _validated_p13(p13_status)
    blockers: list[str] = []
    gate_summary: dict[str, Any] = {'available': isinstance(implementation_gate, dict)}
    audit_summary: dict[str, Any] = {'available': isinstance(independent_audit, dict)}
    integrity_summary: dict[str, Any] = {'available': isinstance(global_integrity, dict), 'verified': False}

    if not p13['eligible']:
        blockers.append('p13_not_eligible')
    else:
        gate_blockers, gate_summary = _gate_evidence(implementation_gate)
        audit_blockers, audit_summary = _audit_evidence(independent_audit, p13)
        integrity_blockers, integrity_summary = _global_integrity_evidence(global_integrity)
        blockers.extend(gate_blockers)
        blockers.extend(audit_blockers)
        blockers.extend(integrity_blockers)

    blockers = list(dict.fromkeys(blockers))
    authorized = bool(p13['eligible'] and not blockers)
    result = {
        'schema': AUTHORIZATION_SCHEMA,
        'decision': FINAL_PROMOTE_DECISION if authorized else KEEP_DECISION,
        'authorized': authorized,
        'production_switch_may_proceed': authorized,
        'champion_remains_active': not authorized,
        'p13_eligible': bool(p13['eligible']),
        'p13_gate': p13,
        'implementation_gate': gate_summary,
        'independent_audit': audit_summary,
        'global_integrity': integrity_summary,
        'global_integrity_verified': bool(integrity_summary.get('verified') is True),
        'known_material_deficiencies': [] if authorized else list(blockers),
        'known_material_deficiency_count': 0 if authorized else len(blockers),
        'blockers': blockers,
        'reason': 'all evidence-only promotion requirements proven' if authorized else 'evidence-only promotion requirements not met',
        'policy': policy_snapshot(),
    }
    result['sha256'] = sha256_json(result)
    return result


def assess_evidence_only_promotion_from_files(
    p13_status: dict[str, Any],
    gate_path: Path,
    audit_report_path: Path,
) -> dict[str, Any]:
    p13 = _validated_p13(p13_status)
    if not p13['eligible']:
        return assess_evidence_only_promotion(p13)
    gate = None
    audit = None
    global_integrity = None
    gate_path = Path(gate_path)
    audit_report_path = Path(audit_report_path)
    if gate_path.is_file():
        gate = json.loads(gate_path.read_text(encoding='utf-8'))
    if audit_report_path.is_file():
        audit = json.loads(audit_report_path.read_text(encoding='utf-8'))
    if gate_path.is_file():
        try:
            from smart_global_integrity import verify_global_integrity
            global_integrity = verify_global_integrity(root=gate_path.resolve().parent, gate_path=gate_path.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            global_integrity = {
                'status': 'FAIL', 'material_deficiencies': [type(exc).__name__],
                'critical_source_hashes_current': False, 'coverage_current': False,
                'red_team_current': False, 'independent_audit_current': False,
                'full_regression_current': False, 'proof_file_sha256': None,
            }
    result = assess_evidence_only_promotion(p13, gate, audit, global_integrity)
    try:
        from smart_global_integrity import DEFAULT_PROOF_PATH
        global_proof_path = gate_path.resolve().parent / DEFAULT_PROOF_PATH
    except ImportError:
        global_proof_path = gate_path.resolve().parent / 'SMART_GLOBAL_INTEGRITY_PROOF.json'
    result['evidence_files'] = {
        'implementation_gate_file': str(gate_path),
        'implementation_gate_sha256': sha256_file(gate_path) if gate_path.is_file() else None,
        'independent_audit_file': str(audit_report_path),
        'independent_audit_file_sha256': sha256_file(audit_report_path) if audit_report_path.is_file() else None,
        'global_integrity_file': str(global_proof_path),
        'global_integrity_file_sha256': sha256_file(global_proof_path) if global_proof_path.is_file() else None,
    }
    result['sha256'] = sha256_json({k: v for k, v in result.items() if k != 'sha256'})
    return result


def require_authorized_promotion(authorization: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(authorization, dict):
        raise PermissionError('P15 authorization object required')
    if authorization.get('schema') != AUTHORIZATION_SCHEMA:
        raise PermissionError('invalid P15 authorization schema')
    if authorization.get('authorized') is not True or authorization.get('production_switch_may_proceed') is not True:
        raise PermissionError('production promotion blocked by P15 evidence-only gate')
    if authorization.get('decision') != FINAL_PROMOTE_DECISION:
        raise PermissionError('P15 authorization decision does not permit promotion')
    if authorization.get('global_integrity_verified') is not True:
        raise PermissionError('P15 authorization lacks verified global integrity')
    observed = authorization.get('sha256')
    canonical = dict(authorization)
    canonical.pop('sha256', None)
    if observed != sha256_json(canonical):
        raise PermissionError('P15 authorization hash invalid')
    if authorization.get('known_material_deficiency_count') != 0 or authorization.get('blockers') != []:
        raise PermissionError('P15 authorization contains material deficiencies')
    return authorization

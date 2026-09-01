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
        'implementation_gate_freeze_allowed_required': True,
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
    numeric_fields = ('n', 'challenger_hits', 'champion_hits', 'advantage_hits', 'cumulative_regret', 'e_value')
    for field in numeric_fields:
        value = p13.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f'P13 field {field} must be finite numeric evidence')
    if int(p13['n']) < 0:
        raise ValueError('P13 n must be non-negative')
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
    items = gate.get('items')
    if not isinstance(items, list) or len(items) != 15:
        blockers.append('implementation_gate_items_invalid')
        return blockers, summary
    priorities = [item.get('priority') for item in items]
    if priorities != list(range(1, 16)):
        blockers.append('implementation_gate_priorities_invalid')
    pending = [
        str(item.get('id'))
        for item in items
        if item.get('status') != 'PROVEN'
        or not isinstance(item.get('evidence'), list)
        or len(item.get('evidence')) == 0
    ]
    if pending:
        blockers.append('implementation_gate_not_15_of_15_proven')
    if gate.get('freeze_allowed') is not True:
        blockers.append('implementation_gate_freeze_not_allowed')
    by_id = {str(item.get('id')): item for item in items}
    if by_id.get('P14_INDEPENDENT_AUDIT_NONREGRESSION', {}).get('status') != 'PROVEN':
        blockers.append('p14_not_proven_in_implementation_gate')
    if by_id.get('P15_EVIDENCE_ONLY_PROMOTION', {}).get('status') != 'PROVEN':
        blockers.append('p15_not_proven_in_implementation_gate')
    summary.update({
        'schema': gate.get('schema'),
        'proven_items': 15 - len(pending),
        'pending_items': pending,
        'freeze_allowed': gate.get('freeze_allowed') is True,
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

    coverage = audit.get('coverage')
    if not isinstance(coverage, dict) or coverage.get('status') != 'PASS':
        blockers.append('independent_audit_coverage_not_pass')

    comparison = ledger.get('full_champion_comparison') if isinstance(ledger, dict) else None
    if not isinstance(comparison, dict):
        blockers.append('independent_audit_champion_comparison_missing')
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
        if comparison.get('all_pairs_recomputed') is not True:
            blockers.append('independent_audit_not_all_pairs_recomputed')
        if ledger.get('pair_count') != int(p13['n']):
            blockers.append('p13_p14_pair_count_mismatch')

    material = audit.get('material_deficiencies', [])
    if not isinstance(material, list):
        blockers.append('independent_audit_material_deficiencies_invalid')
        material = ['invalid_material_deficiency_registry']
    if material:
        blockers.append('known_material_deficiencies_present')

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
) -> dict[str, Any]:
    p13 = _validated_p13(p13_status)
    blockers: list[str] = []
    gate_summary: dict[str, Any] = {'available': isinstance(implementation_gate, dict)}
    audit_summary: dict[str, Any] = {'available': isinstance(independent_audit, dict)}

    if not p13['eligible']:
        blockers.append('p13_not_eligible')
    else:
        gate_blockers, gate_summary = _gate_evidence(implementation_gate)
        audit_blockers, audit_summary = _audit_evidence(independent_audit, p13)
        blockers.extend(gate_blockers)
        blockers.extend(audit_blockers)

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
    gate_path = Path(gate_path)
    audit_report_path = Path(audit_report_path)
    if gate_path.is_file():
        gate = json.loads(gate_path.read_text(encoding='utf-8'))
    if audit_report_path.is_file():
        audit = json.loads(audit_report_path.read_text(encoding='utf-8'))
    result = assess_evidence_only_promotion(p13, gate, audit)
    result['evidence_files'] = {
        'implementation_gate_file': str(gate_path),
        'implementation_gate_sha256': sha256_file(gate_path) if gate_path.is_file() else None,
        'independent_audit_file': str(audit_report_path),
        'independent_audit_file_sha256': sha256_file(audit_report_path) if audit_report_path.is_file() else None,
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
    observed = authorization.get('sha256')
    canonical = dict(authorization)
    canonical.pop('sha256', None)
    if observed != sha256_json(canonical):
        raise PermissionError('P15 authorization hash invalid')
    if authorization.get('known_material_deficiency_count') != 0 or authorization.get('blockers') != []:
        raise PermissionError('P15 authorization contains material deficiencies')
    return authorization

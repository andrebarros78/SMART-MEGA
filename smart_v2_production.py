from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_Z_FOR_SIGNAL = 2.0
MAX_NULL_FALSE_POSITIVE_RATE = 0.10
REQUIRE_BEAT_PLACEBO = True
MIN_PROSPECTIVE_CONTESTS = 20
MIN_E_VALUE = 10.0
LEGACY_LEDGER_SCHEMA = 'SMART_PROSPECTIVE_LEDGER_1'
PRODUCTION_AUTHORITY = 'P15_EVIDENCE_ONLY_PROMOTION_ONLY'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _is_hex64(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _invalid_ledger(n: int, reason: str) -> dict[str, Any]:
    return {
        'valid': False,
        'n': int(n),
        'reason': reason,
        'e_value': 0.0,
        'cumulative_regret': math.inf,
        'diagnostic_only': True,
        'production_authority': False,
    }


def validate_ledger(ledger: dict[str, Any] | None) -> dict[str, Any]:
    """Strictly validate legacy prospective evidence for diagnostics only.

    This legacy ledger can never authorize production. Production authority is
    exclusively owned by the P15 evidence-only promotion path.
    """
    if not isinstance(ledger, dict) or ledger.get('schema') != LEGACY_LEDGER_SCHEMA:
        return _invalid_ledger(0, 'prospective ledger missing or invalid schema')
    rows = ledger.get('records')
    if not isinstance(rows, list):
        return _invalid_ledger(0, 'prospective ledger records must be a list')

    seen: set[int] = set()
    valid: list[tuple[int, int, int, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            return _invalid_ledger(len(valid), 'malformed prospective record')
        contest = row.get('contest')
        frozen = row.get('frozen_before_result')
        adjudicated = row.get('adjudicated')
        prediction_hash = row.get('prediction_sha256')
        smart_hits = row.get('smart_hits')
        baseline_hits = row.get('baseline_hits')
        e_value = row.get('e_value_after')
        comparison_eligible = row.get('comparison_eligible')

        if isinstance(contest, bool) or not isinstance(contest, int) or contest <= 0:
            return _invalid_ledger(len(valid), 'prospective record contest must be a positive integer')
        if frozen is not True or adjudicated is not True:
            return _invalid_ledger(len(valid), 'prospective record requires explicit causal/adjudicated booleans')
        if not _is_hex64(prediction_hash):
            return _invalid_ledger(len(valid), 'prospective prediction hash must be hexadecimal SHA-256')
        if isinstance(smart_hits, bool) or not isinstance(smart_hits, int) or not 0 <= smart_hits <= 6:
            return _invalid_ledger(len(valid), 'prospective smart_hits must be an integer in [0,6]')
        if isinstance(baseline_hits, bool) or not isinstance(baseline_hits, int) or not 0 <= baseline_hits <= 6:
            return _invalid_ledger(len(valid), 'prospective baseline_hits must be an integer in [0,6]')
        if isinstance(e_value, bool) or not isinstance(e_value, (int, float)) or not math.isfinite(float(e_value)) or float(e_value) < 0.0:
            return _invalid_ledger(len(valid), 'prospective e_value_after must be finite and non-negative')
        if not isinstance(comparison_eligible, bool):
            return _invalid_ledger(len(valid), 'comparison_eligible must be an explicit boolean')
        if contest in seen:
            return _invalid_ledger(len(valid), 'duplicate prospective contest')
        seen.add(contest)
        if comparison_eligible:
            valid.append((contest, smart_hits, baseline_hits, float(e_value)))

    if not valid:
        return _invalid_ledger(0, 'no adjudicated comparison-eligible prospective records')
    contests = [row[0] for row in valid]
    if contests != sorted(contests):
        return _invalid_ledger(len(valid), 'contest order invalid')

    smart_total = sum(row[1] for row in valid)
    baseline_total = sum(row[2] for row in valid)
    regret = baseline_total - smart_total
    e_value = valid[-1][3]
    enough = len(valid) >= MIN_PROSPECTIVE_CONTESTS
    superior = smart_total > baseline_total and regret < 0
    sequential = e_value >= MIN_E_VALUE
    diagnostic_valid = bool(enough and superior and sequential)
    return {
        'valid': diagnostic_valid,
        'n': len(valid),
        'smart_hits': smart_total,
        'baseline_hits': baseline_total,
        'cumulative_regret': regret,
        'e_value': e_value,
        'enough_contests': enough,
        'superior_to_baseline': superior,
        'sequential_evidence': sequential,
        'reason': 'legacy diagnostic conditions met' if diagnostic_valid else 'legacy diagnostic conditions not met',
        'diagnostic_only': True,
        'production_authority': False,
    }


def decide(audit: dict[str, Any], ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(audit, dict):
        raise ValueError('audit must be an object')
    try:
        walk_forward = audit['walk_forward']
        placebo = audit['placebo']
        monte_carlo = audit['monte_carlo_null']
        historical_checks = {
            'positive_excess_vs_uniform': float(walk_forward['excess_hits']) > 0.0,
            'diagnostic_z_at_least_2': float(walk_forward['diagnostic_z_vs_uniform']) >= MIN_Z_FOR_SIGNAL,
            'beats_placebo': float(walk_forward['total_hits']) > float(placebo['total_hits']) if REQUIRE_BEAT_PLACEBO else True,
            'null_false_positive_rate_ok': float(monte_carlo['false_positive_rate_z_ge_2']) <= MAX_NULL_FALSE_POSITIVE_RATE,
        }
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('malformed legacy production audit') from exc
    if any(not isinstance(value, bool) for value in historical_checks.values()):
        raise ValueError('legacy historical checks must resolve to booleans')

    prospective = validate_ledger(ledger)
    checks = {**historical_checks, 'legacy_prospective_diagnostic_valid': prospective['valid']}
    legacy_diagnostic_signal = bool(all(checks.values()))

    # Contract: this module is diagnostic compatibility only. It can never
    # switch production, regardless of historical or legacy ledger evidence.
    return {
        'mode': 'NO_PREDICTIVE_SIGNAL_DETECTED',
        'predictive_signal_weight': 0.0,
        'structural_neutral_weight': 1.0,
        'checks': checks,
        'prospective_validation': prospective,
        'legacy_diagnostic_signal_detected': legacy_diagnostic_signal,
        'legacy_production_authority_disabled': True,
        'production_authority': PRODUCTION_AUTHORITY,
        'production_switch_may_proceed': False,
        'champion_remains_active': True,
        'production_claim': 'legacy diagnostics cannot authorize production; P15 evidence-only promotion is required',
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', default='SMART_V2_AUDIT_V3.json')
    parser.add_argument('--data', default='Mega-Sena.xlsx')
    parser.add_argument('--ledger', default='SMART_PROSPECTIVE_LEDGER.json')
    parser.add_argument('--out', default='SMART_V2_PRODUCTION_STATE.json')
    args = parser.parse_args()

    audit_path = Path(args.audit)
    data_path = Path(args.data)
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    ledger_path = Path(args.ledger)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else None
    state = decide(audit, ledger)
    state.update({
        'schema': 'SMART_V2_PRODUCTION_STATE_3',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'audit_file': str(audit_path),
        'audit_sha256': sha256(audit_path),
        'data_file': str(data_path),
        'data_sha256': sha256(data_path),
        'ledger_file': str(ledger_path) if ledger_path.exists() else None,
        'ledger_sha256': sha256(ledger_path) if ledger_path.exists() else None,
        'governor_sha256': sha256(Path(__file__)),
        'tie_break': 'score desc, number asc when research ranking is used',
        'retroactive_rewrite': False,
        'cards_generated': False,
        'reason_cards_not_generated': 'technical improvement mode; user did not request cards',
    })
    Path(args.out).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

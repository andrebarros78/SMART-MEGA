from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import river

import smart_v2_engine as e
import freeze_next_research as champion_engine
from smart_signal_agent import SmartSignalAgent, write_state, SIGNAL_NAMES, AGENT_SCHEMA
from smart_signal_expansion_governance import REGISTRY_PATH, load_registry
from smart_portfolio_pipeline import build_portfolio_package
from smart_promotion_gate import (
    BASE_MIN_PROSPECTIVE_CONTESTS, MIN_E_VALUE, assess_promotion_records, policy_snapshot
)
from smart_evidence_only_promotion import (
    assess_evidence_only_promotion_from_files,
    policy_snapshot as evidence_only_promotion_policy_snapshot,
)

LEDGER_SCHEMA = 'SMART_SIGNAL_LEDGER_1'
MIN_PROSPECTIVE_CONTESTS = BASE_MIN_PROSPECTIVE_CONTESTS
E_BET_LAMBDA = 0.25
PRE_3052_GATE_PATH = Path('SMART_3052_IMPLEMENTATION_GATE.json')
PRE_3052_GATE_SCHEMA = 'SMART_3052_IMPLEMENTATION_GATE_1'
P14_AUDIT_REPORT_PATH = Path('SMART_P14_INDEPENDENT_AUDIT_CURRENT.json')
PROMOTION_LINEAGE_SCHEMA = 'SMART_PROMOTION_LINEAGE_1'
PROMOTION_LINEAGE_COMPONENTS = (
    'engine', 'champion_engine', 'signal_agent', 'signal_quality', 'signal_weights', 'context_regime',
    'redundancy_consensus', 'marginal_utility', 'contextual_meta_weights',
    'rank_score_calibration', 'multi_challengers', 'meta_governor',
    'bounded_online_learning', 'signal_interactions', 'signal_expansion_governance',
)


def require_pre_3052_gate(target: int, gate_path: Path = PRE_3052_GATE_PATH) -> dict[str, Any] | None:
    if int(target) < 3052:
        return None
    if not gate_path.exists():
        raise ValueError('SMART pre-3052 implementation gate missing')
    obj = json.loads(gate_path.read_text(encoding='utf-8'))
    items = obj.get('items', [])
    if obj.get('schema') != PRE_3052_GATE_SCHEMA or len(items) != 15:
        raise ValueError('SMART pre-3052 implementation gate invalid')
    priorities = [int(item.get('priority', -1)) for item in items]
    if priorities != list(range(1, 16)):
        raise ValueError('SMART pre-3052 implementation gate priorities invalid')
    pending = [item.get('id') for item in items
               if item.get('status') != 'PROVEN' or not isinstance(item.get('evidence'), list) or not item.get('evidence')]
    if pending or obj.get('freeze_allowed') is not True:
        raise ValueError(f'SMART pre-3052 implementation gate blocked; pending={pending}')
    # Continuous Red Team freshness is enforced only after all 15 implementation gates open.
    if gate_path.resolve() == PRE_3052_GATE_PATH.resolve():
        from smart_continuous_red_team import verify_latest_report
        verify_latest_report(root=gate_path.resolve().parent)
        from smart_global_integrity import verify_global_integrity
        verify_global_integrity(root=gate_path.resolve().parent, gate_path=gate_path.resolve())
    return obj


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()



def archive_state_snapshot(state_path: Path, state_hash: str) -> Path:
    state_path = Path(state_path)
    archive_dir = state_path.parent / 'SMART_STATE_ARCHIVE'
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f'{state_hash}.json'
    if archive_path.exists():
        if sha256(archive_path) != state_hash:
            raise ValueError('immutable state archive hash collision/mismatch')
    else:
        archive_path.write_bytes(state_path.read_bytes())
        if sha256(archive_path) != state_hash:
            archive_path.unlink(missing_ok=True)
            raise ValueError('immutable state archive write verification failed')
    return archive_path


def source_cutoff_timestamp(data: Path) -> str | None:
    try:
        df = pd.read_excel(data)
        if 'Data do Sorteio' not in df.columns or len(df) == 0:
            return None
        dt = pd.to_datetime(df.iloc[-1]['Data do Sorteio'], dayfirst=True, errors='coerce')
        return None if pd.isna(dt) else dt.isoformat()
    except Exception:
        return None


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            'schema': LEDGER_SCHEMA,
            'events': [],
            'rules': {
                'append_only_events': True,
                'freeze_must_precede_result': True,
                'pre_result_supersede_allowed_but_preserved': True,
                'promotion_min_contests': MIN_PROSPECTIVE_CONTESTS,
                'promotion_min_e_value': MIN_E_VALUE,
                'e_process': 'product(1 + 0.25*(challenger_hits-champion_hits)/6)',
            },
        }
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('schema') != LEDGER_SCHEMA or not isinstance(obj.get('events'), list):
        raise ValueError('invalid SMART signal ledger')
    return obj


def write_ledger(path: Path, ledger: dict[str, Any]) -> str:
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
    return sha256(path)


def freeze_events(ledger: dict[str, Any], target: int) -> list[dict[str, Any]]:
    return [ev for ev in ledger.get('events', [])
            if ev.get('event_type') == 'FREEZE' and int(ev.get('target_contest', -1)) == int(target)]


def _validate_ledger_contract(ledger: dict[str, Any]) -> None:
    if not isinstance(ledger, dict) or ledger.get('schema') != LEDGER_SCHEMA or not isinstance(ledger.get('events'), list):
        raise ValueError('invalid SMART signal ledger contract')
    from smart_sequential_prospective_proof import validate_target_sequence
    targets = sorted({
        int(ev.get('target_contest', -1))
        for ev in ledger['events']
        if isinstance(ev, dict) and ev.get('event_type') in {'FREEZE', 'SUPERSEDE', 'ADJUDICATION'}
    })
    if any(target < 0 for target in targets):
        raise ValueError('ledger contains invalid target contest')
    for target in targets:
        validate_target_sequence(ledger, target)


def active_freeze(ledger: dict[str, Any], target: int) -> dict[str, Any] | None:
    _validate_ledger_contract(ledger)
    freezes = freeze_events(ledger, target)
    if not freezes:
        return None
    from smart_sequential_prospective_proof import validate_target_sequence
    sequence = validate_target_sequence(ledger, int(target))
    active_hash = str(sequence['active_freeze_sha256'])
    active = [fr for fr in freezes if str(fr.get('freeze_sha256')) == active_hash]
    if len(active) != 1:
        raise ValueError(f'ledger must resolve exactly one active freeze for contest {target}')
    return active[0]


def paired_events(ledger: dict[str, Any]):
    _validate_ledger_contract(ledger)
    by_hash = {}
    adjudications = {}
    for index, ev in enumerate(ledger.get('events', [])):
        if ev.get('event_type') == 'FREEZE':
            h = str(ev.get('freeze_sha256', ''))
            if h in by_hash:
                raise ValueError('duplicate freeze hash in SMART signal ledger')
            by_hash[h] = (index, ev)
        elif ev.get('event_type') == 'ADJUDICATION':
            c = int(ev.get('target_contest', -1))
            if c in adjudications:
                raise ValueError(f'duplicate adjudication event for contest {c}')
            adjudications[c] = (index, ev)
    pairs = []
    for c in sorted(adjudications):
        ad_index, ad = adjudications[c]
        freeze_sha = str(ad.get('freeze_sha256', ''))
        if freeze_sha not in by_hash:
            raise ValueError(f'adjudication references unknown freeze for contest {c}')
        fr_index, fr = by_hash[freeze_sha]
        if fr_index >= ad_index:
            raise ValueError(f'freeze must precede adjudication for contest {c}')
        if int(fr.get('target_contest', -1)) != c:
            raise ValueError(f'freeze/adjudication target mismatch for contest {c}')
        active = active_freeze(ledger, c)
        if active is None or str(active.get('freeze_sha256')) != freeze_sha:
            raise ValueError(f'adjudication does not reference active freeze for contest {c}')
        pairs.append((c, fr, ad))
    return pairs


def _promotion_candidate_fingerprint(fr: dict[str, Any]) -> str | None:
    lineage = fr.get('promotion_lineage')
    if not isinstance(lineage, dict) or lineage.get('schema') != PROMOTION_LINEAGE_SCHEMA:
        return None
    observed = lineage.get('sha256')
    if not isinstance(observed, str) or len(observed) != 64:
        return None
    try:
        int(observed, 16)
    except ValueError:
        return None
    canonical = dict(lineage)
    canonical.pop('sha256', None)
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(raw).hexdigest() != observed.lower():
        return None
    hashes = fr.get('hashes')
    declared = lineage.get('component_hashes')
    if not isinstance(hashes, dict) or not isinstance(declared, dict):
        return None
    for component in PROMOTION_LINEAGE_COMPONENTS:
        value = hashes.get(component)
        if not isinstance(value, str) or len(value) != 64:
            return None
        try:
            int(value, 16)
        except ValueError:
            return None
        if declared.get(component) != value.lower():
            return None
    return observed.lower()


def promotion_eligibility_status(ledger: dict[str, Any]) -> dict[str, Any]:
    pairs = paired_events(ledger)
    versioned_pairs: list[tuple[int, dict[str, Any], dict[str, Any], str]] = []
    unversioned_causal_pairs = 0
    for c, fr, ad in pairs:
        if not fr.get('frozen_before_result') or not fr.get('causal_cutoff'):
            continue
        raw_record = {'challenger_hits': ad.get('challenger_hits'), 'champion_hits': ad.get('champion_hits')}
        assess_promotion_records([raw_record], 1.0)
        fingerprint = _promotion_candidate_fingerprint(fr)
        if fingerprint is None:
            unversioned_causal_pairs += 1
            continue
        versioned_pairs.append((c, fr, ad, fingerprint))

    lineage: list[tuple[int, dict[str, Any], dict[str, Any], str]] = []
    current_fingerprint = versioned_pairs[-1][3] if versioned_pairs else None
    if current_fingerprint is not None:
        for row in reversed(versioned_pairs):
            if row[3] != current_fingerprint:
                break
            lineage.append(row)
        lineage.reverse()

    records = [
        {'challenger_hits': ad.get('challenger_hits'), 'champion_hits': ad.get('champion_hits')}
        for _, _, ad, _ in lineage
    ]
    # Reuse P13 validation before any arithmetic so fractional/boolean/nonfinite hits cannot be truncated.
    if records:
        assess_promotion_records(records, 1.0)
    lineage_e_value = 1.0
    for record in records:
        challenger_hits = float(record['challenger_hits'])
        champion_hits = float(record['champion_hits'])
        factor = 1.0 + E_BET_LAMBDA * ((challenger_hits - champion_hits) / 6.0)
        if factor <= 0.0:
            raise ValueError('invalid lineage e-process factor')
        lineage_e_value *= factor

    status = assess_promotion_records(records, lineage_e_value)
    status.update({
        'candidate_fingerprint': current_fingerprint,
        'lineage_pair_count': len(lineage),
        'total_versioned_causal_pairs': len(versioned_pairs),
        'unversioned_causal_pairs_ignored': unversioned_causal_pairs,
        'discarded_prior_version_pairs': len(versioned_pairs) - len(lineage),
        'lineage_e_value': lineage_e_value,
        'stored_global_e_value_trusted_for_promotion': False,
        'lineage_reset_on_predictive_architecture_change': True,
        'promotion_lineage_components': list(PROMOTION_LINEAGE_COMPONENTS),
    })
    return status


def promotion_status(ledger: dict[str, Any], gate_path: Path = PRE_3052_GATE_PATH,
                     audit_report_path: Path = P14_AUDIT_REPORT_PATH) -> dict[str, Any]:
    p13 = promotion_eligibility_status(ledger)
    return assess_evidence_only_promotion_from_files(p13, gate_path, audit_report_path)


def _next_version_path(out: Path) -> Path:
    if not out.exists():
        return out
    for v in range(2, 1000):
        candidate = out.with_name(f'{out.stem}.v{v}{out.suffix}')
        if not candidate.exists():
            return candidate
    raise RuntimeError('unable to allocate versioned freeze filename')


def freeze_champion_challenger(data: Path, target: int, out: Path, ledger_path: Path, state_path: Path,
                               start: int = 1000) -> dict[str, Any]:
    implementation_gate = require_pre_3052_gate(target)
    draws, contests = e.load_draws(data)
    if int(contests[-1]) >= int(target):
        raise ValueError('target already present in data; refusing retrospective freeze')
    if int(contests[-1]) != int(target) - 1:
        raise ValueError('data must end immediately before target contest')

    ledger = load_ledger(ledger_path)
    active = active_freeze(ledger, target)
    if any(ev.get('event_type') == 'ADJUDICATION' and int(ev.get('target_contest', -1)) == int(target)
           for ev in ledger.get('events', [])):
        raise ValueError('target already adjudicated; pre-result supersede is closed')

    component_hashes = {
        'engine': sha256(Path('smart_v2_engine.py')),
        'champion_engine': sha256(Path('freeze_next_research.py')),
        'signal_agent': sha256(Path('smart_signal_agent.py')),
        'signal_quality': sha256(Path('smart_signal_quality.py')),
        'signal_weights': sha256(Path('smart_signal_weights.py')),
        'context_regime': sha256(Path('smart_context_regime.py')),
        'redundancy_consensus': sha256(Path('smart_signal_redundancy_consensus.py')),
        'marginal_utility': sha256(Path('smart_signal_marginal_utility.py')),
        'contextual_meta_weights': sha256(Path('smart_contextual_meta_weights.py')),
        'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py')),
        'multi_challengers': sha256(Path('smart_multi_challengers.py')),
        'meta_governor': sha256(Path('smart_meta_governor.py')),
        'bounded_online_learning': sha256(Path('smart_bounded_online_learning.py')),
        'signal_interactions': sha256(Path('smart_signal_interactions.py')),
        'signal_expansion_governance': sha256(Path('smart_signal_expansion_governance.py')),
        'sequential_prospective_proof': sha256(Path('smart_sequential_prospective_proof.py')),
        'promotion_gate': sha256(Path('smart_promotion_gate.py')),
        'independent_audit': sha256(Path('smart_independent_audit.py')),
        'evidence_only_promotion': sha256(Path('smart_evidence_only_promotion.py')),
        'global_integrity': sha256(Path('smart_global_integrity.py')),
        'portfolio_optimizer': sha256(Path('smart_portfolio_optimizer.py')),
        'portfolio_pipeline': sha256(Path('smart_portfolio_pipeline.py')),
    }
    data_hash = sha256(data)
    expansion_governance = load_registry(REGISTRY_PATH, tuple(SIGNAL_NAMES))
    expansion_snapshot = expansion_governance.snapshot()
    expansion_registry_hash = sha256(REGISTRY_PATH) if REGISTRY_PATH.exists() else None
    from smart_sequential_prospective_proof import freeze_snapshot as sequential_freeze_snapshot
    sequential_snapshot = sequential_freeze_snapshot()
    from smart_independent_audit import policy_snapshot as independent_audit_policy_snapshot
    independent_audit_snapshot = independent_audit_policy_snapshot()
    evidence_only_promotion_snapshot = evidence_only_promotion_policy_snapshot()
    from smart_global_integrity import policy_snapshot as global_integrity_policy_snapshot
    global_integrity_snapshot = global_integrity_policy_snapshot()
    global_integrity_ref = None if implementation_gate is None else implementation_gate.get('global_integrity')
    if active:
        same_components = all(str(active.get('hashes', {}).get(k)) == str(v)
                              for k, v in component_hashes.items())
        same_registry = str(active.get('snapshot', {}).get('signal_expansion_governance', {}).get('sha256')) == str(expansion_snapshot.get('sha256'))
        same_start = int(active.get('start_index', -1)) == int(start)
        same_river = str(active.get('river_version', '')) == str(river.__version__)
        if same_components and same_registry and same_start and same_river and str(active.get('data_sha256')) == data_hash:
            fp = Path(active['freeze_file'])
            if fp.exists() and sha256(fp) == active.get('freeze_sha256'):
                return {'status': 'ALREADY_FROZEN_IDENTICAL_EVENT_PRESERVED', 'target_contest': int(target),
                        'freeze_file': str(fp), 'freeze_sha256': active['freeze_sha256'],
                        'promotion': promotion_status(ledger)}

    freeze_time = datetime.now(timezone.utc).isoformat()
    source_ts = source_cutoff_timestamp(data)
    signal_ts = source_ts or freeze_time
    signal_ts_kind = 'source_draw_datetime' if source_ts else 'signal_generation_utc_source_draw_datetime_unavailable'
    champion = champion_engine.current_policy(draws, start=start)
    agent = SmartSignalAgent(start=start)
    promotion_lineage = {
        'schema': PROMOTION_LINEAGE_SCHEMA,
        'start_index': int(start),
        'agent_schema': AGENT_SCHEMA,
        'river_version': str(river.__version__),
        'signal_ids': list(SIGNAL_NAMES),
        'eta': float(agent.eta),
        'redundancy_threshold': float(agent.redundancy_threshold),
        'meta_strength': float(agent.meta_strength),
        'calibration_strength': float(agent.calibration_strength),
        'signal_expansion_registry_snapshot_sha256': expansion_snapshot.get('sha256'),
        'component_hashes': {k: component_hashes[k].lower() for k in PROMOTION_LINEAGE_COMPONENTS},
    }
    promotion_lineage['sha256'] = hashlib.sha256(
        json.dumps(promotion_lineage, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    challenger_pred, challenger_backtest = agent.predict_next(draws, contests, target_contest=target,
                                                               cutoff_timestamp=signal_ts,
                                                               cutoff_timestamp_kind=signal_ts_kind)

    state = agent.state_document(data_sha256=data_hash)
    state.update({'cutoff_contest': int(contests[-1]), 'target_contest': int(target), 'generated_utc': freeze_time,
                  'source_cutoff_timestamp': source_ts, 'signal_cutoff_timestamp': signal_ts,
                  'signal_cutoff_timestamp_kind': signal_ts_kind,
                  'signal_expansion_governance': expansion_snapshot})
    state_hash = write_state(state_path, state)
    state_archive_path = archive_state_snapshot(state_path, state_hash)

    actual_out = _next_version_path(out) if active else out
    freeze_obj = {
        'schema': 'SMART_CHAMPION_CHALLENGER_FREEZE_2', 'target_contest': int(target),
        'cutoff_contest': int(contests[-1]), 'source_cutoff_timestamp': source_ts,
        'signal_cutoff_timestamp': signal_ts, 'signal_cutoff_timestamp_kind': signal_ts_kind,
        'frozen_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,
        'production_switch_performed': False, 'champion_remains_active': True,
        'data_file': str(data), 'data_sha256': data_hash, 'start_index': int(start), 'river_version': river.__version__,
        'engine_sha256': component_hashes['engine'], 'champion_engine_sha256': component_hashes['champion_engine'],
        'signal_agent_sha256': component_hashes['signal_agent'], 'signal_quality_sha256': component_hashes['signal_quality'],
        'signal_weights_sha256': component_hashes['signal_weights'], 'context_regime_sha256': component_hashes['context_regime'],
        'redundancy_consensus_sha256': component_hashes['redundancy_consensus'],
        'marginal_utility_sha256': component_hashes['marginal_utility'],
        'contextual_meta_weights_sha256': component_hashes['contextual_meta_weights'],
        'rank_score_calibration_sha256': component_hashes['rank_score_calibration'],
        'multi_challengers_sha256': component_hashes['multi_challengers'],
        'meta_governor_sha256': component_hashes['meta_governor'],
        'bounded_online_learning_sha256': component_hashes['bounded_online_learning'],
        'signal_interactions_sha256': component_hashes['signal_interactions'],
        'signal_expansion_governance_sha256': component_hashes['signal_expansion_governance'],
        'sequential_prospective_proof_sha256': component_hashes['sequential_prospective_proof'],
        'promotion_gate_sha256': component_hashes['promotion_gate'],
        'independent_audit_sha256': component_hashes['independent_audit'],
        'evidence_only_promotion_sha256': component_hashes['evidence_only_promotion'],
        'global_integrity_sha256': component_hashes['global_integrity'],
        'portfolio_optimizer_sha256': component_hashes['portfolio_optimizer'],
        'portfolio_pipeline_sha256': component_hashes['portfolio_pipeline'],
        'portfolio_policy': {'enabled': True, 'post_scoring_only': True, 'generated_from_frozen_champion_scores': True},
        'global_integrity_proof': global_integrity_ref,
        'signal_expansion_registry_file': str(REGISTRY_PATH),
        'signal_expansion_registry_sha256': expansion_registry_hash,
        'signal_expansion_governance': expansion_snapshot,
        'sequential_prospective_proof': sequential_snapshot,
        'signal_state_file': str(state_path),
        'signal_state_sha256': state_hash,
        'signal_state_archive_file': str(state_archive_path),
        'signal_state_archive_sha256': state_hash,
        'champion': champion, 'challenger': challenger_pred.as_dict(),
        'governed_challenger_top6': challenger_pred.meta_governor['selected_top6'],
        'governed_challenger_policy': challenger_pred.meta_governor['selected_policy'],
        'challenger_historical_walk_forward_summary': {k: v for k, v in challenger_backtest.items() if k != 'rows'},
        'promotion_policy': policy_snapshot(),
        'independent_audit_policy': independent_audit_snapshot,
        'evidence_only_promotion_policy': evidence_only_promotion_snapshot,
        'global_integrity_policy': global_integrity_snapshot,
        'promotion_lineage': promotion_lineage,
    }
    actual_out.write_text(json.dumps(freeze_obj, ensure_ascii=False, indent=2), encoding='utf-8')
    freeze_hash = sha256(actual_out)
    portfolio_out = actual_out.with_name(f'{actual_out.stem}_PORTFOLIO.json')
    portfolio_package = build_portfolio_package(actual_out, portfolio_out)
    portfolio_hash = sha256(portfolio_out)

    new_event = {
        'event_type': 'FREEZE', 'target_contest': int(target), 'cutoff_contest': int(contests[-1]),
        'created_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,
        'start_index': int(start), 'river_version': str(river.__version__),
        'promotion_lineage': promotion_lineage,
        'freeze_file': str(actual_out), 'freeze_sha256': freeze_hash, 'data_sha256': data_hash,
        'state_archive_file': str(state_archive_path), 'state_archive_sha256': state_hash,
        'portfolio_file': str(portfolio_out), 'portfolio_sha256': portfolio_hash,
        'portfolio_status': portfolio_package['status'],
        'portfolio_games': portfolio_package['portfolio']['games'],
        'portfolio_metrics': portfolio_package['portfolio']['metrics'],
        'champion_top6': champion['top6'], 'challenger_top6': freeze_obj['challenger']['top6'],
        'governed_challenger_top6': freeze_obj['governed_challenger_top6'], 'governed_challenger_policy': freeze_obj['governed_challenger_policy'],
        'snapshot': {'raw_signals': freeze_obj['challenger']['raw_signals'], 'quality_metrics': freeze_obj['challenger']['quality_metrics'],
                     'weight_components': freeze_obj['challenger']['weight_components'], 'weights': freeze_obj['challenger']['weights'],
                     'aggregate_scores': freeze_obj['challenger']['aggregate_scores'], 'ranking60': freeze_obj['challenger']['ranking60'],
                     'river_state': freeze_obj['challenger']['river_state'],
                     'redundancy_consensus': freeze_obj['challenger']['redundancy_consensus'], 'signal_interactions': freeze_obj['challenger']['signal_interactions'],
                     'contextual_meta_weights': freeze_obj['challenger']['contextual_meta_weights'],
                     'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration'],
                     'multi_challengers': freeze_obj['challenger']['multi_challengers'],
                     'meta_governor': freeze_obj['challenger']['meta_governor'],
                     'bounded_online_learning': freeze_obj['challenger']['bounded_online_learning'],
                     'signal_expansion_governance': expansion_snapshot,
                     'sequential_prospective_proof': sequential_snapshot,
                     'promotion_policy': freeze_obj['promotion_policy'],
                     'independent_audit_policy': freeze_obj['independent_audit_policy'],
                     'evidence_only_promotion_policy': freeze_obj['evidence_only_promotion_policy'],
                     'global_integrity_policy': freeze_obj['global_integrity_policy'],
                     'global_integrity_proof': global_integrity_ref,
                     'promotion_lineage': promotion_lineage},
        'hashes': {**component_hashes, 'state': state_hash},
    }
    ledger['events'].append(new_event)
    if active:
        ledger['events'].append({
            'event_type': 'SUPERSEDE', 'target_contest': int(target), 'created_utc': freeze_time,
            'old_freeze_sha256': active['freeze_sha256'], 'new_freeze_sha256': freeze_hash,
            'reason': 'pre-result architecture correction; prior artifact preserved; no result used',
            'frozen_before_result': True, 'retroactive_rewrite': False,
        })
    ledger_hash = write_ledger(ledger_path, ledger)
    return {'status': 'FROZEN_SUPERSEDING_PRIOR' if active else 'FROZEN', 'target_contest': int(target),
            'champion_top6': champion['top6'], 'challenger_top6': freeze_obj['challenger']['top6'],
            'governed_challenger_top6': freeze_obj['governed_challenger_top6'], 'governed_challenger_policy': freeze_obj['governed_challenger_policy'],
            'freeze_file': str(actual_out), 'freeze_sha256': freeze_hash,
            'state_archive_file': str(state_archive_path), 'state_archive_sha256': state_hash,
            'portfolio_file': str(portfolio_out), 'portfolio_sha256': portfolio_hash,
            'portfolio_status': portfolio_package['status'],
            'ledger_sha256': ledger_hash,
            'state_sha256': state_hash, 'promotion': promotion_status(ledger)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='Mega-Sena_through_3050.xlsx')
    ap.add_argument('--target', type=int, default=3051)
    ap.add_argument('--out', default='SMART_3051_CHAMPION_CHALLENGER_FREEZE.json')
    ap.add_argument('--ledger', default='SMART_SIGNAL_LEDGER.json')
    ap.add_argument('--state', default='SMART_SIGNAL_STATE.json')
    ap.add_argument('--start', type=int, default=1000)
    a = ap.parse_args()
    print(json.dumps(freeze_champion_challenger(Path(a.data), a.target, Path(a.out), Path(a.ledger), Path(a.state), a.start),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

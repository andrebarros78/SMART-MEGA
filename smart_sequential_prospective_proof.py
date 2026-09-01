from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA = 'SMART_SEQUENTIAL_PROSPECTIVE_PROOF_1'
LEDGER_SCHEMA = 'SMART_SIGNAL_LEDGER_1'
FREEZE_SNAPSHOT_SCHEMA = 'SMART_SEQUENTIAL_PROSPECTIVE_FREEZE_RULES_1'
LEARNING_EVENT = 'LEARNING_UPDATE'
PROOF_EVENT = 'SEQUENTIAL_PROOF'
POST_RESULT_DERIVED = {
    'ATTRIBUTION', 'MARGINAL_UTILITY', 'INTERACTIONS', 'INTERACTIONS_CORRECTION',
    'MULTI_CHALLENGERS', 'META_GOVERNOR', 'RANK_SCORE_CALIBRATION',
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def canonical_event_hash(event: dict[str, Any]) -> str:
    payload = {k: v for k, v in event.items() if k not in {'event_sha256', 'sequence_sha256'}}
    return sha256_json(payload)


def freeze_snapshot() -> dict[str, Any]:
    payload = {
        'schema': FREEZE_SNAPSHOT_SCHEMA,
        'freeze_before_result_required': True,
        'single_active_freeze_required': True,
        'linear_supersede_chain_required': True,
        'supersede_must_immediately_link_new_freeze': True,
        'adjudication_unique_required': True,
        'adjudication_must_reference_active_freeze': True,
        'derived_events_after_adjudication_only': True,
        'learning_after_adjudication_only': True,
        'learning_state_must_end_at_target': True,
        'learning_state_hash_required': True,
        'sequence_proof_after_learning_only': True,
        'append_only_prefix_preservation_required': True,
        'retroactive_rewrite_prohibited': True,
    }
    payload['sha256'] = sha256_json(payload)
    return payload


def _target_events(ledger: dict[str, Any], target: int) -> list[tuple[int, dict[str, Any]]]:
    return [(i, ev) for i, ev in enumerate(ledger.get('events', []))
            if int(ev.get('target_contest', -1)) == int(target)]


def _active_freeze_from_events(events: list[tuple[int, dict[str, Any]]]) -> tuple[int, dict[str, Any]] | None:
    freezes = [(i, ev) for i, ev in events if ev.get('event_type') == 'FREEZE']
    if not freezes:
        return None
    superseded = {str(ev.get('old_freeze_sha256')) for _, ev in events if ev.get('event_type') == 'SUPERSEDE'}
    active = [(i, ev) for i, ev in freezes if str(ev.get('freeze_sha256')) not in superseded]
    if len(active) != 1:
        raise ValueError('sequence requires exactly one active freeze')
    return active[0]


def _is_hex64(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _validate_supersede_chain(events: list[tuple[int, dict[str, Any]]]) -> str:
    active_hash: str | None = None
    pending_new: str | None = None
    seen_freezes: set[str] = set()
    for _, ev in events:
        et = ev.get('event_type')
        if et == 'FREEZE':
            h = str(ev.get('freeze_sha256', ''))
            if not _is_hex64(h) or h in seen_freezes:
                raise ValueError('invalid or duplicate freeze hash in supersede chain')
            if pending_new is not None:
                raise ValueError('new freeze encountered before prior supersede was linked')
            seen_freezes.add(h)
            if active_hash is None:
                active_hash = h
            else:
                pending_new = h
        elif et == 'SUPERSEDE':
            old = str(ev.get('old_freeze_sha256', ''))
            new = str(ev.get('new_freeze_sha256', ''))
            if not _is_hex64(old) or not _is_hex64(new) or old == new:
                raise ValueError('invalid supersede hash linkage')
            if pending_new is None:
                raise ValueError('supersede event requires a preceding new freeze')
            if old != active_hash or new != pending_new:
                raise ValueError('supersede must replace exactly the previously active freeze')
            active_hash = pending_new
            pending_new = None
        elif pending_new is not None:
            raise ValueError('supersede event must immediately link a newly appended freeze')
    if pending_new is not None:
        raise ValueError('new freeze is missing its supersede linkage')
    if active_hash is None:
        raise ValueError('supersede chain requires at least one freeze')
    return active_hash


def _event_chain(events: list[tuple[int, dict[str, Any]]], stop_before_proof: bool = True) -> tuple[list[str], str]:
    hashes = []
    for _, ev in events:
        if stop_before_proof and ev.get('event_type') == PROOF_EVENT:
            continue
        hashes.append(canonical_event_hash(ev))
    return hashes, sha256_json(hashes)


def validate_target_sequence(ledger: dict[str, Any], target: int, *, require_learning: bool = False,
                             require_proof: bool = False, verify_files: bool = False,
                             root: Path = Path('.')) -> dict[str, Any]:
    if not isinstance(ledger, dict) or not isinstance(ledger.get('events'), list):
        raise ValueError('invalid ledger structure')
    events = _target_events(ledger, target)
    chain_active_hash = _validate_supersede_chain(events)
    active = _active_freeze_from_events(events)
    if active is None:
        raise ValueError('sequence requires a frozen prediction')
    active_i, active_fr = active
    if str(active_fr.get('freeze_sha256')) != chain_active_hash:
        raise ValueError('active freeze resolution disagrees with supersede chain')
    freeze_indices = [i for i, ev in events if ev.get('event_type') == 'FREEZE']
    supersede_indices = [i for i, ev in events if ev.get('event_type') == 'SUPERSEDE']
    adjud = [(i, ev) for i, ev in events if ev.get('event_type') == 'ADJUDICATION']
    learning = [(i, ev) for i, ev in events if ev.get('event_type') == LEARNING_EVENT]
    proofs = [(i, ev) for i, ev in events if ev.get('event_type') == PROOF_EVENT]
    derived = [(i, ev) for i, ev in events if ev.get('event_type') in POST_RESULT_DERIVED]

    if len(adjud) > 1:
        raise ValueError('sequence refuses duplicate adjudication')
    if len(learning) > 1:
        raise ValueError('sequence refuses duplicate learning update')
    if len(proofs) > 1:
        raise ValueError('sequence refuses duplicate sequential proof')
    if require_learning and len(learning) != 1:
        raise ValueError('sequence requires exactly one learning update')
    if require_proof and len(proofs) != 1:
        raise ValueError('sequence requires exactly one sequential proof')

    if adjud:
        adj_i, adj = adjud[0]
        if adj_i <= active_i:
            raise ValueError('adjudication must occur after active freeze')
        if any(i >= adj_i for i in freeze_indices + supersede_indices):
            raise ValueError('freeze/supersede cannot occur after adjudication')
        if str(adj.get('freeze_sha256')) != str(active_fr.get('freeze_sha256')):
            raise ValueError('adjudication must reference active freeze hash')
        for i, _ in derived:
            if i <= adj_i:
                raise ValueError('derived post-result event cannot predate adjudication')
    elif derived or learning or proofs:
        raise ValueError('post-result sequence event exists without adjudication')

    if learning:
        learn_i, learn = learning[0]
        adj_i, adj = adjud[0]
        if learn_i <= adj_i:
            raise ValueError('learning must occur after adjudication')
        if derived and learn_i <= max(i for i, _ in derived):
            raise ValueError('learning must occur after post-result evaluation events')
        if str(learn.get('source_adjudication_sha256')) != canonical_event_hash(adj):
            raise ValueError('learning does not bind to adjudication event')
        if int(learn.get('trained_through_contest', -1)) != int(target):
            raise ValueError('learning state must end at target contest')
        if learn.get('learning_after_adjudication') is not True or learn.get('retroactive_rewrite') is not False:
            raise ValueError('learning governance flags invalid')
        if verify_files:
            state_path = Path(learn['state_file'])
            if not state_path.is_absolute():
                state_path = Path(root) / state_path
            if not state_path.is_file() or sha256_file(state_path) != learn.get('state_sha256'):
                raise ValueError('learning state hash mismatch')

    if proofs:
        proof_i, proof = proofs[0]
        if not learning:
            raise ValueError('sequential proof requires prior learning')
        if proof_i <= learning[0][0]:
            raise ValueError('sequential proof must occur after learning')
        prior = [(i, ev) for i, ev in events if i < proof_i]
        hashes, chain = _event_chain(prior)
        if proof.get('sequence_sha256') != chain or proof.get('event_hashes') != hashes:
            raise ValueError('sequential proof chain mismatch')

    if verify_files:
        fp = Path(active_fr['freeze_file'])
        if not fp.is_absolute():
            fp = Path(root) / fp
        if not fp.is_file() or sha256_file(fp) != active_fr.get('freeze_sha256'):
            raise ValueError('active freeze hash mismatch')

    _, chain = _event_chain(events)
    return {
        'schema': SCHEMA,
        'target_contest': int(target),
        'event_count': len(events),
        'freeze_count': len(freeze_indices),
        'supersede_count': len(supersede_indices),
        'adjudicated': bool(adjud),
        'derived_event_count': len(derived),
        'learning_recorded': bool(learning),
        'proof_recorded': bool(proofs),
        'active_freeze_sha256': active_fr.get('freeze_sha256'),
        'sequence_sha256': chain,
        'valid': True,
    }


def _load_ledger(path: Path) -> dict[str, Any]:
    p=Path(path)
    if not p.is_file():
        return {'schema': LEDGER_SCHEMA, 'events': []}
    obj=json.loads(p.read_text(encoding='utf-8'))
    if obj.get('schema')!=LEDGER_SCHEMA or not isinstance(obj.get('events'),list):
        raise ValueError('invalid SMART signal ledger')
    return obj


def _write_ledger(path: Path, ledger: dict[str, Any]) -> str:
    Path(path).write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    return sha256_file(Path(path))


def append_learning_update(ledger_path: Path, target: int, state_file: Path,
                           canonical_data: Path | None = None) -> dict[str, Any]:
    ledger_path = Path(ledger_path)
    ledger = _load_ledger(ledger_path)
    validate_target_sequence(ledger, target, require_learning=False)
    events = _target_events(ledger, target)
    if any(ev.get('event_type') == LEARNING_EVENT for _, ev in events):
        raise ValueError('learning update already recorded')
    adjud = [(i, ev) for i, ev in events if ev.get('event_type') == 'ADJUDICATION']
    if len(adjud) != 1:
        raise ValueError('learning requires exactly one adjudication')
    state_file = Path(state_file)
    if not state_file.is_file():
        raise ValueError('learning state file missing')
    state = json.loads(state_file.read_text(encoding='utf-8'))
    if not str(state.get('schema', '')).startswith('SMART_SIGNAL_STATE_'):
        raise ValueError('invalid learning state schema')
    if int(state.get('last_contest', -1)) != int(target):
        raise ValueError('learning state must be trained exactly through target')
    data_sha = None
    if canonical_data is not None:
        canonical_data = Path(canonical_data)
        if not canonical_data.is_file():
            raise ValueError('canonical learning data missing')
        df = pd.read_excel(canonical_data)
        if 'Concurso' not in df.columns or len(df) == 0 or int(df.iloc[-1]['Concurso']) != int(target):
            raise ValueError('canonical learning data must end at target contest')
        data_sha = sha256_file(canonical_data)
    before_hash = sha256_file(ledger_path) if ledger_path.exists() else None
    adj = adjud[0][1]
    event = {
        'event_type': LEARNING_EVENT,
        'target_contest': int(target),
        'source_adjudication_sha256': canonical_event_hash(adj),
        'source_freeze_sha256': adj.get('freeze_sha256'),
        'state_file': str(state_file),
        'state_sha256': sha256_file(state_file),
        'canonical_data_file': None if canonical_data is None else str(canonical_data),
        'canonical_data_sha256': data_sha,
        'trained_through_contest': int(target),
        'learning_after_adjudication': True,
        'uses_target_result_only_after_adjudication': True,
        'retroactive_rewrite': False,
        'ledger_sha256_before_append': before_hash,
    }
    event['event_sha256'] = canonical_event_hash(event)
    prefix = json.loads(json.dumps(ledger.get('events', [])))
    ledger['events'].append(event)
    if ledger['events'][:len(prefix)] != prefix:
        raise RuntimeError('append-only prefix changed during learning append')
    ledger_hash = _write_ledger(ledger_path, ledger)
    return {'status': 'LEARNING_RECORDED', 'target_contest': int(target), 'event_sha256': event['event_sha256'],
            'state_sha256': event['state_sha256'], 'ledger_sha256': ledger_hash}


def append_sequence_proof(ledger_path: Path, target: int) -> dict[str, Any]:
    ledger_path = Path(ledger_path)
    ledger = _load_ledger(ledger_path)
    validate_target_sequence(ledger, target, require_learning=True)
    events = _target_events(ledger, target)
    if any(ev.get('event_type') == PROOF_EVENT for _, ev in events):
        raise ValueError('sequential proof already recorded')
    hashes, chain = _event_chain(events)
    event = {
        'event_type': PROOF_EVENT,
        'target_contest': int(target),
        'schema': SCHEMA,
        'event_hashes': hashes,
        'sequence_sha256': chain,
        'freeze_to_adjudication_to_learning_verified': True,
        'append_only_verified': True,
        'retroactive_rewrite': False,
    }
    event['event_sha256'] = canonical_event_hash(event)
    prefix = json.loads(json.dumps(ledger.get('events', [])))
    ledger['events'].append(event)
    if ledger['events'][:len(prefix)] != prefix:
        raise RuntimeError('append-only prefix changed during proof append')
    ledger_hash = _write_ledger(ledger_path, ledger)
    final = validate_target_sequence(ledger, target, require_learning=True, require_proof=True)
    return {'status': 'SEQUENCE_PROVEN', 'target_contest': int(target), 'event_sha256': event['event_sha256'],
            'sequence_sha256': chain, 'ledger_sha256': ledger_hash, 'validation': final}

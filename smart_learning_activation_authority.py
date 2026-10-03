from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_learning_activation_gate import ActivationDecision
from smart_source_identity import sha256_source_file

SCHEMA = 'SMART_LEARNING_ACTIVATION_AUTHORITY_1'
MATERIALITY_SCHEMA = 'SMART_DECISION_MATERIALITY_1'
DEFAULT_PATH = Path('SMART_LEARNING_ACTIVATION_AUTHORITY.json')
COMPONENTS = {
    'learning_activation_gate': 'smart_learning_activation_gate.py',
    'signal_agent': 'smart_signal_agent.py',
    'marginal_utility': 'smart_signal_marginal_utility.py',
    'meta_governor': 'smart_meta_governor.py',
    'multi_challengers': 'smart_multi_challengers.py',
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _is_hex64(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def build_materiality_evidence(*, decision_change_count: int, validation_gain: float, holdout_gain: float,
                               global_gain: float, independent_holdout: bool = True, leakage_free: bool = True) -> dict[str, Any]:
    obj = {
        'schema': MATERIALITY_SCHEMA,
        'decision_change_count': decision_change_count,
        'validation_gain': float(validation_gain),
        'holdout_gain': float(holdout_gain),
        'global_gain': float(global_gain),
        'independent_holdout': independent_holdout,
        'leakage_free': leakage_free,
    }
    _validate_materiality_evidence(obj, require_hash=False)
    obj['sha256'] = _sha256_json(obj)
    return obj


def _validate_materiality_evidence(value: Any, *, require_hash: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get('schema') != MATERIALITY_SCHEMA:
        raise ValueError('decision materiality evidence missing or invalid')
    count = value.get('decision_change_count')
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError('decision materiality requires at least one changed decision')
    gains = []
    for key in ('validation_gain', 'holdout_gain', 'global_gain'):
        x = value.get(key)
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
            raise ValueError(f'decision materiality {key} must be finite')
        if float(x) < 0.0:
            raise ValueError(f'decision materiality {key} regresses baseline')
        gains.append(float(x))
    if max(gains) <= 0.0:
        raise ValueError('decision materiality requires positive gain on at least one declared partition')
    if value.get('independent_holdout') is not True:
        raise ValueError('decision materiality requires independent holdout')
    if value.get('leakage_free') is not True:
        raise ValueError('decision materiality requires leakage-free evidence')
    if require_hash:
        observed = value.get('sha256')
        canonical = dict(value); canonical.pop('sha256', None)
        if not _is_hex64(observed) or observed.lower() != _sha256_json(canonical):
            raise ValueError('decision materiality evidence self-hash invalid')
    return value


@dataclass(frozen=True)
class ActivationRuntimeConfig:
    enabled: bool
    marginal_strength: float
    allow_meta_alternate_selection: bool
    decision: ActivationDecision | None
    authority: dict[str, Any]


def _disabled(reason: str, path: Path, target: int) -> ActivationRuntimeConfig:
    return ActivationRuntimeConfig(
        enabled=False,
        marginal_strength=0.0,
        allow_meta_alternate_selection=False,
        decision=None,
        authority={
            'schema': SCHEMA,
            'status': 'FAIL_CLOSED_INACTIVE',
            'target_contest': int(target),
            'authority_file': str(path),
            'reason': reason,
            'predictive_weight_authorized': False,
        },
    )


def build_authority(*, target_contest: int, decision: ActivationDecision, evidence_sha256: str,
                    marginal_strength: float = 0.0, allow_meta_alternate_selection: bool = False,
                    materiality_evidence: dict[str, Any] | None = None, root: Path = Path('.')) -> dict[str, Any]:
    target = int(target_contest)
    if target < 1:
        raise ValueError('target_contest must be positive')
    if not isinstance(decision, ActivationDecision):
        raise ValueError('ActivationDecision required')
    if decision.status != 'ELIGIBLE_FOR_BOUNDED_PROMOTION' or decision.predictive_weight_authorized is not True:
        raise ValueError('activation authority requires prospective predictive-weight authorization')
    strength = float(marginal_strength)
    if not math.isfinite(strength) or not 0.0 <= strength <= 1.0:
        raise ValueError('marginal_strength must be finite in [0,1]')
    allow_meta = bool(allow_meta_alternate_selection)
    if strength <= 0.0 and not allow_meta:
        raise ValueError('activation authority must enable at least one bounded mechanism')
    if not _is_hex64(evidence_sha256):
        raise ValueError('evidence_sha256 must be 64-hex')
    materiality = _validate_materiality_evidence(materiality_evidence)
    root = Path(root).resolve()
    component_hashes = {}
    for key, name in COMPONENTS.items():
        p = root / name
        if not p.is_file():
            raise ValueError(f'activation component missing: {name}')
        component_hashes[key] = sha256_source_file(p)
    obj = {
        'schema': SCHEMA,
        'status': 'AUTHORIZED',
        'target_contest': target,
        'activation_decision': decision.to_dict(),
        'marginal_strength': strength,
        'allow_meta_alternate_selection': allow_meta,
        'evidence_sha256': evidence_sha256.lower(),
        'materiality_evidence': materiality,
        'component_hashes': component_hashes,
        'single_target_authority': True,
        'future_targets_require_new_authority': True,
        'manual_override_prohibited': True,
    }
    obj['sha256'] = _sha256_json(obj)
    return obj


def load_activation_authority(path: Path = DEFAULT_PATH, *, target_contest: int,
                              root: Path = Path('.')) -> ActivationRuntimeConfig:
    path = Path(path)
    target = int(target_contest)
    if not path.is_file():
        return _disabled('activation authority file absent', path, target)
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or obj.get('schema') != SCHEMA:
        raise ValueError('invalid learning activation authority schema')
    observed = obj.get('sha256')
    canonical = dict(obj)
    canonical.pop('sha256', None)
    if not _is_hex64(observed) or observed.lower() != _sha256_json(canonical):
        raise ValueError('learning activation authority self-hash invalid')
    if obj.get('status') != 'AUTHORIZED' or obj.get('single_target_authority') is not True:
        raise ValueError('learning activation authority is not active')
    if isinstance(obj.get('target_contest'), bool) or not isinstance(obj.get('target_contest'), int) or obj['target_contest'] != target:
        raise ValueError('learning activation authority target mismatch')
    if not _is_hex64(obj.get('evidence_sha256')):
        raise ValueError('learning activation authority evidence hash invalid')
    _validate_materiality_evidence(obj.get('materiality_evidence'))
    decision_obj = obj.get('activation_decision')
    if not isinstance(decision_obj, dict):
        raise ValueError('learning activation decision missing')
    try:
        decision = ActivationDecision(
            status=str(decision_obj['status']),
            predictive_weight_authorized=decision_obj['predictive_weight_authorized'],
            prospective_challenger_authorized=decision_obj['prospective_challenger_authorized'],
            reason=str(decision_obj['reason']),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError('learning activation decision malformed') from exc
    if not isinstance(decision.predictive_weight_authorized, bool) or not isinstance(decision.prospective_challenger_authorized, bool):
        raise ValueError('learning activation decision booleans invalid')
    if decision.status != 'ELIGIBLE_FOR_BOUNDED_PROMOTION' or decision.predictive_weight_authorized is not True:
        raise ValueError('learning activation decision is not production-authorized')
    strength = obj.get('marginal_strength')
    if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(float(strength)) or not 0.0 <= float(strength) <= 1.0:
        raise ValueError('learning activation marginal strength invalid')
    allow_meta = obj.get('allow_meta_alternate_selection')
    if not isinstance(allow_meta, bool):
        raise ValueError('learning activation meta flag invalid')
    if float(strength) <= 0.0 and not allow_meta:
        raise ValueError('learning activation authority enables no mechanism')
    component_hashes = obj.get('component_hashes')
    if not isinstance(component_hashes, dict) or set(component_hashes) != set(COMPONENTS):
        raise ValueError('learning activation component hashes incomplete')
    root = Path(root).resolve()
    for key, name in COMPONENTS.items():
        p = root / name
        if not p.is_file() or component_hashes.get(key) != sha256_source_file(p):
            raise ValueError(f'learning activation component hash stale: {key}')
    return ActivationRuntimeConfig(
        enabled=True,
        marginal_strength=float(strength),
        allow_meta_alternate_selection=allow_meta,
        decision=decision,
        authority=obj,
    )


def write_authority(path: Path, authority: dict[str, Any]) -> str:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'refusing to overwrite activation authority: {path}')
    canonical = dict(authority)
    observed = canonical.pop('sha256', None)
    if not _is_hex64(observed) or observed.lower() != _sha256_json(canonical):
        raise ValueError('activation authority must be self-hashed before write')
    path.write_text(json.dumps(authority, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return _sha256_file(path)


__all__ = ['SCHEMA', 'MATERIALITY_SCHEMA', 'DEFAULT_PATH', 'ActivationRuntimeConfig', 'build_materiality_evidence', 'build_authority', 'load_activation_authority', 'write_authority']

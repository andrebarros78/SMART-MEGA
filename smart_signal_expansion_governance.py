from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = 'SMART_SIGNAL_EXPANSION_GOVERNANCE_1'
REGISTRY_SCHEMA = 'SMART_SIGNAL_EXPANSION_REGISTRY_1'
AUTHORIZATION_PROOF_SCHEMA = 'SMART_SIGNAL_EXPANSION_AUTHORIZATION_PROOF_1'
REGISTRY_PATH = Path('SMART_SIGNAL_EXPANSION_REGISTRY.json')
MIN_CALIBRATION_OOS = 150
MIN_VALIDATION_OOS = 100
MIN_TOTAL_OOS = MIN_CALIBRATION_OOS + MIN_VALIDATION_OOS
MIN_MEAN_DELTA_HITS = 0.0
MIN_VALIDATION_LCB = 0.0
MIN_MEAN_NOVELTY = 0.25
LCB_Z = 1.96
MAX_LIMITED_CHALLENGER_WEIGHT = 0.05


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hex64(value: str) -> bool:
    return bool(re.fullmatch(r'[0-9a-fA-F]{64}', str(value)))


def _verify_embedded_sha256(obj: dict[str, Any], label: str) -> None:
    observed = obj.get('sha256')
    if not _hex64(str(observed or '')):
        raise ValueError(f'{label} sha256 missing or invalid')
    canonical = dict(obj)
    canonical.pop('sha256', None)
    if str(observed).lower() != sha256_json(canonical):
        raise ValueError(f'{label} sha256 mismatch')


def _rules() -> dict[str, Any]:
    return {
        'new_signals_start_shadow_only': True,
        'marginal_oos_required_before_material_influence': True,
        'validation_partition_required': True,
        'automatic_material_influence': False,
        'explicit_authorization_required': True,
        'authorization_bound_to_current_candidate_evidence': True,
        'scope_after_authorization': 'CHALLENGER_ONLY',
        'champion_influence_prohibited': True,
        'max_limited_challenger_weight': MAX_LIMITED_CHALLENGER_WEIGHT,
        'registry_embedded_hash_required': True,
        'candidate_snapshot_hash_required': True,
        'tampered_authorization_state_rejected_on_load': True,
    }


def _float_equal(a: Any, b: Any, tol: float = 1e-12) -> bool:
    try:
        af = float(a); bf = float(b)
    except (TypeError, ValueError, OverflowError):
        return False
    if math.isinf(af) or math.isinf(bf):
        return af == bf
    return math.isclose(af, bf, rel_tol=tol, abs_tol=tol)


@dataclass
class CandidateSignalState:
    candidate_id: str
    family: str
    registered_cutoff: int
    calibration_observations: int = 0
    validation_observations: int = 0
    total_observations: int = 0
    sum_delta_hits: float = 0.0
    m2_delta_hits: float = 0.0
    validation_sum_delta_hits: float = 0.0
    validation_m2_delta_hits: float = 0.0
    novelty_sum: float = 0.0
    last_contest: int | None = None
    authorized_proof_sha256: str | None = None
    material_weight_cap: float = 0.0
    status: str = 'SHADOW_CHALLENGER'

    def __post_init__(self) -> None:
        self.candidate_id = str(self.candidate_id).strip()
        self.family = str(self.family).strip()
        self.registered_cutoff = int(self.registered_cutoff)
        if not self.candidate_id or not self.family:
            raise ValueError('candidate_id and family are required')
        if self.registered_cutoff < 0:
            raise ValueError('registered_cutoff must be >= 0')

    @staticmethod
    def _welford(n: int, mean: float, m2: float, value: float) -> tuple[float, float]:
        n2 = n + 1
        delta = value - mean
        mean2 = mean + delta / n2
        return mean2, m2 + delta * (value - mean2)

    def observe_oos(self, contest: int, marginal_delta_hits: float, novelty: float) -> dict[str, Any]:
        contest = int(contest)
        delta = float(marginal_delta_hits)
        novelty = float(novelty)
        if contest <= self.registered_cutoff or (self.last_contest is not None and contest <= self.last_contest):
            raise ValueError('candidate OOS observations must be strictly causal and increasing')
        if not math.isfinite(delta) or delta < -6.0 or delta > 6.0:
            raise ValueError('marginal_delta_hits must be finite in [-6,6]')
        if not math.isfinite(novelty) or not 0.0 <= novelty <= 1.0:
            raise ValueError('novelty must be finite in [0,1]')
        old_n = self.total_observations
        old_mean = self.sum_delta_hits / old_n if old_n else 0.0
        new_mean, self.m2_delta_hits = self._welford(old_n, old_mean, self.m2_delta_hits, delta)
        self.total_observations += 1
        self.sum_delta_hits = new_mean * self.total_observations
        partition = 'calibration' if self.calibration_observations < MIN_CALIBRATION_OOS else 'validation'
        if partition == 'calibration':
            self.calibration_observations += 1
        else:
            vn = self.validation_observations
            vm = self.validation_sum_delta_hits / vn if vn else 0.0
            vm2, self.validation_m2_delta_hits = self._welford(vn, vm, self.validation_m2_delta_hits, delta)
            self.validation_observations += 1
            self.validation_sum_delta_hits = vm2 * self.validation_observations
        self.novelty_sum += novelty
        self.last_contest = contest
        authorization_revoked = self.status == 'LIMITED_CHALLENGER_AUTHORIZED'
        if authorization_revoked:
            self.authorized_proof_sha256 = None
            self.material_weight_cap = 0.0
        self.status = 'EVIDENCE_ELIGIBLE' if self.evaluation()['eligible_for_material_challenger_influence'] else 'SHADOW_CHALLENGER'
        return {'contest': contest, 'partition': partition, 'delta_hits': delta, 'novelty': novelty,
                'update_after_result_only': True, 'authorization_revoked_due_new_evidence': authorization_revoked,
                'status_after': self.status}

    def evaluation(self) -> dict[str, Any]:
        n = self.total_observations
        vn = self.validation_observations
        mean = self.sum_delta_hits / n if n else 0.0
        val_mean = self.validation_sum_delta_hits / vn if vn else 0.0
        val_std = math.sqrt(self.validation_m2_delta_hits / (vn - 1)) if vn > 1 else 0.0
        val_lcb = val_mean - LCB_Z * val_std / math.sqrt(vn) if vn > 1 else float('-inf')
        novelty = self.novelty_sum / n if n else 0.0
        checks = {
            'minimum_total_oos': n >= MIN_TOTAL_OOS,
            'minimum_calibration_oos': self.calibration_observations >= MIN_CALIBRATION_OOS,
            'minimum_validation_oos': vn >= MIN_VALIDATION_OOS,
            'positive_total_marginal_utility': mean > MIN_MEAN_DELTA_HITS,
            'positive_validation_marginal_utility': val_mean > MIN_MEAN_DELTA_HITS,
            'validation_lcb_positive': val_lcb > MIN_VALIDATION_LCB,
            'novelty_sufficient': novelty >= MIN_MEAN_NOVELTY,
        }
        eligible = all(checks.values())
        return {
            'candidate_id': self.candidate_id, 'family': self.family, 'status': self.status,
            'total_oos': n, 'calibration_oos': self.calibration_observations, 'validation_oos': vn,
            'mean_delta_hits': mean, 'validation_mean_delta_hits': val_mean,
            'validation_std_delta_hits': val_std, 'validation_lcb95_delta_hits': val_lcb,
            'mean_novelty': novelty, 'checks': checks,
            'eligible_for_material_challenger_influence': bool(eligible),
            'automatic_material_influence': False,
            'champion_influence_prohibited': True,
            'max_limited_challenger_weight': MAX_LIMITED_CHALLENGER_WEIGHT,
        }

    def authorization_proof(self) -> dict[str, Any]:
        ev = self.evaluation()
        if not ev['eligible_for_material_challenger_influence']:
            raise ValueError('candidate lacks required causal OOS marginal evidence')
        evidence = {
            'candidate_id': self.candidate_id,
            'family': self.family,
            'registered_cutoff': self.registered_cutoff,
            'last_contest': self.last_contest,
            'total_oos': ev['total_oos'],
            'calibration_oos': ev['calibration_oos'],
            'validation_oos': ev['validation_oos'],
            'mean_delta_hits': ev['mean_delta_hits'],
            'validation_mean_delta_hits': ev['validation_mean_delta_hits'],
            'validation_lcb95_delta_hits': ev['validation_lcb95_delta_hits'],
            'mean_novelty': ev['mean_novelty'],
            'checks': ev['checks'],
        }
        payload = {
            'schema': AUTHORIZATION_PROOF_SCHEMA,
            'candidate_evidence': evidence,
            'scope': 'CHALLENGER_ONLY',
            'champion_influence': False,
            'material_weight_cap': MAX_LIMITED_CHALLENGER_WEIGHT,
        }
        payload['sha256'] = sha256_json(payload)
        return payload

    def authorize_material_influence(self, proof: dict[str, Any] | str) -> dict[str, Any]:
        expected = self.authorization_proof()
        if isinstance(proof, dict):
            _verify_embedded_sha256(proof, 'authorization proof')
            if proof != expected:
                raise ValueError('authorization proof does not match current candidate evidence')
            proof_sha256 = str(proof['sha256'])
        else:
            proof_sha256 = str(proof).lower()
            if not _hex64(proof_sha256) or proof_sha256 != expected['sha256']:
                raise ValueError('authorization proof hash does not match current candidate evidence')
        self.authorized_proof_sha256 = proof_sha256
        self.material_weight_cap = MAX_LIMITED_CHALLENGER_WEIGHT
        self.status = 'LIMITED_CHALLENGER_AUTHORIZED'
        return {'candidate_id': self.candidate_id, 'status': self.status,
                'material_weight_cap': self.material_weight_cap,
                'scope': 'CHALLENGER_ONLY', 'champion_influence': False,
                'proof_sha256': self.authorized_proof_sha256}

    def assert_material_use_allowed(self, requested_weight: float) -> None:
        w = float(requested_weight)
        if self.status != 'LIMITED_CHALLENGER_AUTHORIZED':
            raise ValueError('candidate material influence is not authorized')
        if not _hex64(str(self.authorized_proof_sha256 or '')):
            raise ValueError('candidate authorization proof is missing or invalid')
        if not math.isfinite(w) or w < 0.0 or w > self.material_weight_cap + 1e-15:
            raise ValueError('requested candidate weight exceeds authorized cap')

    def snapshot(self) -> dict[str, Any]:
        payload = {**self.evaluation(), 'registered_cutoff': self.registered_cutoff,
                   'last_contest': self.last_contest, 'authorized_proof_sha256': self.authorized_proof_sha256,
                   'material_weight_cap': self.material_weight_cap,
                   'm2_delta_hits': self.m2_delta_hits,
                   'validation_m2_delta_hits': self.validation_m2_delta_hits,
                   'novelty_sum': self.novelty_sum,
                   'policy': 'shadow first; causal marginal OOS proof; explicit limited authorization; Challenger only'}
        payload['sha256'] = sha256_json(payload)
        return payload


@dataclass
class SignalExpansionGovernance:
    reserved_signal_ids: tuple[str, ...] = ()
    candidates: dict[str, CandidateSignalState] = field(default_factory=dict)

    def register(self, candidate_id: str, family: str, registered_cutoff: int) -> CandidateSignalState:
        cid = str(candidate_id).strip()
        if cid in self.reserved_signal_ids:
            raise ValueError('candidate id collides with an existing canonical signal')
        if cid in self.candidates:
            raise ValueError('candidate already registered')
        state = CandidateSignalState(cid, family, registered_cutoff)
        self.candidates[cid] = state
        return state

    def observe_oos(self, candidate_id: str, contest: int, marginal_delta_hits: float, novelty: float) -> dict[str, Any]:
        if candidate_id not in self.candidates:
            raise ValueError('unknown signal candidate')
        return self.candidates[candidate_id].observe_oos(contest, marginal_delta_hits, novelty)

    def authorize(self, candidate_id: str, proof: dict[str, Any] | str) -> dict[str, Any]:
        if candidate_id not in self.candidates:
            raise ValueError('unknown signal candidate')
        return self.candidates[candidate_id].authorize_material_influence(proof)

    def snapshot(self) -> dict[str, Any]:
        payload = {
            'schema': SCHEMA,
            'registry_schema': REGISTRY_SCHEMA,
            'candidate_count': len(self.candidates),
            'reserved_signal_ids': list(self.reserved_signal_ids),
            'candidates': {k: self.candidates[k].snapshot() for k in sorted(self.candidates)},
            'rules': _rules(),
        }
        payload['sha256'] = sha256_json(payload)
        return payload


def write_registry(path: Path, governance: SignalExpansionGovernance) -> str:
    obj = governance.snapshot()
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    return sha256_file(Path(path))


def _validate_rehydrated_candidate(st: CandidateSignalState, row: dict[str, Any]) -> None:
    if st.total_observations < 0 or st.calibration_observations < 0 or st.validation_observations < 0:
        raise ValueError('candidate registry observation counts must be non-negative')
    if st.total_observations != st.calibration_observations + st.validation_observations:
        raise ValueError('candidate registry observation counts are inconsistent')
    if st.calibration_observations > MIN_CALIBRATION_OOS:
        raise ValueError('candidate registry calibration partition exceeds fixed calibration size')
    if st.validation_observations and st.calibration_observations != MIN_CALIBRATION_OOS:
        raise ValueError('candidate registry validation cannot precede complete calibration partition')
    if st.total_observations == 0 and st.last_contest is not None:
        raise ValueError('candidate registry last_contest invalid without observations')
    if st.total_observations > 0:
        if st.last_contest is None or int(st.last_contest) <= st.registered_cutoff:
            raise ValueError('candidate registry last_contest invalid')
    ev = st.evaluation()
    comparable = (
        'total_oos','calibration_oos','validation_oos','mean_delta_hits','validation_mean_delta_hits',
        'validation_std_delta_hits','validation_lcb95_delta_hits','mean_novelty',
        'eligible_for_material_challenger_influence','automatic_material_influence','champion_influence_prohibited',
        'max_limited_challenger_weight'
    )
    for key in comparable:
        if key not in row:
            raise ValueError(f'candidate registry missing evidence field: {key}')
        if isinstance(ev[key], float):
            if not _float_equal(row[key], ev[key]):
                raise ValueError(f'candidate registry evidence mismatch: {key}')
        elif row[key] != ev[key]:
            raise ValueError(f'candidate registry evidence mismatch: {key}')
    if row.get('checks') != ev['checks']:
        raise ValueError('candidate registry eligibility checks mismatch')
    eligible = bool(ev['eligible_for_material_challenger_influence'])
    if st.status == 'SHADOW_CHALLENGER':
        if eligible or st.authorized_proof_sha256 is not None or abs(st.material_weight_cap) > 1e-15:
            raise ValueError('candidate shadow authorization state is inconsistent')
    elif st.status == 'EVIDENCE_ELIGIBLE':
        if not eligible or st.authorized_proof_sha256 is not None or abs(st.material_weight_cap) > 1e-15:
            raise ValueError('candidate evidence-eligible authorization state is inconsistent')
    elif st.status == 'LIMITED_CHALLENGER_AUTHORIZED':
        if not eligible or not _hex64(str(st.authorized_proof_sha256 or '')):
            raise ValueError('candidate authorized state lacks valid causal evidence/proof')
        expected = st.authorization_proof()['sha256']
        if str(st.authorized_proof_sha256).lower() != expected:
            raise ValueError('candidate authorized proof no longer matches current evidence')
        if not _float_equal(st.material_weight_cap, MAX_LIMITED_CHALLENGER_WEIGHT):
            raise ValueError('candidate authorized material cap mismatch')
    else:
        raise ValueError('unknown candidate registry status')


def load_registry(path: Path, reserved_signal_ids: tuple[str, ...] = ()) -> SignalExpansionGovernance:
    p = Path(path)
    gov = SignalExpansionGovernance(tuple(reserved_signal_ids))
    if not p.is_file():
        return gov
    obj = json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError('invalid signal expansion registry document')
    if obj.get('schema') != SCHEMA or obj.get('registry_schema') != REGISTRY_SCHEMA:
        raise ValueError('invalid signal expansion registry schema')
    _verify_embedded_sha256(obj, 'signal expansion registry')
    stored_reserved = tuple(obj.get('reserved_signal_ids', []))
    if stored_reserved != tuple(reserved_signal_ids):
        raise ValueError('signal expansion registry canonical signal set mismatch')
    candidates = obj.get('candidates')
    if not isinstance(candidates, dict):
        raise ValueError('signal expansion registry candidates must be an object')
    if int(obj.get('candidate_count', -1)) != len(candidates):
        raise ValueError('signal expansion registry candidate_count mismatch')
    if obj.get('rules') != _rules():
        raise ValueError('signal expansion registry rules mismatch')
    for cid, row in candidates.items():
        if not isinstance(row, dict):
            raise ValueError('candidate registry row must be an object')
        _verify_embedded_sha256(row, f'candidate {cid}')
        st = gov.register(cid, row['family'], int(row['registered_cutoff']))
        st.total_observations = int(row['total_oos'])
        st.calibration_observations = int(row['calibration_oos'])
        st.validation_observations = int(row['validation_oos'])
        st.sum_delta_hits = float(row['mean_delta_hits']) * st.total_observations
        st.m2_delta_hits = float(row.get('m2_delta_hits', 0.0))
        st.validation_sum_delta_hits = float(row['validation_mean_delta_hits']) * st.validation_observations
        st.validation_m2_delta_hits = float(row.get('validation_m2_delta_hits', float(row['validation_std_delta_hits']) ** 2 * max(0, st.validation_observations - 1)))
        st.novelty_sum = float(row.get('novelty_sum', float(row['mean_novelty']) * st.total_observations))
        st.last_contest = row.get('last_contest')
        st.authorized_proof_sha256 = row.get('authorized_proof_sha256')
        st.material_weight_cap = float(row.get('material_weight_cap', 0.0))
        st.status = str(row.get('status', 'SHADOW_CHALLENGER'))
        _validate_rehydrated_candidate(st, row)
    return gov

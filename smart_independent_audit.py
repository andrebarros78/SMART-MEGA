from __future__ import annotations







import ast



import hashlib



import json



import math



from datetime import datetime



from pathlib import Path



from typing import Any, Iterable







import pandas as pd







import smart_v2_engine as engine



import freeze_next_research as champion_engine



from smart_signal_agent import SmartSignalAgent

from smart_independent_oracle import validate_frozen_decision, validate_prediction_snapshot

from smart_material_deficiency_registry import load_registry as load_material_deficiency_registry
from smart_source_identity import sha256_source_file







SCHEMA = 'SMART_INDEPENDENT_AUDIT_1'



COVERAGE_BINDING_SCHEMA = 'SMART_COVERAGE_BINDING_1'



LEDGER_SCHEMA = 'SMART_SIGNAL_LEDGER_1'



E_BET_LAMBDA = 0.25



LEGACY_CONTINUITY_SCHEMA = 'SMART_P14_LEGACY_RESULT_CONTINUITY_1'



LEGACY_CONTINUITY_TARGET = 3051



PROMOTION_LINEAGE_SCHEMA = 'SMART_PROMOTION_LINEAGE_1'

LEGACY_MUTABLE_STATE_EVIDENCE = {3051: 'SMART_SIGNAL_INTEGRATION_FINAL_PROOF.json', 3052: 'SMART_3052_TRAINED_APPLICATION.json'}



PROMOTION_LINEAGE_COMPONENTS = (



    'engine', 'champion_engine', 'signal_agent', 'signal_quality', 'signal_weights', 'context_regime',



    'redundancy_consensus', 'marginal_utility', 'contextual_meta_weights',



    'rank_score_calibration', 'multi_challengers', 'meta_governor',



    'bounded_online_learning', 'signal_interactions', 'signal_expansion_governance', 'learning_activation_gate', 'learning_activation_authority', 'data_quality_gate',



)











def sha256_file(path: Path) -> str:



    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    h = hashlib.sha256()



    with path.open('rb') as f:



        for chunk in iter(lambda: f.read(1024 * 1024), b''):



            h.update(chunk)



    return h.hexdigest()











def sha256_json(obj: Any) -> str:



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











def _resolve(root: Path, value: str | Path) -> Path:



    p = Path(value)



    return p if p.is_absolute() else Path(root) / p











def _resolve_hash_bound_evidence(root: Path, value: str | Path, expected_sha256: str, label: str, *, allow_legacy_mismatch: bool = False) -> Path:
    root = Path(root).resolve()
    declared = Path(value)
    if declared.is_absolute():
        raise ValueError(f'{label} external absolute path denied')
    resolved = (root / declared).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f'{label} escapes project root') from exc
    if not resolved.is_file():
        raise ValueError(f'{label} missing')
    observed = sha256_file(resolved)
    if observed == expected_sha256 or allow_legacy_mismatch:
        return resolved
    raise ValueError(f'{label} hash mismatch')


def _resolve_historical_evidence_by_hash(root: Path, filename: str, expected_sha256: str, label: str, *, allow_legacy_mismatch: bool = False) -> Path:
    root = Path(root).resolve()
    name = Path(filename).name
    candidates = []
    for candidate in root.rglob(name):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f'{label} evidence candidate escapes project root') from exc
        candidates.append(resolved)
    exact = []
    for candidate in candidates:
        try:
            if sha256_file(candidate) == expected_sha256:
                exact.append(candidate)
        except OSError:
            continue
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        # Prefer one live canonical artifact over immutable archival copies of
        # the same hash. Multiple live matches remain ambiguous/fail-closed.
        live = []
        for candidate in exact:
            rel_parts = candidate.relative_to(root).parts
            if not rel_parts or rel_parts[0].casefold() != 'smart_state_archive':
                live.append(candidate)
        if len(live) == 1:
            return live[0]
        raise ValueError(f'{label} hash-bound evidence ambiguous')
    if allow_legacy_mismatch and len(candidates) == 1:
        return candidates[0]
    raise ValueError(f'{label} missing')


def _resolve_audit_evidence(root: Path, value: str | Path, expected_sha256: str, label: str, *, allow_legacy_mismatch: bool = False) -> Path:
    declared = Path(value)
    if declared.is_absolute():
        # Historical absolute paths are never dereferenced or trusted.
        # Only the filename hint plus cryptographic hash may identify a file
        # physically contained by the canonical B2 workspace.
        return _resolve_historical_evidence_by_hash(root, declared.name, expected_sha256, label, allow_legacy_mismatch=allow_legacy_mismatch)
    return _resolve_hash_bound_evidence(root, declared, expected_sha256, label, allow_legacy_mismatch=allow_legacy_mismatch)

def _load_json(path: Path) -> dict[str, Any]:



    obj = json.loads(Path(path).read_text(encoding='utf-8'))



    if not isinstance(obj, dict):



        raise ValueError(f'JSON object required: {path}')



    return obj











def _valid_top6(value: Any, label: str) -> list[int]:



    if not isinstance(value, list) or len(value) != 6:



        raise ValueError(f'{label} must contain exactly six numbers')



    if any(isinstance(x, bool) or not isinstance(x, int) for x in value):



        raise ValueError(f'{label} must contain integer numbers')



    out = [int(x) for x in value]



    if len(set(out)) != 6 or min(out) < 1 or max(out) > 60:



        raise ValueError(f'{label} contains invalid lottery numbers')



    return out











def _event_time(value: Any) -> datetime | None:



    if not isinstance(value, str) or not value:



        return None



    try:



        return datetime.fromisoformat(value.replace('Z', '+00:00'))



    except ValueError:



        return None















def _semantic_frame(df: pd.DataFrame) -> pd.DataFrame:



    out = df.copy()



    for col in out.columns:



        series = out[col]



        if pd.api.types.is_datetime64_any_dtype(series):



            out[col] = series.dt.strftime('%Y-%m-%dT%H:%M:%S').where(series.notna(), None)



        else:



            out[col] = series.astype(object).where(series.notna(), None)



            out[col] = out[col].map(



                lambda value: int(value) if isinstance(value, float) and value.is_integer() else value



            )



    return out











def semantic_dataframe_sha256(df: pd.DataFrame) -> str:



    normalized = _semantic_frame(df)



    raw = normalized.to_json(



        orient='split', date_format='iso', date_unit='s', double_precision=15, force_ascii=False



    ).encode('utf-8')



    return hashlib.sha256(raw).hexdigest()











def audit_legacy_result_continuity(root: Path, target: int, adjudication: dict[str, Any],



                                   frozen: dict[str, Any], frozen_data_file: Path,



                                   current_result_file: Path) -> dict[str, Any]:



    if int(target) != LEGACY_CONTINUITY_TARGET:



        raise ValueError('legacy result continuity is permitted only for contest 3051')



    root = Path(root)



    proof_path = root / f'SMART_P14_LEGACY_RESULT_CONTINUITY_{int(target)}.json'



    proof = _load_json(proof_path)



    if proof.get('schema') != LEGACY_CONTINUITY_SCHEMA or int(proof.get('target_contest', -1)) != int(target):



        raise ValueError('invalid legacy continuity proof')



    original_hash = str(adjudication.get('result_data_sha256', ''))



    if str(proof.get('original_adjudicated_result_sha256')) != original_hash:



        raise ValueError('legacy proof original adjudicated hash mismatch')



    current_hash = sha256_file(current_result_file)



    if str(proof.get('current_result_sha256')) != current_hash:



        raise ValueError('legacy proof current result hash mismatch')



    frozen_hash = sha256_file(frozen_data_file)



    if frozen_hash != str(frozen.get('data_sha256')) or frozen_hash != str(proof.get('frozen_prefix_sha256')):



        raise ValueError('legacy proof frozen prefix hash mismatch')







    prefix_df = pd.read_excel(frozen_data_file)



    current_df = pd.read_excel(current_result_file)



    if list(prefix_df.columns) != list(current_df.columns):



        raise ValueError('legacy result columns differ from frozen prefix')



    if len(current_df) != len(prefix_df) + 1:



        raise ValueError('legacy current result must equal frozen prefix plus one contest')



    prefix_current = current_df.iloc[:len(prefix_df)].copy()



    left = _semantic_frame(prefix_df)



    right = _semantic_frame(prefix_current)



    if not left.equals(right):



        raise ValueError('legacy current result prefix differs semantically from frozen data')



    prefix_semantic_sha = semantic_dataframe_sha256(prefix_df)



    if str(proof.get('prefix_semantic_sha256')) != prefix_semantic_sha:



        raise ValueError('legacy proof semantic prefix hash mismatch')



    contests = current_df['Concurso'].astype(int)



    if int(contests.iloc[-1]) != int(target) or int(contests.max()) != int(target):



        raise ValueError('legacy current result has contests beyond target or wrong final contest')



    actual = _contest_numbers(current_df, target)



    stored_actual = sorted(_valid_top6(adjudication.get('actual_numbers'), 'adjudication actual numbers'))



    if actual != stored_actual or actual != sorted(_valid_top6(proof.get('target_numbers'), 'legacy proof target numbers')):



        raise ValueError('legacy target result does not match adjudication and proof')



    current_semantic_sha = semantic_dataframe_sha256(current_df)



    if str(proof.get('current_semantic_sha256')) != current_semantic_sha:



        raise ValueError('legacy proof current semantic hash mismatch')



    return {



        'status': 'PASS',



        'target_contest': int(target),



        'proof_file': proof_path.name,



        'proof_sha256': sha256_file(proof_path),



        'original_adjudicated_result_sha256': original_hash,



        'current_result_sha256': current_hash,



        'frozen_prefix_sha256': frozen_hash,



        'prefix_semantic_sha256': prefix_semantic_sha,



        'current_semantic_sha256': current_semantic_sha,



        'exact_prefix_semantic_equal': True,



        'target_numbers': actual,



        'binary_hash_exception_scope': 'legacy contest 3051 only',



    }









def audit_legacy_state_continuity(root: Path, target: int, fr: dict[str, Any], frozen: dict[str, Any], state_sha: str) -> dict[str, Any]:

    evidence_name = LEGACY_MUTABLE_STATE_EVIDENCE.get(int(target))

    if evidence_name is None:

        raise ValueError('frozen signal state hash mismatch')

    evidence_path = Path(root) / evidence_name

    if not evidence_path.is_file():

        raise ValueError('legacy state continuity evidence missing')

    evidence = _load_json(evidence_path)

    freeze_sha = str(fr.get('freeze_sha256', ''))

    if int(target) == 3051:

        active = evidence.get('active_freeze')

        artifacts = evidence.get('artifact_hashes')

        event = active.get('event') if isinstance(active, dict) else None

        if evidence.get('schema') != 'SMART_SIGNAL_INTEGRATION_FINAL_PROOF_1' or evidence.get('status') != 'MISSION_PROVEN':

            raise ValueError('legacy 3051 state continuity proof invalid')

        if not isinstance(active, dict) or not isinstance(event, dict) or not isinstance(artifacts, dict):

            raise ValueError('legacy 3051 state continuity proof incomplete')

        if active.get('sha256') != freeze_sha or event.get('freeze_sha256') != freeze_sha or artifacts.get('freeze') != freeze_sha:

            raise ValueError('legacy 3051 state continuity freeze mismatch')

        if event.get('hashes', {}).get('state') != state_sha or artifacts.get('state') != state_sha:

            raise ValueError('legacy 3051 state continuity hash mismatch')

    elif int(target) == 3052:

        if evidence.get('schema') != 'SMART_3052_TRAINED_APPLICATION_1' or int(evidence.get('contest', -1)) != 3052:

            raise ValueError('legacy 3052 state continuity proof invalid')

        if evidence.get('causal') is not True or evidence.get('result_used') is not False:

            raise ValueError('legacy 3052 state continuity causal flags invalid')

        if evidence.get('active_freeze_sha256') != freeze_sha or evidence.get('signal_state_sha256') != state_sha:

            raise ValueError('legacy 3052 state continuity hash mismatch')

        if evidence.get('data_sha256') != frozen.get('data_sha256'):

            raise ValueError('legacy 3052 state continuity data mismatch')

    else:

        raise ValueError('unsupported legacy mutable state target')

    return {

        'status': 'PASS',

        'mode': 'LEGACY_HASH_BOUND_CONTINUITY',

        'target_contest': int(target),

        'evidence_file': evidence_path.name,

        'evidence_file_sha256': sha256_file(evidence_path),

        'freeze_sha256': freeze_sha,

        'state_sha256': state_sha,

        'mutable_state_path_not_trusted': True,

        'legacy_scope_only': True,

    }





def audit_frozen_state_evidence(root: Path, target: int, fr: dict[str, Any], frozen: dict[str, Any], state_sha: str) -> dict[str, Any]:

    archive_raw = frozen.get('signal_state_archive_file')

    archive_sha = frozen.get('signal_state_archive_sha256')

    if archive_raw is not None or archive_sha is not None:

        if not isinstance(archive_raw, str) or not isinstance(archive_sha, str) or archive_sha != state_sha:

            raise ValueError('immutable state archive metadata invalid')

        archive_path = _resolve(root, archive_raw)

        if not archive_path.is_file() or sha256_file(archive_path) != state_sha:

            raise ValueError('immutable state archive hash mismatch')

        if fr.get('state_archive_sha256') != state_sha:

            raise ValueError('ledger state archive hash mismatch')

        return {

            'status': 'PASS', 'mode': 'IMMUTABLE_HASH_ARCHIVE',

            'archive_file': archive_path.name, 'archive_sha256': state_sha,

            'legacy_scope_only': False,

        }

    state_file = _resolve(root, str(frozen.get('signal_state_file', '')))

    if state_file.is_file() and sha256_file(state_file) == state_sha:

        return {

            'status': 'PASS', 'mode': 'LEGACY_LIVE_FILE_EXACT_HASH',

            'state_file': state_file.name, 'state_sha256': state_sha,

            'legacy_scope_only': True,

        }

    return audit_legacy_state_continuity(root, target, fr, frozen, state_sha)





def policy_snapshot() -> dict[str, Any]:



    payload = {



        'schema': 'SMART_INDEPENDENT_AUDIT_POLICY_1',



        'promotion_authority': False,



        'fail_closed': True,



        'independent_recomputation_required': True,



        'coverage_source_hash_binding_required': True,



        'line_and_branch_coverage_required': True,



        'evidence_only_promotion_coverage_required': True,



        'frozen_artifact_hash_required': True,

        'immutable_state_archive_required_for_new_freezes': True,

        'legacy_mutable_state_continuity_targets': sorted(LEGACY_MUTABLE_STATE_EVIDENCE),



        'frozen_data_hash_required': True,



        'result_data_hash_required': True,



        'legacy_result_continuity_target': LEGACY_CONTINUITY_TARGET,



        'legacy_binary_hash_exception_requires_full_semantic_equivalence': True,



        'active_freeze_required': True,



        'freeze_before_adjudication_required': True,



        'cutoff_must_end_at_target_minus_one': True,



        'target_result_absent_from_freeze_data': True,



        'recompute_hits_from_frozen_top6': True,



        'recompute_e_process': True,



        'deterministic_replay_required': True,



        'full_champion_comparison_required': True,



        'promotion_lineage_recomputation_required': True,



        'independence_static_import_scan_required': True,

        'independent_decision_oracle_required': True,

        'material_deficiency_registry_required': True,

        'deterministic_replay_uses_production_implementation': True,

        'deterministic_replay_is_not_independent_oracle': True,



        'forbidden_upward_dependencies': [



            'smart_champion_challenger', 'smart_promotion_gate', 'adjudicate_signal_challenger'



        ],



    }



    payload['sha256'] = sha256_json(payload)



    return payload











def audit_independence(root: Path) -> dict[str, Any]:



    root = Path(root)



    runtime_source = Path(__file__).resolve()



    project_source = (root / 'smart_independent_audit.py').resolve()



    if project_source.is_file():



        if sha256_source_file(project_source) != sha256_source_file(runtime_source):



            raise ValueError('independent audit project/runtime source mismatch')



        source = project_source



    else:



        source = runtime_source



    tree = ast.parse(source.read_text(encoding='utf-8-sig'), filename=str(source))



    imported: set[str] = set()



    for node in ast.walk(tree):



        if isinstance(node, ast.Import):



            imported.update(alias.name for alias in node.names)



        elif isinstance(node, ast.ImportFrom) and node.module:



            imported.add(node.module)



    forbidden = set(policy_snapshot()['forbidden_upward_dependencies'])



    forbidden_found = sorted(



        name for name in imported



        if any(name == blocked or name.startswith(blocked + '.') for blocked in forbidden)



    )



    if forbidden_found:



        raise ValueError(f'independent audit has forbidden upward dependency: {forbidden_found}')



    runtime_oracle_source = Path(__file__).with_name('smart_independent_oracle.py').resolve()

    project_oracle_source = (root / 'smart_independent_oracle.py').resolve()

    if project_oracle_source.is_file():

        if sha256_source_file(project_oracle_source) != sha256_source_file(runtime_oracle_source):

            raise ValueError('independent decision oracle project/runtime source mismatch')

        oracle_source = project_oracle_source

    else:

        oracle_source = runtime_oracle_source

    if not oracle_source.is_file():

        raise ValueError('independent decision oracle source missing')

    oracle_tree = ast.parse(oracle_source.read_text(encoding='utf-8-sig'), filename=str(oracle_source))

    oracle_imports: set[str] = set()

    for node in ast.walk(oracle_tree):

        if isinstance(node, ast.Import):

            oracle_imports.update(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom) and node.module:

            oracle_imports.add(node.module)

    project_imports = sorted(name for name in oracle_imports if name == 'smart' or name.startswith('smart_'))

    if project_imports:

        raise ValueError(f'independent decision oracle imports project implementation: {project_imports}')



    return {



        'status': 'PASS', 'source_file': source.name, 'source_sha256': sha256_source_file(source),



        'forbidden_dependencies': sorted(forbidden), 'forbidden_dependencies_found': forbidden_found,



        'static_import_scan': True, 'independent': True,

        'independent_oracle_file': oracle_source.name,

        'independent_oracle_sha256': sha256_source_file(oracle_source),

        'independent_oracle_project_imports': project_imports,

        'independent_oracle_has_no_project_imports': True,

        'deterministic_replay_classification': 'SAME_IMPLEMENTATION_DETERMINISM_ONLY',



    }











def _promotion_lineage_fingerprint_independent(fr: dict[str, Any]) -> str | None:



    lineage = fr.get('promotion_lineage')



    if not isinstance(lineage, dict) or lineage.get('schema') != PROMOTION_LINEAGE_SCHEMA:



        return None



    observed = lineage.get('sha256')



    if not _is_hex64(observed):



        return None



    canonical = dict(lineage)



    canonical.pop('sha256', None)



    if sha256_json(canonical) != str(observed).lower():



        return None



    hashes = fr.get('hashes')



    declared = lineage.get('component_hashes')



    if not isinstance(hashes, dict) or not isinstance(declared, dict):



        return None



    for component in PROMOTION_LINEAGE_COMPONENTS:



        value = hashes.get(component)



        if not _is_hex64(value) or declared.get(component) != str(value).lower():



            return None



    return str(observed).lower()











def audit_coverage_binding(root: Path, binding_path: Path) -> dict[str, Any]:



    root = Path(root)



    binding_path = _resolve(root, binding_path)



    binding = _load_json(binding_path)



    if binding.get('schema') != COVERAGE_BINDING_SCHEMA:



        raise ValueError('invalid coverage binding schema')



    source = _resolve(root, binding.get('source_file', ''))



    report = _resolve(root, binding.get('coverage_report_file', ''))



    if not source.is_file() or not report.is_file():



        raise ValueError('coverage binding source/report missing')



    current_source_sha = sha256_source_file(source)



    current_report_sha = sha256_file(report)



    if current_source_sha != binding.get('source_sha256'):



        raise ValueError('coverage binding source hash mismatch')



    if current_report_sha != binding.get('coverage_report_sha256'):



        raise ValueError('coverage binding report hash mismatch')



    report_obj = _load_json(report)



    if report_obj.get('meta', {}).get('branch_coverage') is not True:



        raise ValueError('branch coverage was not enabled')



    key = str(binding.get('coverage_file_key') or source.name)



    f = report_obj.get('files', {}).get(key)



    if not isinstance(f, dict):



        raise ValueError(f'coverage report does not contain {key}')



    s = f.get('summary', {})



    if int(s.get('missing_lines', -1)) != 0 or int(s.get('missing_branches', -1)) != 0:



        raise ValueError('coverage has missing lines or branches')



    if int(s.get('covered_lines', -1)) != int(s.get('num_statements', -2)):



        raise ValueError('line coverage is incomplete')



    if int(s.get('covered_branches', -1)) != int(s.get('num_branches', -2)):



        raise ValueError('branch coverage is incomplete')



    return {



        'status': 'PASS',



        'binding_file': binding_path.name,



        'binding_sha256': sha256_file(binding_path),



        'source_file': source.name,



        'source_sha256': current_source_sha,



        'coverage_report_file': report.name,



        'coverage_report_sha256': current_report_sha,



        'covered_lines': int(s['covered_lines']),



        'statements': int(s['num_statements']),



        'covered_branches': int(s['covered_branches']),



        'branches': int(s['num_branches']),



    }











def audit_coverage_bindings(root: Path, binding_paths: Iterable[Path]) -> dict[str, Any]:



    rows = [audit_coverage_binding(root, p) for p in binding_paths]



    if not rows:



        raise ValueError('at least one independent coverage binding is required')



    return {'status': 'PASS', 'count': len(rows), 'bindings': rows}











def _load_ledger(path: Path) -> dict[str, Any]:



    obj = _load_json(path)



    if obj.get('schema') != LEDGER_SCHEMA or not isinstance(obj.get('events'), list):



        raise ValueError('invalid SMART signal ledger')



    return obj











def _freeze_hash_field(component: str) -> str:



    return 'signal_state_sha256' if component == 'state' else f'{component}_sha256'











def _contest_numbers(df: pd.DataFrame, target: int) -> list[int]:



    if 'Concurso' not in df.columns:



        raise ValueError('dataset missing Concurso column')



    row = df[df['Concurso'].astype(int) == int(target)]



    if len(row) != 1:



        raise ValueError('target contest must occur exactly once')



    r = row.iloc[0]



    values = [int(r[f'Bola{i}']) for i in range(1, 7)]



    return sorted(_valid_top6(values, 'official result'))











def _audit_supersede_chains(events: list[dict[str, Any]]) -> dict[int, str]:



    states: dict[int, dict[str, Any]] = {}



    for ev in events:



        et = ev.get('event_type')



        if et not in {'FREEZE', 'SUPERSEDE'}:



            continue



        target = int(ev.get('target_contest', -1))



        state = states.setdefault(target, {'active': None, 'pending': None, 'seen': set()})



        if et == 'FREEZE':



            h = str(ev.get('freeze_sha256', ''))



            if not _is_hex64(h) or h in state['seen']:



                raise ValueError('invalid or duplicate freeze hash in independent supersede audit')



            if state['pending'] is not None:



                raise ValueError('new freeze encountered before prior supersede linkage')



            state['seen'].add(h)



            if state['active'] is None:



                state['active'] = h



            else:



                state['pending'] = h



        else:



            old = str(ev.get('old_freeze_sha256', ''))



            new = str(ev.get('new_freeze_sha256', ''))



            if not _is_hex64(old) or not _is_hex64(new) or old == new:



                raise ValueError('invalid supersede hash linkage')



            if state['pending'] is None:



                raise ValueError('supersede event requires preceding new freeze')



            if old != state['active'] or new != state['pending']:



                raise ValueError('supersede must replace exactly the independently resolved active freeze')



            state['active'] = state['pending']



            state['pending'] = None



    out: dict[int, str] = {}



    for target, state in states.items():



        if state['pending'] is not None:



            raise ValueError('new freeze is missing supersede linkage')



        active = state['active']



        if active is None:  # pragma: no cover - impossible after a valid FREEZE/SUPERSEDE chain



            raise AssertionError('validated supersede state lost active freeze')



        out[target] = str(active)



    return out











def audit_prospective_ledger(root: Path, ledger_path: Path) -> dict[str, Any]:



    root = Path(root)



    ledger_path = _resolve(root, ledger_path)



    ledger = _load_ledger(ledger_path)



    events = ledger['events']



    independently_active = _audit_supersede_chains(events)



    freezes: dict[str, tuple[int, dict[str, Any]]] = {}



    superseded: set[str] = set()



    adjudications: dict[int, tuple[int, dict[str, Any]]] = {}







    for i, ev in enumerate(events):



        et = ev.get('event_type')



        if et == 'FREEZE':



            h = str(ev.get('freeze_sha256', ''))



            if not _is_hex64(h) or h in freezes:



                raise ValueError('invalid or duplicate freeze hash')



            freezes[h] = (i, ev)



        elif et == 'SUPERSEDE':



            old = str(ev.get('old_freeze_sha256', ''))



            new = str(ev.get('new_freeze_sha256', ''))



            if not _is_hex64(old) or not _is_hex64(new):



                raise ValueError('invalid supersede hashes')



            superseded.add(old)



        elif et == 'ADJUDICATION':



            target = int(ev.get('target_contest', -1))



            if target in adjudications:



                raise ValueError(f'duplicate adjudication for contest {target}')



            adjudications[target] = (i, ev)







    rows: list[dict[str, Any]] = []



    previous_e = 1.0



    for target, (ad_i, ad) in sorted(adjudications.items()):



        freeze_sha = str(ad.get('freeze_sha256', ''))



        if independently_active.get(target) != freeze_sha:



            raise ValueError('adjudication does not reference independently resolved active freeze')



        if freeze_sha not in freezes:



            raise ValueError('adjudication references unknown freeze')



        if freeze_sha in superseded:



            raise ValueError('adjudication references superseded freeze')



        fr_i, fr = freezes[freeze_sha]



        if fr_i >= ad_i:



            raise ValueError('freeze must precede adjudication in append-only ledger')



        if int(fr.get('target_contest', -1)) != target:



            raise ValueError('freeze/adjudication target mismatch')



        if fr.get('frozen_before_result') is not True or fr.get('causal_cutoff') is not True:



            raise ValueError('freeze lacks causal pre-result flags')



        for j, ev in enumerate(events):



            if j <= ad_i or int(ev.get('target_contest', -1)) != target:



                continue



            if ev.get('event_type') in {'FREEZE', 'SUPERSEDE'}:



                raise ValueError('freeze/supersede appears after adjudication')



        fr_time = _event_time(fr.get('created_utc'))



        ad_time = _event_time(ad.get('created_utc'))



        if fr_time is not None and ad_time is not None and ad_time <= fr_time:



            raise ValueError('adjudication timestamp must follow freeze timestamp')







        freeze_file = _resolve_audit_evidence(root, str(fr.get('freeze_file', '')), freeze_sha, 'frozen artifact')



        if not freeze_file.is_file() or sha256_file(freeze_file) != freeze_sha:



            raise ValueError('frozen artifact hash mismatch')



        frozen = _load_json(freeze_file)

        oracle = validate_frozen_decision(frozen)



        if int(frozen.get('target_contest', -1)) != target:



            raise ValueError('frozen artifact target mismatch')



        cutoff = int(frozen.get('cutoff_contest', -1))



        if cutoff != target - 1 or int(fr.get('cutoff_contest', -1)) != cutoff:



            raise ValueError('causal cutoff must be target minus one')



        if frozen.get('frozen_before_result') is not True or frozen.get('causal_cutoff') is not True:



            raise ValueError('frozen artifact lacks causal flags')



        if str(frozen.get('data_sha256')) != str(fr.get('data_sha256')):



            raise ValueError('freeze event and artifact data hashes disagree')







        data_file = _resolve_audit_evidence(root, str(frozen.get('data_file', '')), str(frozen.get('data_sha256', '')), 'frozen input data')



        if not data_file.is_file() or sha256_file(data_file) != frozen.get('data_sha256'):



            raise ValueError('frozen input data hash mismatch')



        pre_df = pd.read_excel(data_file)



        contests = pre_df['Concurso'].astype(int)



        if int(target) in set(contests.tolist()):



            raise ValueError('future result leaked into frozen dataset')



        if len(pre_df) == 0 or int(contests.iloc[-1]) != cutoff or int(contests.max()) != cutoff:



            raise ValueError('frozen dataset does not end at causal cutoff')







        result_file = _resolve_audit_evidence(root, str(ad.get('result_data_file', '')), str(ad.get('result_data_sha256', '')), 'result data', allow_legacy_mismatch=(int(target) == LEGACY_CONTINUITY_TARGET))



        if not result_file.is_file():



            raise ValueError('result data missing')



        result_binary_sha = sha256_file(result_file)



        legacy_continuity = None



        if result_binary_sha != ad.get('result_data_sha256'):



            legacy_continuity = audit_legacy_result_continuity(



                root, target, ad, frozen, data_file, result_file



            )



        result_df = pd.read_excel(result_file)



        actual = _contest_numbers(result_df, target)



        if actual != sorted(_valid_top6(ad.get('actual_numbers'), 'adjudication actual numbers')):



            raise ValueError('stored adjudication result does not match hashed result dataset')







        champion_top6 = _valid_top6(fr.get('champion_top6'), 'frozen champion top6')



        challenger_top6 = _valid_top6(fr.get('challenger_top6'), 'frozen challenger top6')



        if champion_top6 != _valid_top6(frozen.get('champion', {}).get('top6'), 'artifact champion top6'):



            raise ValueError('champion top6 differs between ledger and frozen artifact')



        if challenger_top6 != _valid_top6(frozen.get('challenger', {}).get('top6'), 'artifact challenger top6'):



            raise ValueError('challenger top6 differs between ledger and frozen artifact')



        aset = set(actual)



        champion_hits = len(set(champion_top6) & aset)



        challenger_hits = len(set(challenger_top6) & aset)



        if champion_hits != int(ad.get('champion_hits', -1)) or challenger_hits != int(ad.get('challenger_hits', -1)):



            raise ValueError('stored hit comparison does not reproduce independently')



        diff = challenger_hits - champion_hits



        if diff != int(ad.get('difference_hits', 999)):



            raise ValueError('stored hit difference mismatch')



        expected_e = previous_e * (1.0 + E_BET_LAMBDA * (diff / 6.0))



        observed_e = float(ad.get('e_value_after', float('nan')))



        if not math.isfinite(observed_e) or not math.isclose(observed_e, expected_e, rel_tol=1e-12, abs_tol=1e-12):



            raise ValueError('sequential e-process does not reproduce independently')



        previous_e = expected_e







        hashes = fr.get('hashes', {})



        if not isinstance(hashes, dict) or not hashes:



            raise ValueError('frozen component hash snapshot missing')



        for component, value in hashes.items():



            if not _is_hex64(value):



                raise ValueError(f'invalid frozen component hash: {component}')



            field = _freeze_hash_field(component)



            if field in frozen and str(frozen[field]) != str(value):



                raise ValueError(f'frozen component hash mismatch: {component}')



        state_sha = hashes.get('state')



        state_evidence = None



        if state_sha is not None:



            state_evidence = audit_frozen_state_evidence(root, target, fr, frozen, state_sha)







        promotion_lineage_sha256 = _promotion_lineage_fingerprint_independent(fr)



        rows.append({



            'target_contest': target,



            'freeze_sha256': freeze_sha,



            'cutoff_contest': cutoff,



            'actual_numbers': actual,



            'champion_top6': champion_top6,



            'challenger_top6': challenger_top6,



            'champion_hits': champion_hits,



            'challenger_hits': challenger_hits,



            'difference_hits': diff,



            'e_value_after_recomputed': expected_e,



            'freeze_hash_verified': True,



            'frozen_data_hash_verified': True,



            'state_evidence': state_evidence,



            'result_data_hash_verified': legacy_continuity is None,



            'result_binary_hash_exact': legacy_continuity is None,



            'legacy_result_continuity': legacy_continuity,



            'future_leakage_detected': False,



            'promotion_lineage_sha256': promotion_lineage_sha256,

            'independent_decision_oracle': oracle,



        })







    if not rows:



        raise ValueError('independent audit requires at least one adjudicated prospective pair')



    ch = sum(r['challenger_hits'] for r in rows)



    cp = sum(r['champion_hits'] for r in rows)



    comparison = {



        'adjudicated_contests': len(rows),



        'champion_hits': cp,



        'challenger_hits': ch,



        'advantage_hits': ch - cp,



        'cumulative_regret': cp - ch,



        'all_pairs_recomputed': True,



    }



    versioned = [r for r in rows if r.get('promotion_lineage_sha256')]



    lineage_rows: list[dict[str, Any]] = []



    current_lineage = versioned[-1]['promotion_lineage_sha256'] if versioned else None



    if current_lineage is not None:



        for row in reversed(versioned):



            if row['promotion_lineage_sha256'] != current_lineage:



                break



            lineage_rows.append(row)



        lineage_rows.reverse()



    lch = sum(r['challenger_hits'] for r in lineage_rows)



    lcp = sum(r['champion_hits'] for r in lineage_rows)



    lineage_e = 1.0



    for row in lineage_rows:



        lineage_e *= 1.0 + E_BET_LAMBDA * ((row['challenger_hits'] - row['champion_hits']) / 6.0)



    lineage_comparison = {



        'candidate_fingerprint': current_lineage,



        'adjudicated_contests': len(lineage_rows),



        'champion_hits': lcp,



        'challenger_hits': lch,



        'advantage_hits': lch - lcp,



        'cumulative_regret': lcp - lch,



        'e_value': lineage_e,



        'unversioned_causal_pairs_ignored': len(rows) - len(versioned),



        'discarded_prior_version_pairs': len(versioned) - len(lineage_rows),



        'lineage_recomputed_independently': True,



        'lineage_pairs_recomputed': True,



    }



    oracle_applicable = [r for r in rows if r['independent_decision_oracle'].get('status') != 'LEGACY_NOT_APPLICABLE']

    oracle_verified = [r for r in oracle_applicable if r['independent_decision_oracle'].get('verified') is True]

    if len(oracle_verified) != len(oracle_applicable):

        raise ValueError('independent decision oracle did not verify every applicable frozen prediction')



    return {



        'status': 'PASS',



        'ledger_file': ledger_path.name,



        'ledger_sha256': sha256_file(ledger_path),



        'pair_count': len(rows),



        'no_future_leakage': True,



        'hash_integrity': True,



        'supersede_chain_integrity': True,



        'legacy_result_continuity_used': any(row['legacy_result_continuity'] is not None for row in rows),



        'e_process_recomputed': True,



        'full_champion_comparison': comparison,



        'promotion_lineage_comparison': lineage_comparison,

        'independent_oracle_applicable_pairs': len(oracle_applicable),

        'independent_oracle_verified_pairs': len(oracle_verified),

        'independent_oracle_scope_complete': len(oracle_verified) == len(oracle_applicable),



        'pairs': rows,



    }











def _prediction_replay_document(prediction: Any, backtest: dict[str, Any]) -> dict[str, Any]:



    p = prediction.as_dict()



    p.pop('generated_utc', None)



    return {'prediction': p, 'backtest': backtest}











def audit_deterministic_replay(root: Path, data_path: Path, target: int, start: int = 1000) -> dict[str, Any]:



    root = Path(root)



    data_path = _resolve(root, data_path)



    if not data_path.is_file():



        raise ValueError('replay data missing')



    draws, contests = engine.load_draws(data_path)



    if len(contests) == 0 or int(contests[-1]) != int(target) - 1:



        raise ValueError('replay data must end immediately before target')







    champion_a = champion_engine.current_policy(draws, start=start)



    champion_b = champion_engine.current_policy(draws, start=start)



    champion_hash_a = sha256_json(champion_a)



    champion_hash_b = sha256_json(champion_b)



    if champion_hash_a != champion_hash_b:



        raise ValueError('Champion replay is not deterministic')







    fixed_ts = f'independent-audit-cutoff-contest-{int(contests[-1])}'



    agent_a = SmartSignalAgent(start=start)



    pred_a, back_a = agent_a.predict_next(



        draws, contests, target_contest=int(target), cutoff_timestamp=fixed_ts,



        cutoff_timestamp_kind='independent_audit_fixed_cutoff', champion_top6=champion_a['top6']



    )



    agent_b = SmartSignalAgent(start=start)



    pred_b, back_b = agent_b.predict_next(



        draws, contests, target_contest=int(target), cutoff_timestamp=fixed_ts,



        cutoff_timestamp_kind='independent_audit_fixed_cutoff', champion_top6=champion_a['top6']



    )



    doc_a = _prediction_replay_document(pred_a, back_a)



    doc_b = _prediction_replay_document(pred_b, back_b)



    challenger_hash_a = sha256_json(doc_a)



    challenger_hash_b = sha256_json(doc_b)



    if challenger_hash_a != challenger_hash_b:



        raise ValueError('Challenger replay is not deterministic')



    if int(pred_a.cutoff_contest) != int(target) - 1 or int(pred_a.target_contest) != int(target):



        raise ValueError('Challenger replay violates causal target/cutoff')



    oracle = validate_prediction_snapshot(pred_a.as_dict())

    if oracle.get('verified') is not True:

        raise ValueError('independent decision oracle could not verify replay prediction')







    return {



        'status': 'PASS',



        'data_file': data_path.name,



        'data_sha256': sha256_file(data_path),



        'target_contest': int(target),



        'cutoff_contest': int(contests[-1]),



        'start_index': int(start),



        'champion_replay_sha256': champion_hash_a,



        'challenger_replay_sha256': challenger_hash_a,



        'champion_top6': [int(x) for x in champion_a['top6']],



        'challenger_top6': [int(x) for x in pred_a.top6],

        'independent_decision_oracle': oracle,



        'deterministic': True,



        'causal_cutoff_verified': True,



    }











def run_independent_audit(root: Path, ledger_path: Path, coverage_bindings: Iterable[Path],



                          replay_data: Path, replay_target: int, start: int = 1000) -> dict[str, Any]:



    root = Path(root).resolve()



    policy = policy_snapshot()



    independence = audit_independence(root)



    coverage = audit_coverage_bindings(root, coverage_bindings)



    ledger = audit_prospective_ledger(root, ledger_path)



    replay = audit_deterministic_replay(root, replay_data, replay_target, start=start)



    deficiency_registry = load_material_deficiency_registry(root=root)

    material_deficiencies = list(deficiency_registry['open_deficiencies'])



    report = {



        'schema': SCHEMA,



        'status': 'PASS' if not material_deficiencies else 'FAIL',



        'policy': policy,



        'independence': independence,



        'coverage': coverage,



        'prospective_ledger': ledger,



        'deterministic_replay': replay,



        'checks': {



            'coverage_lines_and_branches': True,



            'hash_integrity': True,



            'deterministic_replay': True,



            'future_leakage_absent': True,



            'full_champion_comparison': True,



            'promotion_lineage_recomputed': True,



            'independence_no_forbidden_dependencies': True,

            'independent_freeze_decision_oracle': bool(replay.get('independent_decision_oracle', {}).get('verified') is True),



        },



        'promotion_authority': False,



        'independent_of_promotion_decision': True,



        'material_deficiency_registry': deficiency_registry,



        'material_deficiencies': material_deficiencies,



    }



    report['sha256'] = sha256_json(report)



    return report








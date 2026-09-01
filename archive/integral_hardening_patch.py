from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(r'C:\New Projet\SMART-MEGA')
ARCHIVE = ROOT / 'archive'


def backup(name: str, suffix: str) -> None:
    src = ROOT / name
    dst = ARCHIVE / f'{Path(name).stem}.{suffix}{Path(name).suffix}'
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)


def write(name: str, text: str) -> None:
    (ROOT / name).write_text(text, encoding='utf-8')


# Preserve exact pre-hardening sources.
for name in ('smart_champion_challenger.py', 'smart_independent_audit.py',
             'smart_evidence_only_promotion.py', 'smart_continuous_red_team.py'):
    backup(name, 'pre_integral_hardening_v2')

# ---------------------------------------------------------------------------
# P13 / orchestrator: cryptographic predictive lineage, lineage-local e-process,
# and idempotence sensitive to start/config/registry changes.
# ---------------------------------------------------------------------------
p = ROOT / 'smart_champion_challenger.py'
s = p.read_text(encoding='utf-8')
s = s.replace(
    'from smart_signal_agent import SmartSignalAgent, write_state, SIGNAL_NAMES',
    'from smart_signal_agent import SmartSignalAgent, write_state, SIGNAL_NAMES, AGENT_SCHEMA'
)
s = re.sub(
    r"PROMOTION_LINEAGE_COMPONENTS = \(.*?\)\n",
    "PROMOTION_LINEAGE_SCHEMA = 'SMART_PROMOTION_LINEAGE_1'\n"
    "PROMOTION_LINEAGE_COMPONENTS = (\n"
    "    'engine', 'champion_engine', 'signal_agent', 'signal_quality', 'signal_weights', 'context_regime',\n"
    "    'redundancy_consensus', 'marginal_utility', 'contextual_meta_weights',\n"
    "    'rank_score_calibration', 'multi_challengers', 'meta_governor',\n"
    "    'bounded_online_learning', 'signal_interactions', 'signal_expansion_governance',\n"
    ")\n",
    s,
    count=1,
    flags=re.S,
)
start = s.index('def _promotion_candidate_fingerprint(')
end = s.index('def promotion_status(', start)
new = '''def _promotion_candidate_fingerprint(fr: dict[str, Any]) -> str | None:\n    lineage = fr.get('promotion_lineage')\n    if not isinstance(lineage, dict) or lineage.get('schema') != PROMOTION_LINEAGE_SCHEMA:\n        return None\n    observed = lineage.get('sha256')\n    if not isinstance(observed, str) or len(observed) != 64:\n        return None\n    try:\n        int(observed, 16)\n    except ValueError:\n        return None\n    canonical = dict(lineage)\n    canonical.pop('sha256', None)\n    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')\n    if hashlib.sha256(raw).hexdigest() != observed.lower():\n        return None\n    hashes = fr.get('hashes')\n    declared = lineage.get('component_hashes')\n    if not isinstance(hashes, dict) or not isinstance(declared, dict):\n        return None\n    for component in PROMOTION_LINEAGE_COMPONENTS:\n        value = hashes.get(component)\n        if not isinstance(value, str) or len(value) != 64:\n            return None\n        try:\n            int(value, 16)\n        except ValueError:\n            return None\n        if declared.get(component) != value.lower():\n            return None\n    return observed.lower()\n\n\ndef promotion_eligibility_status(ledger: dict[str, Any]) -> dict[str, Any]:\n    pairs = paired_events(ledger)\n    versioned_pairs: list[tuple[int, dict[str, Any], dict[str, Any], str]] = []\n    unversioned_causal_pairs = 0\n    for c, fr, ad in pairs:\n        if not fr.get('frozen_before_result') or not fr.get('causal_cutoff'):\n            continue\n        fingerprint = _promotion_candidate_fingerprint(fr)\n        if fingerprint is None:\n            unversioned_causal_pairs += 1\n            continue\n        versioned_pairs.append((c, fr, ad, fingerprint))\n\n    lineage: list[tuple[int, dict[str, Any], dict[str, Any], str]] = []\n    current_fingerprint = versioned_pairs[-1][3] if versioned_pairs else None\n    if current_fingerprint is not None:\n        for row in reversed(versioned_pairs):\n            if row[3] != current_fingerprint:\n                break\n            lineage.append(row)\n        lineage.reverse()\n\n    records = [\n        {'challenger_hits': ad.get('challenger_hits'), 'champion_hits': ad.get('champion_hits')}\n        for _, _, ad, _ in lineage\n    ]\n    # Reuse P13 validation before any arithmetic so fractional/boolean/nonfinite hits cannot be truncated.\n    if records:\n        assess_promotion_records(records, 1.0)\n    lineage_e_value = 1.0\n    for record in records:\n        challenger_hits = float(record['challenger_hits'])\n        champion_hits = float(record['champion_hits'])\n        factor = 1.0 + E_BET_LAMBDA * ((challenger_hits - champion_hits) / 6.0)\n        if factor <= 0.0:\n            raise ValueError('invalid lineage e-process factor')\n        lineage_e_value *= factor\n\n    status = assess_promotion_records(records, lineage_e_value)\n    status.update({\n        'candidate_fingerprint': current_fingerprint,\n        'lineage_pair_count': len(lineage),\n        'total_versioned_causal_pairs': len(versioned_pairs),\n        'unversioned_causal_pairs_ignored': unversioned_causal_pairs,\n        'discarded_prior_version_pairs': len(versioned_pairs) - len(lineage),\n        'lineage_e_value': lineage_e_value,\n        'stored_global_e_value_trusted_for_promotion': False,\n        'lineage_reset_on_predictive_architecture_change': True,\n        'promotion_lineage_components': list(PROMOTION_LINEAGE_COMPONENTS),\n    })\n    return status\n\n\n'''
s = s[:start] + new + s[end:]

old = '''    if active:\n        same_components = all(str(active.get('hashes', {}).get(k)) == str(v)\n                              for k, v in component_hashes.items() if k != 'champion_engine')\n        if same_components and str(active.get('data_sha256')) == data_hash:\n            fp = Path(active['freeze_file'])\n            if fp.exists() and sha256(fp) == active.get('freeze_sha256'):\n                return {'status': 'ALREADY_FROZEN_IDENTICAL_EVENT_PRESERVED', 'target_contest': int(target),\n                        'freeze_file': str(fp), 'freeze_sha256': active['freeze_sha256'],\n                        'promotion': promotion_status(ledger)}\n'''
new_idem = '''    if active:\n        same_components = all(str(active.get('hashes', {}).get(k)) == str(v)\n                              for k, v in component_hashes.items())\n        same_registry = str(active.get('snapshot', {}).get('signal_expansion_governance', {}).get('sha256')) == str(expansion_snapshot.get('sha256'))\n        same_start = int(active.get('start_index', -1)) == int(start)\n        same_river = str(active.get('river_version', '')) == str(river.__version__)\n        if same_components and same_registry and same_start and same_river and str(active.get('data_sha256')) == data_hash:\n            fp = Path(active['freeze_file'])\n            if fp.exists() and sha256(fp) == active.get('freeze_sha256'):\n                return {'status': 'ALREADY_FROZEN_IDENTICAL_EVENT_PRESERVED', 'target_contest': int(target),\n                        'freeze_file': str(fp), 'freeze_sha256': active['freeze_sha256'],\n                        'promotion': promotion_status(ledger)}\n'''
if old not in s:
    raise RuntimeError('champion idempotence marker missing')
s = s.replace(old, new_idem, 1)

old_agent = '''    champion = champion_engine.current_policy(draws, start=start)\n    agent = SmartSignalAgent(start=start)\n    challenger_pred, challenger_backtest = agent.predict_next(draws, contests, target_contest=target,\n                                                               cutoff_timestamp=signal_ts,\n                                                               cutoff_timestamp_kind=signal_ts_kind)\n'''
new_agent = '''    champion = champion_engine.current_policy(draws, start=start)\n    agent = SmartSignalAgent(start=start)\n    promotion_lineage = {\n        'schema': PROMOTION_LINEAGE_SCHEMA,\n        'start_index': int(start),\n        'agent_schema': AGENT_SCHEMA,\n        'river_version': str(river.__version__),\n        'signal_ids': list(SIGNAL_NAMES),\n        'eta': float(agent.eta),\n        'redundancy_threshold': float(agent.redundancy_threshold),\n        'meta_strength': float(agent.meta_strength),\n        'calibration_strength': float(agent.calibration_strength),\n        'signal_expansion_registry_snapshot_sha256': expansion_snapshot.get('sha256'),\n        'component_hashes': {k: component_hashes[k].lower() for k in PROMOTION_LINEAGE_COMPONENTS},\n    }\n    promotion_lineage['sha256'] = hashlib.sha256(\n        json.dumps(promotion_lineage, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')\n    ).hexdigest()\n    challenger_pred, challenger_backtest = agent.predict_next(draws, contests, target_contest=target,\n                                                               cutoff_timestamp=signal_ts,\n                                                               cutoff_timestamp_kind=signal_ts_kind)\n'''
if old_agent not in s:
    raise RuntimeError('champion agent marker missing')
s = s.replace(old_agent, new_agent, 1)
s = s.replace(
    "        'evidence_only_promotion_policy': evidence_only_promotion_snapshot,\n    }",
    "        'evidence_only_promotion_policy': evidence_only_promotion_snapshot,\n        'promotion_lineage': promotion_lineage,\n    }",
    1,
)
s = s.replace(
    "        'created_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,\n        'freeze_file': str(actual_out),",
    "        'created_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,\n        'start_index': int(start), 'river_version': str(river.__version__),\n        'promotion_lineage': promotion_lineage,\n        'freeze_file': str(actual_out),",
    1,
)
s = s.replace(
    "                     'evidence_only_promotion_policy': freeze_obj['evidence_only_promotion_policy']},",
    "                     'evidence_only_promotion_policy': freeze_obj['evidence_only_promotion_policy'],\n                     'promotion_lineage': promotion_lineage},",
    1,
)
write('smart_champion_challenger.py', s)

# ---------------------------------------------------------------------------
# P14: independently verify import independence and independently reconstruct
# the same promotion lineage without importing P13/P15 decision code.
# ---------------------------------------------------------------------------
p = ROOT / 'smart_independent_audit.py'
s = p.read_text(encoding='utf-8')
if 'import ast\n' not in s:
    s = s.replace('import hashlib\n', 'import ast\nimport hashlib\n', 1)
if "PROMOTION_LINEAGE_SCHEMA = 'SMART_PROMOTION_LINEAGE_1'" not in s:
    s = s.replace(
        "LEGACY_CONTINUITY_TARGET = 3051\n",
        "LEGACY_CONTINUITY_TARGET = 3051\n"
        "PROMOTION_LINEAGE_SCHEMA = 'SMART_PROMOTION_LINEAGE_1'\n"
        "PROMOTION_LINEAGE_COMPONENTS = (\n"
        "    'engine', 'champion_engine', 'signal_agent', 'signal_quality', 'signal_weights', 'context_regime',\n"
        "    'redundancy_consensus', 'marginal_utility', 'contextual_meta_weights',\n"
        "    'rank_score_calibration', 'multi_challengers', 'meta_governor',\n"
        "    'bounded_online_learning', 'signal_interactions', 'signal_expansion_governance',\n"
        ")\n",
        1,
    )
s = s.replace(
    "        'full_champion_comparison_required': True,\n",
    "        'full_champion_comparison_required': True,\n        'promotion_lineage_recomputation_required': True,\n        'independence_static_import_scan_required': True,\n",
    1,
)
marker = 'def audit_coverage_binding(root: Path, binding_path: Path) -> dict[str, Any]:'
if 'def audit_independence(' not in s:
    func = '''def audit_independence(root: Path) -> dict[str, Any]:\n    root = Path(root)\n    source = root / 'smart_independent_audit.py'\n    if not source.is_file():\n        raise ValueError('independent audit source missing')\n    tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))\n    imported: set[str] = set()\n    for node in ast.walk(tree):\n        if isinstance(node, ast.Import):\n            imported.update(alias.name for alias in node.names)\n        elif isinstance(node, ast.ImportFrom) and node.module:\n            imported.add(node.module)\n    forbidden = set(policy_snapshot()['forbidden_upward_dependencies'])\n    forbidden_found = sorted(\n        name for name in imported\n        if any(name == blocked or name.startswith(blocked + '.') for blocked in forbidden)\n    )\n    if forbidden_found:\n        raise ValueError(f'independent audit has forbidden upward dependency: {forbidden_found}')\n    return {\n        'status': 'PASS', 'source_file': source.name, 'source_sha256': sha256_file(source),\n        'forbidden_dependencies': sorted(forbidden), 'forbidden_dependencies_found': forbidden_found,\n        'static_import_scan': True, 'independent': True,\n    }\n\n\ndef _promotion_lineage_fingerprint_independent(fr: dict[str, Any]) -> str | None:\n    lineage = fr.get('promotion_lineage')\n    if not isinstance(lineage, dict) or lineage.get('schema') != PROMOTION_LINEAGE_SCHEMA:\n        return None\n    observed = lineage.get('sha256')\n    if not _is_hex64(observed):\n        return None\n    canonical = dict(lineage)\n    canonical.pop('sha256', None)\n    if sha256_json(canonical) != str(observed).lower():\n        return None\n    hashes = fr.get('hashes')\n    declared = lineage.get('component_hashes')\n    if not isinstance(hashes, dict) or not isinstance(declared, dict):\n        return None\n    for component in PROMOTION_LINEAGE_COMPONENTS:\n        value = hashes.get(component)\n        if not _is_hex64(value) or declared.get(component) != str(value).lower():\n            return None\n    return str(observed).lower()\n\n\n'''
    idx = s.index(marker)
    s = s[:idx] + func + s[idx:]

# Attach independent lineage fingerprint to each audited pair.
s = s.replace(
    "        rows.append({\n            'target_contest': target,",
    "        promotion_lineage_sha256 = _promotion_lineage_fingerprint_independent(fr)\n        rows.append({\n            'target_contest': target,",
    1,
)
s = s.replace(
    "            'future_leakage_detected': False,\n        })",
    "            'future_leakage_detected': False,\n            'promotion_lineage_sha256': promotion_lineage_sha256,\n        })",
    1,
)
old_comp = '''    comparison = {\n        'adjudicated_contests': len(rows),\n        'champion_hits': cp,\n        'challenger_hits': ch,\n        'advantage_hits': ch - cp,\n        'cumulative_regret': cp - ch,\n        'all_pairs_recomputed': True,\n    }\n    return {\n'''
new_comp = '''    comparison = {\n        'adjudicated_contests': len(rows),\n        'champion_hits': cp,\n        'challenger_hits': ch,\n        'advantage_hits': ch - cp,\n        'cumulative_regret': cp - ch,\n        'all_pairs_recomputed': True,\n    }\n    versioned = [r for r in rows if r.get('promotion_lineage_sha256')]\n    lineage_rows: list[dict[str, Any]] = []\n    current_lineage = versioned[-1]['promotion_lineage_sha256'] if versioned else None\n    if current_lineage is not None:\n        for row in reversed(versioned):\n            if row['promotion_lineage_sha256'] != current_lineage:\n                break\n            lineage_rows.append(row)\n        lineage_rows.reverse()\n    lch = sum(r['challenger_hits'] for r in lineage_rows)\n    lcp = sum(r['champion_hits'] for r in lineage_rows)\n    lineage_e = 1.0\n    for row in lineage_rows:\n        lineage_e *= 1.0 + E_BET_LAMBDA * ((row['challenger_hits'] - row['champion_hits']) / 6.0)\n    lineage_comparison = {\n        'candidate_fingerprint': current_lineage,\n        'adjudicated_contests': len(lineage_rows),\n        'champion_hits': lcp,\n        'challenger_hits': lch,\n        'advantage_hits': lch - lcp,\n        'cumulative_regret': lcp - lch,\n        'e_value': lineage_e,\n        'unversioned_causal_pairs_ignored': len(rows) - len(versioned),\n        'discarded_prior_version_pairs': len(versioned) - len(lineage_rows),\n        'lineage_recomputed_independently': True,\n    }\n    return {\n'''
if old_comp not in s:
    raise RuntimeError('P14 comparison marker missing')
s = s.replace(old_comp, new_comp, 1)
s = s.replace(
    "        'full_champion_comparison': comparison,\n        'pairs': rows,",
    "        'full_champion_comparison': comparison,\n        'promotion_lineage_comparison': lineage_comparison,\n        'pairs': rows,",
    1,
)
old_run = '''    policy = policy_snapshot()\n    coverage = audit_coverage_bindings(root, coverage_bindings)\n    ledger = audit_prospective_ledger(root, ledger_path)\n    replay = audit_deterministic_replay(root, replay_data, replay_target, start=start)\n'''
new_run = '''    policy = policy_snapshot()\n    independence = audit_independence(root)\n    coverage = audit_coverage_bindings(root, coverage_bindings)\n    ledger = audit_prospective_ledger(root, ledger_path)\n    replay = audit_deterministic_replay(root, replay_data, replay_target, start=start)\n'''
if old_run not in s:
    raise RuntimeError('P14 run marker missing')
s = s.replace(old_run, new_run, 1)
s = s.replace("        'policy': policy,\n        'coverage': coverage,", "        'policy': policy,\n        'independence': independence,\n        'coverage': coverage,", 1)
s = s.replace(
    "            'full_champion_comparison': True,\n",
    "            'full_champion_comparison': True,\n            'promotion_lineage_recomputed': True,\n            'independence_no_forbidden_dependencies': True,\n",
    1,
)
s = s.replace(
    "        'independent_of_promotion_decision': True,\n    }",
    "        'independent_of_promotion_decision': True,\n        'material_deficiencies': [],\n    }",
    1,
)
write('smart_independent_audit.py', s)

# ---------------------------------------------------------------------------
# P15: fail closed on missing material-deficiency registry and consume P14's
# independently recomputed promotion lineage, not all historical pairs.
# ---------------------------------------------------------------------------
p = ROOT / 'smart_evidence_only_promotion.py'
s = p.read_text(encoding='utf-8')
s = s.replace(
    "    'full_champion_comparison',\n)",
    "    'full_champion_comparison',\n    'promotion_lineage_recomputed',\n    'independence_no_forbidden_dependencies',\n)",
    1,
)
s = s.replace(
    "    comparison = ledger.get('full_champion_comparison') if isinstance(ledger, dict) else None",
    "    comparison = ledger.get('promotion_lineage_comparison') if isinstance(ledger, dict) else None",
    1,
)
s = s.replace(
    "            blockers.append('p13_p14_pair_count_mismatch')",
    "            blockers.append('p13_p14_pair_count_mismatch')\n        if comparison.get('candidate_fingerprint') != p13.get('candidate_fingerprint'):\n            blockers.append('p13_p14_lineage_fingerprint_mismatch')\n        observed_lineage_e = comparison.get('e_value')\n        if not isinstance(observed_lineage_e, (int, float)) or isinstance(observed_lineage_e, bool) or not math.isfinite(float(observed_lineage_e)) or not math.isclose(float(observed_lineage_e), float(p13['e_value']), rel_tol=1e-12, abs_tol=1e-12):\n            blockers.append('p13_p14_lineage_e_value_mismatch')",
    1,
)
old_material = '''    material = audit.get('material_deficiencies', [])\n    if not isinstance(material, list):\n        blockers.append('independent_audit_material_deficiencies_invalid')\n        material = ['invalid_material_deficiency_registry']\n    if material:\n        blockers.append('known_material_deficiencies_present')\n'''
new_material = '''    if 'material_deficiencies' not in audit:\n        blockers.append('independent_audit_material_deficiencies_missing')\n        material = ['missing_material_deficiency_registry']\n    else:\n        material = audit.get('material_deficiencies')\n        if not isinstance(material, list):\n            blockers.append('independent_audit_material_deficiencies_invalid')\n            material = ['invalid_material_deficiency_registry']\n    if material:\n        blockers.append('known_material_deficiencies_present')\n\n    independence = audit.get('independence')\n    if not isinstance(independence, dict):\n        blockers.append('independent_audit_independence_evidence_missing')\n    elif (independence.get('status') != 'PASS' or independence.get('independent') is not True\n          or independence.get('static_import_scan') is not True\n          or independence.get('forbidden_dependencies_found') != []):\n        blockers.append('independent_audit_independence_evidence_invalid')\n'''
if old_material not in s:
    raise RuntimeError('P15 material marker missing')
s = s.replace(old_material, new_material, 1)
write('smart_evidence_only_promotion.py', s)

# ---------------------------------------------------------------------------
# P09: any P12-P15 behavioral/governance code change invalidates the latest
# continuous red-team report.
# ---------------------------------------------------------------------------
p = ROOT / 'smart_continuous_red_team.py'
s = p.read_text(encoding='utf-8')
old = "    'smart_signal_expansion_governance.py',\n    'smart_signal_agent.py',\n    'smart_champion_challenger.py',\n    'adjudicate_signal_challenger.py',"
new = "    'smart_signal_expansion_governance.py',\n    'smart_sequential_prospective_proof.py',\n    'smart_promotion_gate.py',\n    'smart_independent_audit.py',\n    'smart_evidence_only_promotion.py',\n    'smart_signal_agent.py',\n    'smart_champion_challenger.py',\n    'adjudicate_signal_challenger.py',"
if old not in s:
    raise RuntimeError('P09 behavioral file marker missing')
s = s.replace(old, new, 1)
write('smart_continuous_red_team.py', s)

print('INTEGRAL_HARDENING_PATCH_OK')

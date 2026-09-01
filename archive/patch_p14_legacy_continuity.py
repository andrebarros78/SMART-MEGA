from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_independent_audit.py'
s=p.read_text(encoding='utf-8-sig')
if "LEGACY_CONTINUITY_SCHEMA" not in s:
    s=s.replace("E_BET_LAMBDA = 0.25\n", "E_BET_LAMBDA = 0.25\nLEGACY_CONTINUITY_SCHEMA = 'SMART_P14_LEGACY_RESULT_CONTINUITY_1'\nLEGACY_CONTINUITY_TARGET = 3051\n")

marker="\ndef policy_snapshot() -> dict[str, Any]:\n"
helper=r'''

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
    current_prefix_semantic_sha = semantic_dataframe_sha256(prefix_current)
    if prefix_semantic_sha != current_prefix_semantic_sha:
        raise ValueError('legacy semantic prefix hash mismatch')
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
'''
if 'def audit_legacy_result_continuity' not in s:
    if marker not in s: raise SystemExit('policy marker missing')
    s=s.replace(marker, helper+marker,1)

old="        'result_data_hash_required': True,\n"
new="        'result_data_hash_required': True,\n        'legacy_result_continuity_target': LEGACY_CONTINUITY_TARGET,\n        'legacy_binary_hash_exception_requires_full_semantic_equivalence': True,\n"
if new.strip() not in s:
    if old not in s: raise SystemExit('policy field marker missing')
    s=s.replace(old,new,1)

old2="        result_file = _resolve(root, str(ad.get('result_data_file', '')))\n        if not result_file.is_file() or sha256_file(result_file) != ad.get('result_data_sha256'):\n            raise ValueError('result data hash mismatch')\n        result_df = pd.read_excel(result_file)\n"
new2="        result_file = _resolve(root, str(ad.get('result_data_file', '')))\n        if not result_file.is_file():\n            raise ValueError('result data missing')\n        result_binary_sha = sha256_file(result_file)\n        legacy_continuity = None\n        if result_binary_sha != ad.get('result_data_sha256'):\n            legacy_continuity = audit_legacy_result_continuity(\n                root, target, ad, frozen, data_file, result_file\n            )\n        result_df = pd.read_excel(result_file)\n"
if new2.strip() not in s:
    if old2 not in s: raise SystemExit('result marker missing')
    s=s.replace(old2,new2,1)

old3="            'result_data_hash_verified': True,\n            'future_leakage_detected': False,\n        })\n"
new3="            'result_data_hash_verified': legacy_continuity is None,\n            'result_binary_hash_exact': legacy_continuity is None,\n            'legacy_result_continuity': legacy_continuity,\n            'future_leakage_detected': False,\n        })\n"
if new3.strip() not in s:
    if old3 not in s: raise SystemExit('row marker missing')
    s=s.replace(old3,new3,1)

old4="        'hash_integrity': True,\n        'e_process_recomputed': True,\n"
new4="        'hash_integrity': True,\n        'legacy_result_continuity_used': any(row['legacy_result_continuity'] is not None for row in rows),\n        'e_process_recomputed': True,\n"
if new4.strip() not in s:
    if old4 not in s: raise SystemExit('return marker missing')
    s=s.replace(old4,new4,1)

p.write_text(s,encoding='utf-8')
print('P14 legacy continuity support patched')

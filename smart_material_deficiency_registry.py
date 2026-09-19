from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA = 'SMART_MATERIAL_DEFICIENCY_REGISTRY_1'
DEFAULT_PATH = Path('SMART_MATERIAL_DEFICIENCY_REGISTRY.json')
ALLOWED_SEVERITIES = ('P0', 'P1', 'P2', 'P3')
ALLOWED_STATUSES = ('OPEN', 'REOPENED', 'RESOLVED')
OPEN_STATUSES = {'OPEN', 'REOPENED'}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
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


def build_registry(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError('material deficiency entry must be an object')
        deficiency_id = raw.get('id')
        if not isinstance(deficiency_id, str) or not deficiency_id.strip() or deficiency_id in seen:
            raise ValueError('material deficiency id must be unique and non-empty')
        seen.add(deficiency_id)
        severity = raw.get('severity')
        status = raw.get('status')
        summary = raw.get('summary')
        evidence = raw.get('evidence')
        if severity not in ALLOWED_SEVERITIES:
            raise ValueError(f'invalid material deficiency severity: {deficiency_id}')
        if status not in ALLOWED_STATUSES:
            raise ValueError(f'invalid material deficiency status: {deficiency_id}')
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError(f'material deficiency summary required: {deficiency_id}')
        if not isinstance(evidence, list) or any(not isinstance(x, str) or not x.strip() for x in evidence):
            raise ValueError(f'material deficiency evidence must be a string list: {deficiency_id}')
        if status == 'RESOLVED' and not evidence:
            raise ValueError(f'resolved material deficiency requires evidence: {deficiency_id}')
        normalized.append({
            'id': deficiency_id,
            'severity': severity,
            'status': status,
            'summary': summary,
            'evidence': list(evidence),
        })
    obj = {
        'schema': SCHEMA,
        'entries': normalized,
        'rules': {
            'open_statuses': sorted(OPEN_STATUSES),
            'resolved_requires_evidence': True,
            'missing_registry_fails_closed': True,
            'self_hash_required': True,
        },
    }
    obj['sha256'] = sha256_json(obj)
    return obj


def load_registry(path: Path = DEFAULT_PATH, *, root: Path = Path('.')) -> dict[str, Any]:
    root = Path(root).resolve()
    path = Path(path)
    resolved = path if path.is_absolute() else root / path
    if not resolved.is_file():
        raise ValueError('material deficiency registry missing')
    obj = json.loads(resolved.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or obj.get('schema') != SCHEMA:
        raise ValueError('material deficiency registry schema invalid')
    observed = obj.get('sha256')
    canonical = dict(obj)
    canonical.pop('sha256', None)
    if not _is_hex64(observed) or observed.lower() != sha256_json(canonical):
        raise ValueError('material deficiency registry self-hash invalid')
    rules = obj.get('rules')
    if not isinstance(rules, dict) or rules.get('open_statuses') != sorted(OPEN_STATUSES) or rules.get('resolved_requires_evidence') is not True or rules.get('missing_registry_fails_closed') is not True or rules.get('self_hash_required') is not True:
        raise ValueError('material deficiency registry rules invalid')
    entries = obj.get('entries')
    if not isinstance(entries, list):
        raise ValueError('material deficiency registry entries invalid')
    rebuilt = build_registry(entries)
    if rebuilt != obj:
        raise ValueError('material deficiency registry canonical content invalid')
    open_rows = [dict(row) for row in entries if row['status'] in OPEN_STATUSES]
    return {
        'schema': SCHEMA,
        'status': 'PASS' if not open_rows else 'BLOCKED',
        'file': resolved.name,
        'file_sha256': sha256_file(resolved),
        'registry_sha256': str(obj['sha256']).lower(),
        'entry_count': len(entries),
        'open_count': len(open_rows),
        'open_deficiencies': [row['id'] for row in open_rows],
        'open_entries': open_rows,
        'all_entries_validated': True,
    }


def upsert_deficiency(path: Path, entry: dict[str, Any], *, root: Path = Path('.')) -> dict[str, Any]:
    root = Path(root).resolve()
    path = Path(path)
    resolved = path if path.is_absolute() else root / path
    load_registry(resolved, root=root)
    current = json.loads(resolved.read_text(encoding='utf-8'))
    entries = list(current.get('entries', []))
    deficiency_id = entry.get('id')
    replaced = False
    for index, row in enumerate(entries):
        if row.get('id') == deficiency_id:
            next_entry = dict(entry)
            if row.get('status') == 'RESOLVED' and next_entry.get('status') == 'OPEN':
                next_entry['status'] = 'REOPENED'
            entries[index] = next_entry
            replaced = True
            break
    if not replaced:
        entries.append(dict(entry))
    registry = build_registry(entries)
    tmp = resolved.with_name(resolved.name + '.tmp-deficiency-sync')
    tmp.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(resolved)
    return load_registry(resolved, root=root)


def write_registry(path: Path, registry: dict[str, Any]) -> str:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'refusing to overwrite material deficiency registry: {path}')
    if not isinstance(registry, dict):
        raise ValueError('material deficiency registry object required')
    canonical = dict(registry)
    observed = canonical.pop('sha256', None)
    if not _is_hex64(observed) or observed.lower() != sha256_json(canonical):
        raise ValueError('material deficiency registry must be self-hashed before write')
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return sha256_file(path)


__all__ = ['SCHEMA', 'DEFAULT_PATH', 'build_registry', 'load_registry', 'upsert_deficiency', 'write_registry', 'sha256_file', 'sha256_json']

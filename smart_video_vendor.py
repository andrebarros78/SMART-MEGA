"""Offline, digest-pinned acquired visual-learning integrations.

Full upstream source is bundled; importing this module never installs packages,
runs models, resolves media URLs or changes the official source authority.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

BUNDLE_ROOT = Path(__file__).resolve().parent / 'vendor' / 'visual_learning'
KNOWN = frozenset(('watch-skill', 'mcp-video-analyzer', 'm3-agent', 'TaskMem'))


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _manifest(root: Path) -> list[dict]:
    lock = json.loads((root / 'VENDOR_LOCK.json').read_text(encoding='utf-8'))
    if lock.get('schema') != 'SMART_VENDOR_LEARNING_LOCK_V1' or lock.get('predictive_weight') != 0.0:
        raise ValueError('INVALID_VENDOR_MANIFEST')
    items = lock.get('sources')
    if not isinstance(items, list) or len(items) != len(KNOWN) or {x.get('name') for x in items} != KNOWN:
        raise ValueError('INVALID_VENDOR_ITEMS')
    for item in items:
        if item['name'] not in KNOWN or not re.fullmatch(r'[0-9a-f]{40}', item['revision']):
            raise ValueError('INVALID_VENDOR_IDENTITY')
        if item['license'] not in ('MIT', 'Apache-2.0'):
            raise ValueError('INVALID_VENDOR_LICENSE')
        for key, prefix, suffix in (('archive', 'sources/', '.tar.gz'), ('license_file', 'sources/', '.LICENSE')):
            value = item[key]
            if not isinstance(value, str) or not value.startswith(prefix) or not value.endswith(suffix) or '/' in value[len(prefix):]:
                raise ValueError('UNSAFE_VENDOR_PATH')
    return items


def verify_bundles(root: str | Path = BUNDLE_ROOT) -> dict:
    root = Path(root)
    items = _manifest(root)
    verified = []
    for item in items:
        for key, digest_key in (('archive', 'archive_sha256'), ('license_file', 'license_sha256')):
            path = root / item[key]
            if path.is_symlink() or not path.is_file() or _sha(path) != item[digest_key]:
                raise ValueError('VENDOR_DIGEST_MISMATCH:' + item['name'])
        verified.append(item['name'])
    return {'status': 'PASS', 'verified': verified, 'predictive_weight': 0.0,
            'remote_repository_dependency': False}


def m3_observation_prompt() -> str:
    """Expose upstream M3 atomic video-observation contract; never generate facts."""
    from vendor.visual_learning.runtime.m3_prompts import prompt_generate_captions_with_ids
    return prompt_generate_captions_with_ids


def normalize_taskmem_entities(text: str) -> str:
    if not isinstance(text, str) or len(text) > 65536:
        raise ValueError('INVALID_OBSERVATION_TEXT')
    from vendor.visual_learning.runtime.taskmem_short_term_memory import unify_face_id
    return unify_face_id(text)


def get_status() -> dict:
    integrity = verify_bundles()
    capabilities = {
        'watch-skill': {'source_bundled': True, 'operational': False, 'reason': 'NODE22_AND_PEER_DEPENDENCIES_UNVERIFIED'},
        'mcp-video-analyzer': {'source_bundled': True, 'operational': False, 'reason': 'NODE22_AND_FFMPEG_OCR_DEPENDENCIES_UNVERIFIED'},
        'm3-agent': {'source_bundled': True, 'operational': False, 'reason': 'GPU_MODEL_AND_PYTHON_DEPENDENCIES_UNVERIFIED'},
        'TaskMem': {'source_bundled': True, 'operational': False, 'reason': 'VIDEO_MODELS_AND_PYTHON_DEPENDENCIES_UNVERIFIED'},
    }
    return {'schema': 'SMART_VENDOR_LEARNING_INTEGRATION_V1', 'integrity': integrity['status'],
            'components': capabilities, 'pure_components_active': ['TaskMem.unify_face_id', 'M3-Agent.observation_prompt'],
            'model_execution_enabled': False, 'source_gate': 'BLOCKED',
            'predictive_weight': 0.0, 'remote_repository_dependency': False}


def materialize_bundle(name: str, destination: str | Path, root: str | Path = BUNDLE_ROOT) -> dict:
    """Extract pinned source only, with no scripts, imports, network or installation."""
    if name not in KNOWN:
        raise ValueError('UNKNOWN_VENDOR')
    base = Path(root)
    verified = verify_bundles(base)
    if name not in verified['verified']:
        raise ValueError('UNVERIFIED_VENDOR')
    item = next(x for x in _manifest(base) if x['name'] == name)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError('UNSAFE_DESTINATION')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vendor-stage-', dir=destination.parent) as staging:
        stage = Path(staging)
        total = 0
        count = 0
        with tarfile.open(base / item['archive'], 'r:gz') as archive:
            for member in archive:
                parts = Path(member.name)
                if (parts.is_absolute() or '..' in parts.parts or member.issym() or member.islnk()
                        or not (member.isfile() or member.isdir())):
                    raise ValueError('UNSAFE_VENDOR_ARCHIVE')
                count += 1
                total += member.size
                if count > 5000 or total > 200 * 1024 * 1024:
                    raise ValueError('VENDOR_ARCHIVE_LIMIT_EXCEEDED')
                archive.extract(member, path=stage, filter='data')
        stage.rename(destination)
    return {'status': 'MATERIALIZED_SOURCE_ONLY', 'name': name, 'files': count,
            'runtime_executed': False, 'predictive_weight': 0.0}

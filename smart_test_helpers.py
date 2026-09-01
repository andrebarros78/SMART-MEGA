from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def make_valid_freeze_fixture(cc, path: Path, target: int, snapshot: dict[str, Any], champion_top6, challenger_top6, **event_extra):
    fixture_hash = 'f' * 64
    data_hash = 'd' * 64
    artifact = {
        'schema': 'SMART_TEST_FREEZE_FIXTURE_1',
        'target_contest': int(target),
        'cutoff_contest': int(target) - 1,
        'frozen_before_result': True,
        'causal_cutoff': True,
        'data_sha256': data_hash,
        'champion': {'top6': list(champion_top6)},
        'challenger': {'top6': list(challenger_top6), **snapshot},
        'fixture_sha256': fixture_hash,
    }
    path.write_text(json.dumps(artifact, ensure_ascii=False), encoding='utf-8')
    event = {
        'event_type': 'FREEZE',
        'target_contest': int(target),
        'cutoff_contest': int(target) - 1,
        'freeze_file': str(path),
        'freeze_sha256': cc.sha256(path),
        'data_sha256': data_hash,
        'frozen_before_result': True,
        'causal_cutoff': True,
        'snapshot': snapshot,
        'champion_top6': list(champion_top6),
        'challenger_top6': list(challenger_top6),
        'hashes': {'fixture': fixture_hash},
    }
    event.update(event_extra)
    return event


def bind_valid_freeze_fixture(cc, path: Path, event: dict[str, Any]) -> dict[str, Any]:
    target = int(event['target_contest'])
    snapshot = event.get('snapshot', {})
    champion_top6 = event['champion_top6']
    challenger_top6 = event['challenger_top6']
    fixture_hash = 'f' * 64
    data_hash = event.get('data_sha256', 'd' * 64)
    artifact = {
        'schema': 'SMART_TEST_FREEZE_FIXTURE_1',
        'target_contest': target,
        'cutoff_contest': target - 1,
        'frozen_before_result': True,
        'causal_cutoff': True,
        'data_sha256': data_hash,
        'champion': {'top6': list(champion_top6)},
        'challenger': {'top6': list(challenger_top6), **snapshot},
        'fixture_sha256': fixture_hash,
    }
    path.write_text(json.dumps(artifact, ensure_ascii=False), encoding='utf-8')
    event['freeze_file'] = str(path)
    event['freeze_sha256'] = cc.sha256(path)
    event['cutoff_contest'] = target - 1
    event['data_sha256'] = data_hash
    event['frozen_before_result'] = True
    event['causal_cutoff'] = True
    event['hashes'] = {'fixture': fixture_hash}
    return event

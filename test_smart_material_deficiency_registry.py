import copy
import json
from pathlib import Path

import pytest

import smart_material_deficiency_registry as mdr


def _resolved():
    return {'id':'D1','severity':'P0','status':'RESOLVED','summary':'fixed','evidence':['test::evidence']}


def test_open_deficiency_is_reported_and_resolved_registry_is_clean(tmp_path):
    clean = mdr.build_registry([_resolved()])
    p = tmp_path / 'registry.json'
    mdr.write_registry(p, clean)
    snap = mdr.load_registry(p, root=tmp_path)
    assert snap['status'] == 'PASS' and snap['open_count'] == 0 and snap['open_deficiencies'] == []
    assert snap['entry_count'] == 1 and snap['all_entries_validated'] is True

    open_reg = mdr.build_registry([{'id':'D2','severity':'P1','status':'OPEN','summary':'open','evidence':[]}])
    q = tmp_path / 'open.json'
    mdr.write_registry(q, open_reg)
    blocked = mdr.load_registry(q, root=tmp_path)
    assert blocked['status'] == 'BLOCKED'
    assert blocked['open_count'] == 1 and blocked['open_deficiencies'] == ['D2']
    assert blocked['open_entries'][0]['severity'] == 'P1'


def test_registry_missing_tampered_and_invalid_entries_fail_closed(tmp_path):
    with pytest.raises(ValueError, match='missing'):
        mdr.load_registry(tmp_path/'missing.json', root=tmp_path)

    good = mdr.build_registry([_resolved()])
    p = tmp_path/'r.json'; p.write_text(json.dumps(good), encoding='utf-8')
    bad = copy.deepcopy(good); bad['entries'][0]['summary'] = 'tampered'
    p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='self-hash'):
        mdr.load_registry(p, root=tmp_path)

    bad = copy.deepcopy(good); bad['schema'] = 'bad'; p.write_text(json.dumps(bad),encoding='utf-8')
    with pytest.raises(ValueError, match='schema'):
        mdr.load_registry(p, root=tmp_path)

    bad = copy.deepcopy(good); bad['rules']['self_hash_required'] = False; bad['sha256'] = mdr.sha256_json({k:v for k,v in bad.items() if k!='sha256'}); p.write_text(json.dumps(bad),encoding='utf-8')
    with pytest.raises(ValueError, match='rules'):
        mdr.load_registry(p, root=tmp_path)

    bad = copy.deepcopy(good); bad['entries'] = {}; bad['sha256'] = mdr.sha256_json({k:v for k,v in bad.items() if k!='sha256'}); p.write_text(json.dumps(bad),encoding='utf-8')
    with pytest.raises(ValueError, match='entries'):
        mdr.load_registry(p, root=tmp_path)

    invalids = [
        [None],
        [{'id':'','severity':'P0','status':'OPEN','summary':'x','evidence':[]}],
        [_resolved(), _resolved()],
        [{'id':'D','severity':'PX','status':'OPEN','summary':'x','evidence':[]}],
        [{'id':'D','severity':'P0','status':'BAD','summary':'x','evidence':[]}],
        [{'id':'D','severity':'P0','status':'OPEN','summary':'','evidence':[]}],
        [{'id':'D','severity':'P0','status':'OPEN','summary':'x','evidence':'bad'}],
        [{'id':'D','severity':'P0','status':'OPEN','summary':'x','evidence':['']}],
        [{'id':'D','severity':'P0','status':'RESOLVED','summary':'x','evidence':[]}],
    ]
    for entries in invalids:
        with pytest.raises(ValueError):
            mdr.build_registry(entries)


def test_registry_write_guards_and_relative_load(tmp_path):
    reg = mdr.build_registry([_resolved()])
    p = tmp_path/'r.json'
    h = mdr.write_registry(p, reg)
    assert h == mdr.sha256_file(p)
    assert mdr.load_registry(Path('r.json'), root=tmp_path)['file_sha256'] == h
    with pytest.raises(FileExistsError):
        mdr.write_registry(p, reg)
    with pytest.raises(ValueError, match='object'):
        mdr.write_registry(tmp_path/'bad1.json', [])
    bad = dict(reg); bad['sha256'] = 'short'
    with pytest.raises(ValueError, match='self-hashed'):
        mdr.write_registry(tmp_path/'bad2.json', bad)


def test_build_registry_accepts_reopened_and_hash_helpers():
    reg = mdr.build_registry([{'id':'D3','severity':'P3','status':'REOPENED','summary':'again','evidence':['x']}])
    assert len(reg['sha256']) == 64
    assert reg['rules']['open_statuses'] == ['OPEN','REOPENED']


def test_replace_with_retry_falls_back_when_replace_is_denied(tmp_path, monkeypatch):
    source = tmp_path / 'source.json'
    target = tmp_path / 'target.json'
    source.write_text('new', encoding='utf-8')
    target.write_text('old', encoding='utf-8')
    original_replace = Path.replace
    calls = {'count': 0}

    def denied_replace(self, other):
        if self == source:
            calls['count'] += 1
            raise PermissionError('replace denied')
        return original_replace(self, other)

    monkeypatch.setattr(Path, 'replace', denied_replace)
    mdr._replace_with_retry(source, target, attempts=2, delay_seconds=0)
    assert calls['count'] == 2
    assert target.read_text(encoding='utf-8') == 'new'
    assert not target.with_name(target.name + '.replace-backup').exists()


def test_upsert_deficiency_opens_reopens_and_preserves_integrity(tmp_path):
    path = tmp_path / 'registry.json'
    base = mdr.build_registry([{'id':'D37','severity':'P0','status':'RESOLVED','summary':'fixed','evidence':['old-proof']}])
    mdr.write_registry(path, base)
    snap = mdr.upsert_deficiency(path, {'id':'D37','severity':'P0','status':'OPEN','summary':'failed again','evidence':['new-proof']}, root=tmp_path)
    assert snap['status'] == 'BLOCKED' and snap['open_count'] == 1
    assert snap['open_entries'][0]['status'] == 'REOPENED'
    assert mdr.load_registry(path, root=tmp_path) == snap

    tampered = json.loads(path.read_text(encoding='utf-8'))
    tampered['entries'][0]['summary'] = 'tampered'
    path.write_text(json.dumps(tampered), encoding='utf-8')
    with pytest.raises(ValueError, match='self-hash'):
        mdr.upsert_deficiency(path, {'id':'D38','severity':'P1','status':'OPEN','summary':'x','evidence':[]}, root=tmp_path)

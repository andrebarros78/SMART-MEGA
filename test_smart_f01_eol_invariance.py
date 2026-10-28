"""EOL-independent F01 identity must still reject real Python source mutations."""
from pathlib import Path

from smart_component_reachability import build_registry

ROOT=Path(__file__).resolve().parent
TARGET=ROOT/'test_smart_mega_week_2026_schedule.py'


def _registry_with_virtual_bytes(monkeypatch, changed: bytes):
    original_read=Path.read_bytes
    with monkeypatch.context() as patched:
        def read(path):
            if Path(path).resolve()==TARGET:
                return changed
            return original_read(path)
        patched.setattr(Path,'read_bytes',read)
        return build_registry(ROOT)


def test_f01_eol_changes_do_not_alter_inventory_identity(monkeypatch):
    initial=build_registry(ROOT)
    raw=TARGET.read_bytes()
    assert b'\n' in raw
    lf=raw.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    alternate=lf if lf!=raw else lf.replace(b'\n',b'\r\n')
    assert raw!=alternate
    changed=_registry_with_virtual_bytes(monkeypatch,alternate)
    assert initial['gate']['status']=='PASS'
    assert changed['gate']['status']=='PASS'
    assert changed['inventory_sha256']==initial['inventory_sha256']
    original_item=next(x for x in initial['components'] if x['source_file']==TARGET.name)
    changed_item=next(x for x in changed['components'] if x['source_file']==TARGET.name)
    assert original_item['sha256']==changed_item['sha256']


def test_f01_real_non_eol_change_is_still_detected(monkeypatch):
    initial=build_registry(ROOT)
    changed=_registry_with_virtual_bytes(monkeypatch,TARGET.read_bytes()+b'\n# RESEARCH_REGRESSION_TAMPER\n')
    assert changed['gate']['status']=='PASS'
    assert changed['inventory_sha256']!=initial['inventory_sha256']
    original_item=next(x for x in initial['components'] if x['source_file']==TARGET.name)
    changed_item=next(x for x in changed['components'] if x['source_file']==TARGET.name)
    assert original_item['sha256']!=changed_item['sha256']
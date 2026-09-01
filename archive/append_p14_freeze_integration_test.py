from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_independent_audit.py'
s=p.read_text(encoding='utf-8')
add=r'''


def test_p14_future_freeze_hashes_and_snapshots_independent_audit(tmp_path: Path):
    import smart_champion_challenger as cc
    data=tmp_path/'pre.xlsx'; _dataset(35,seed=1415).to_excel(data,index=False)
    out=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    cwd=Path.cwd()
    try:
        # Component hashes are resolved from the canonical project working directory.
        result=cc.freeze_champion_challenger(data,36,out,ledger,state,start=20)
    finally:
        assert Path.cwd()==cwd
    assert result['status']=='FROZEN'
    frozen=json.loads(out.read_text()); L=json.loads(ledger.read_text()); ev=L['events'][0]
    assert frozen['independent_audit_sha256']==ia.sha256_file(Path('smart_independent_audit.py'))
    assert frozen['independent_audit_policy']['schema']=='SMART_INDEPENDENT_AUDIT_POLICY_1'
    assert frozen['independent_audit_policy']['promotion_authority'] is False
    assert ev['hashes']['independent_audit']==frozen['independent_audit_sha256']
    assert ev['snapshot']['independent_audit_policy']==frozen['independent_audit_policy']
'''
if 'test_p14_future_freeze_hashes_and_snapshots_independent_audit' not in s:
    s += add
p.write_text(s,encoding='utf-8')
print('P14 freeze integration test appended')

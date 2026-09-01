from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_sequential_prospective_proof.py'
s=p.read_text(encoding='utf-8-sig')
add=r'''

def test_all_proven_gate_calls_continuous_red_team_freshness(monkeypatch, tmp_path: Path):
    import smart_continuous_red_team as rt
    gate=tmp_path/'gate.json'
    obj={'schema':cc.PRE_3052_GATE_SCHEMA,'freeze_allowed':True,
         'items':[{'priority':i,'id':f'P{i:02d}','status':'PROVEN','evidence':[{'proof':'x'}]} for i in range(1,16)]}
    gate.write_text(json.dumps(obj))
    seen={}
    def fake_verify(*, root):
        seen['root']=Path(root); return {'status':'PASS'}
    monkeypatch.setattr(rt,'verify_latest_report',fake_verify)
    out=cc.require_pre_3052_gate(3052,gate)
    assert out['freeze_allowed'] is True and seen['root']==tmp_path.resolve()
'''
if 'test_all_proven_gate_calls_continuous_red_team_freshness' not in s: s+=add
p.write_text(s,encoding='utf-8')
print('p12 gate coverage appended')

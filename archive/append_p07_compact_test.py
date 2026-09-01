from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_multi_challengers.py')
s=p.read_text(encoding='utf-8-sig')
append=r'''

def test_compact_replay_mode_preserves_decisions_without_full_audit_payload():
    scores,w,m,f,r=_inputs()
    full=build_multi_challengers(scores,w,m,f,r,{'active':True},audit_detail=True)
    compact=build_multi_challengers(scores,w,m,f,r,{'active':True},audit_detail=False)
    for pid in POLICY_IDS:
        assert compact['policies'][pid]['top6']==full['policies'][pid]['top6']
        assert compact['policies'][pid]['weights']==full['policies'][pid]['weights']
        assert compact['policies'][pid]['ranking60']==[]
        assert compact['policies'][pid]['aggregate_scores']=={}
        assert compact['policies'][pid]['audit_detail'] is False
        assert full['policies'][pid]['audit_detail'] is True
'''
if 'test_compact_replay_mode_preserves_decisions' not in s: s+=append
p.write_text(s,encoding='utf-8')
print('appended compact test')
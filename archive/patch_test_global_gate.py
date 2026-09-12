from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_sequential_prospective_proof.py')
s=p.read_text(encoding='utf-8-sig')
old="""def test_all_proven_gate_calls_continuous_red_team_freshness(monkeypatch, tmp_path: Path):\n    import smart_continuous_red_team as rt\n"""
new="""def test_all_proven_gate_calls_continuous_red_team_freshness(monkeypatch, tmp_path: Path):\n    import smart_continuous_red_team as rt\n    import smart_global_integrity as gi\n"""
if old not in s: raise SystemExit('test import marker missing')
s=s.replace(old,new,1)
old2="""    monkeypatch.setattr(rt,'verify_latest_report',fake_verify)\n    monkeypatch.setattr(cc,'PRE_3052_GATE_PATH',gate)\n"""
new2="""    monkeypatch.setattr(rt,'verify_latest_report',fake_verify)\n    monkeypatch.setattr(gi,'verify_global_integrity',lambda **kwargs: {'status':'PASS'})\n    monkeypatch.setattr(cc,'PRE_3052_GATE_PATH',gate)\n"""
if old2 not in s: raise SystemExit('test monkeypatch marker missing')
s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8')
print('GLOBAL_GATE_TEST_PATCH_OK')

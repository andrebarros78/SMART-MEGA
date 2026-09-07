from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_coverage_governance.py')
s=p.read_text(encoding='utf-8-sig')
old="""    monkeypatch.setattr(sys, 'argv', ['smart_champion_challenger.py','--data',str(data),'--target','31','--out',str(out),'--ledger',str(led),'--state',str(state),'--start','10'])
    runpy.run_path(str(Path(cc.__file__)), run_name='__main__')
"""
new="""    import smart_target_schedule as sts
    synthetic_schedule = {"schema": sts.SCHEMA, "target_contest": 31, "scheduled_datetime": "2099-01-01T00:00:00+00:00"}
    monkeypatch.setattr(sts, "resolve_target_schedule", lambda *args, **kwargs: synthetic_schedule)
    monkeypatch.setattr(sts, "assert_pre_draw_window", lambda schedule, **kwargs: {"schema": sts.TEMPORAL_GUARD_SCHEMA, "status": "PASS", "target_contest": 31, "before_scheduled_draw": True, "result_used": False})
    monkeypatch.setattr(sys, 'argv', ['smart_champion_challenger.py','--data',str(data),'--target','31','--out',str(out),'--ledger',str(led),'--state',str(state),'--start','10'])
    runpy.run_path(str(Path(cc.__file__)), run_name='__main__')
"""
if old not in s:
    raise SystemExit('CLI test block not found')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('PATCH_TEST_CLI=PASS')

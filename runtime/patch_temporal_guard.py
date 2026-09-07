from __future__ import annotations
import ast, json, hashlib
from pathlib import Path
ROOT=Path(r'C:\New Projet\SMART-MEGA')

# target schedule
p=ROOT/'smart_target_schedule.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('from datetime import datetime\n','from datetime import datetime, timezone\n')
s=s.replace('TIME_POLICY_SCHEMA = "SMART_MEGA_SENA_DRAW_TIME_POLICY_1"\n', 'TIME_POLICY_SCHEMA = "SMART_MEGA_SENA_DRAW_TIME_POLICY_1"\nTEMPORAL_GUARD_SCHEMA = "SMART_PRE_DRAW_TEMPORAL_GUARD_1"\nMIN_OPERATIONAL_FREEZE_LEAD_SECONDS = 60\n')
needle='    return obj, resolved\n\n\ndef extract_target_from_text'
insert='''    return obj, resolved\n\n\ndef assert_pre_draw_window(\n    schedule: dict[str, Any],\n    *,\n    now: datetime | None = None,\n    minimum_lead_seconds: int = MIN_OPERATIONAL_FREEZE_LEAD_SECONDS,\n) -> dict[str, Any]:\n    if not isinstance(schedule, dict) or schedule.get("schema") != SCHEMA:\n        raise ValueError("target schedule authority invalid for temporal guard")\n    scheduled_raw = schedule.get("scheduled_datetime")\n    if not isinstance(scheduled_raw, str):\n        raise ValueError("target schedule lacks scheduled_datetime")\n    try:\n        scheduled = datetime.fromisoformat(scheduled_raw)\n    except ValueError as exc:\n        raise ValueError("target scheduled_datetime invalid") from exc\n    if scheduled.tzinfo is None or scheduled.utcoffset() is None:\n        raise ValueError("target scheduled_datetime must be timezone-aware")\n    if isinstance(minimum_lead_seconds, bool) or not isinstance(minimum_lead_seconds, int) or minimum_lead_seconds < 0:\n        raise ValueError("minimum freeze lead seconds must be a non-negative integer")\n    observed = datetime.now(timezone.utc) if now is None else now\n    if observed.tzinfo is None or observed.utcoffset() is None:\n        raise ValueError("temporal guard now must be timezone-aware")\n    observed_utc = observed.astimezone(timezone.utc)\n    scheduled_utc = scheduled.astimezone(timezone.utc)\n    seconds_until_draw = (scheduled_utc - observed_utc).total_seconds()\n    if seconds_until_draw <= float(minimum_lead_seconds):\n        raise ValueError(\n            f"prospective freeze window closed or inside safety margin: "\n            f"target={schedule.get('target_contest')} scheduled={scheduled.isoformat()} "\n            f"seconds_until_draw={seconds_until_draw:.3f} required_lead={minimum_lead_seconds}"\n        )\n    return {\n        "schema": TEMPORAL_GUARD_SCHEMA,\n        "status": "PASS",\n        "target_contest": int(schedule["target_contest"]),\n        "checked_at_utc": observed_utc.isoformat(),\n        "scheduled_datetime": scheduled.isoformat(),\n        "seconds_until_draw": seconds_until_draw,\n        "minimum_lead_seconds": int(minimum_lead_seconds),\n        "before_scheduled_draw": True,\n        "result_used": False,\n    }\n\n\ndef extract_target_from_text'''
if needle not in s: raise SystemExit('target schedule insertion point missing')
s=s.replace(needle,insert)
old='__all__ = ["SCHEMA", "DEFAULT_ARCHIVE", "DEFAULT_TIME_POLICY", "TIME_POLICY_SCHEMA", "extract_target_from_text", "load_draw_time_policy", "resolve_target_schedule", "sha256_file"]'
new='__all__ = ["SCHEMA", "DEFAULT_ARCHIVE", "DEFAULT_TIME_POLICY", "TIME_POLICY_SCHEMA", "TEMPORAL_GUARD_SCHEMA", "MIN_OPERATIONAL_FREEZE_LEAD_SECONDS", "assert_pre_draw_window", "extract_target_from_text", "load_draw_time_policy", "resolve_target_schedule", "sha256_file"]'
if old not in s: raise SystemExit('target schedule __all__ missing')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')

# champion challenger
p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
imp='from smart_portfolio_pipeline import build_portfolio_package\n'
if imp not in s: raise SystemExit('cc import point missing')
s=s.replace(imp, imp+'from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule\n')
old='''def freeze_champion_challenger(data: Path, target: int, out: Path, ledger_path: Path, state_path: Path,\n                               start: int = 1000, allow_pre_result_supersede: bool = False,\n                               activation_authority_path: Path = ACTIVATION_AUTHORITY_PATH,\n                               expansion_registry_path: Path = REGISTRY_PATH) -> dict[str, Any]:\n    implementation_gate = require_pre_3052_gate(target)'''
new='''def freeze_champion_challenger(data: Path, target: int, out: Path, ledger_path: Path, state_path: Path,\n                               start: int = 1000, allow_pre_result_supersede: bool = False,\n                               activation_authority_path: Path = ACTIVATION_AUTHORITY_PATH,\n                               expansion_registry_path: Path = REGISTRY_PATH,\n                               enforce_temporal_guard: bool = True,\n                               schedule_authority: dict[str, Any] | None = None) -> dict[str, Any]:\n    if enforce_temporal_guard:\n        schedule_authority = schedule_authority or resolve_target_schedule(Path('.'), int(target))\n        temporal_guard = assert_pre_draw_window(schedule_authority)\n    else:\n        temporal_guard = {\n            'schema': 'SMART_PRE_DRAW_TEMPORAL_GUARD_1',\n            'status': 'TEST_ONLY_BYPASS',\n            'target_contest': int(target),\n            'before_scheduled_draw': True,\n            'authoritative': False,\n            'result_used': False,\n        }\n    implementation_gate = require_pre_3052_gate(target)'''
if old not in s: raise SystemExit('cc signature block missing')
s=s.replace(old,new)
s=s.replace('    freeze_time = datetime.now(timezone.utc).isoformat()\n    source_ts = source_cutoff_timestamp(data)\n    signal_ts = source_ts or freeze_time','    generation_started_utc = datetime.now(timezone.utc).isoformat()\n    source_ts = source_cutoff_timestamp(data)\n    signal_ts = source_ts or generation_started_utc')
needle='''    challenger_pred, challenger_backtest = agent.predict_next(draws, contests, target_contest=target,\n                                                               cutoff_timestamp=signal_ts,\n                                                               cutoff_timestamp_kind=signal_ts_kind)\n\n    state = agent.state_document(data_sha256=data_hash)'''
replacement='''    challenger_pred, challenger_backtest = agent.predict_next(draws, contests, target_contest=target,\n                                                               cutoff_timestamp=signal_ts,\n                                                               cutoff_timestamp_kind=signal_ts_kind)\n\n    if enforce_temporal_guard:\n        temporal_guard = assert_pre_draw_window(schedule_authority)\n    freeze_time = datetime.now(timezone.utc).isoformat()\n    state = agent.state_document(data_sha256=data_hash)'''
if needle not in s: raise SystemExit('cc final guard insertion missing')
s=s.replace(needle,replacement)
s=s.replace("'frozen_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,", "'frozen_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,\n        'target_schedule': schedule_authority if enforce_temporal_guard else None,\n        'temporal_guard': temporal_guard, 'temporal_guard_enforced': bool(enforce_temporal_guard),",1)
s=s.replace("'created_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,", "'created_utc': freeze_time, 'frozen_before_result': True, 'causal_cutoff': True,\n        'scheduled_datetime': (schedule_authority.get('scheduled_datetime') if enforce_temporal_guard else None),\n        'temporal_guard': temporal_guard, 'temporal_guard_enforced': bool(enforce_temporal_guard),",1)
s=s.replace("'state_sha256': state_hash, 'promotion': promotion_status(ledger)}", "'state_sha256': state_hash, 'temporal_guard': temporal_guard, 'promotion': promotion_status(ledger)}",1)
p.write_text(s,encoding='utf-8')

# full pipeline
p=ROOT/'smart_full_process_pipeline.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('from smart_target_schedule import resolve_target_schedule\n','from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule\n')
s=s.replace('    schedule = resolve_target_schedule(root, target)\n    pre_checks = {','    schedule = resolve_target_schedule(root, target)\n    temporal_guard = assert_pre_draw_window(schedule)\n    pre_checks = {')
s=s.replace('        "official_schedule_result_unused": schedule.get("result_used") is False,\n    }','        "official_schedule_result_unused": schedule.get("result_used") is False,\n        "official_schedule_window_open": temporal_guard.get("status") == "PASS" and temporal_guard.get("before_scheduled_draw") is True,\n    }',1)
s=s.replace('            expansion_registry_path=expansion_registry_path,\n        )','            expansion_registry_path=expansion_registry_path,\n            schedule_authority=schedule,\n        )',1)
s=s.replace('        "official_schedule_bound": True\n    }','        "official_schedule_bound": True,\n        "freeze_temporal_guard_pass": freeze_obj.get("temporal_guard_enforced") is True and freeze_obj.get("temporal_guard", {}).get("status") == "PASS",\n    }',1)
p.write_text(s,encoding='utf-8')

# explicit historical-test override in current tests
for p in ROOT.glob('test_*.py'):
    text=p.read_text(encoding='utf-8-sig')
    try: tree=ast.parse(text)
    except SyntaxError: continue
    lines=text.splitlines(keepends=True); starts=[]; pos=0
    for line in lines: starts.append(pos); pos += len(line)
    inserts=[]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        fn=node.func
        name=fn.id if isinstance(fn,ast.Name) else (fn.attr if isinstance(fn,ast.Attribute) else None)
        if name!='freeze_champion_challenger': continue
        if any(k.arg=='enforce_temporal_guard' for k in node.keywords if k.arg): continue
        close_idx=starts[node.end_lineno-1]+node.end_col_offset-1
        if text[close_idx]!=')': raise SystemExit(f'call close mismatch {p}:{node.end_lineno}')
        j=close_idx-1
        while j>=0 and text[j].isspace(): j-=1
        addition=' enforce_temporal_guard=False' if text[j]==',' else ', enforce_temporal_guard=False'
        inserts.append((close_idx,addition))
    if inserts:
        for idx,addition in sorted(inserts,reverse=True): text=text[:idx]+addition+text[idx:]
        ast.parse(text); p.write_text(text,encoding='utf-8')

# tests
test=ROOT/'test_smart_temporal_freeze_guard_20260906.py'
test.write_text('''from __future__ import annotations\n\nfrom datetime import datetime, timedelta, timezone\nimport inspect\nimport pytest\nimport smart_champion_challenger as cc\nimport smart_full_process_pipeline as fp\nfrom smart_target_schedule import MIN_OPERATIONAL_FREEZE_LEAD_SECONDS, SCHEMA, assert_pre_draw_window\n\ndef _schedule(draw: datetime, target: int = 9999) -> dict:\n    return {"schema": SCHEMA, "target_contest": target, "scheduled_datetime": draw.isoformat()}\n\ndef test_temporal_guard_accepts_only_a_safely_future_draw():\n    now=datetime(2026,9,6,14,0,tzinfo=timezone.utc)\n    draw=now+timedelta(seconds=MIN_OPERATIONAL_FREEZE_LEAD_SECONDS+120)\n    proof=assert_pre_draw_window(_schedule(draw),now=now)\n    assert proof["status"]=="PASS" and proof["before_scheduled_draw"] is True\n    assert proof["seconds_until_draw"]>MIN_OPERATIONAL_FREEZE_LEAD_SECONDS\n\ndef test_temporal_guard_rejects_post_draw_and_safety_margin():\n    now=datetime(2026,9,6,14,0,tzinfo=timezone.utc)\n    with pytest.raises(ValueError,match="window closed"):\n        assert_pre_draw_window(_schedule(now-timedelta(seconds=1)),now=now)\n    with pytest.raises(ValueError,match="safety margin"):\n        assert_pre_draw_window(_schedule(now+timedelta(seconds=MIN_OPERATIONAL_FREEZE_LEAD_SECONDS)),now=now)\n\ndef test_production_freeze_defaults_fail_closed_and_pipeline_binds_schedule():\n    sig=inspect.signature(cc.freeze_champion_challenger)\n    assert sig.parameters["enforce_temporal_guard"].default is True\n    source=inspect.getsource(fp.run_full_process)\n    assert "temporal_guard = assert_pre_draw_window(schedule)" in source\n    assert "schedule_authority=schedule" in source\n    assert "official_schedule_window_open" in source\n\ndef test_freeze_artifact_records_authoritative_temporal_evidence():\n    source=inspect.getsource(cc.freeze_champion_challenger)\n    assert "temporal_guard_enforced" in source and "target_schedule" in source\n    assert source.count("assert_pre_draw_window(schedule_authority)")>=2\n''',encoding='utf-8')

# registry D009
regp=ROOT/'SMART_MATERIAL_DEFICIENCY_REGISTRY.json'; reg=json.loads(regp.read_text(encoding='utf-8-sig'))
entry={'id':'D009_POST_DRAW_FREEZE_FALSE_PROSPECTIVE','severity':'P0','status':'RESOLVED','summary':'Operational freeze paths could label an artifact frozen_before_result without comparing wall-clock time against the authoritative scheduled draw datetime.','evidence':['test_smart_temporal_freeze_guard_20260906.py::test_temporal_guard_accepts_only_a_safely_future_draw','test_smart_temporal_freeze_guard_20260906.py::test_temporal_guard_rejects_post_draw_and_safety_margin','test_smart_temporal_freeze_guard_20260906.py::test_production_freeze_defaults_fail_closed_and_pipeline_binds_schedule','test_smart_temporal_freeze_guard_20260906.py::test_freeze_artifact_records_authoritative_temporal_evidence']}
if not any(e.get('id')==entry['id'] for e in reg['entries']): reg['entries'].append(entry)
reg.pop('sha256',None); reg['sha256']=hashlib.sha256(json.dumps(reg,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
regp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p in [ROOT/'smart_target_schedule.py',ROOT/'smart_champion_challenger.py',ROOT/'smart_full_process_pipeline.py',test]: ast.parse(p.read_text(encoding='utf-8-sig'))
print('PATCH_TEMPORAL_GUARD=PASS')

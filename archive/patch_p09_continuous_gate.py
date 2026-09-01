from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
old="    if pending or obj.get('freeze_allowed') is not True:\n        raise ValueError(f'SMART pre-3052 implementation gate blocked; pending={pending}')\n    return obj\n"
new="    if pending or obj.get('freeze_allowed') is not True:\n        raise ValueError(f'SMART pre-3052 implementation gate blocked; pending={pending}')\n    # Continuous Red Team freshness is enforced only after all 15 implementation gates open.\n    from smart_continuous_red_team import verify_latest_report\n    verify_latest_report(root=gate_path.resolve().parent)\n    return obj\n"
if old not in s:
    raise SystemExit('gate marker not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
# architecture: include P09 leaf and prohibit upward orchestration imports.
a=ROOT/'test_smart_architecture_alignment.py'
t=a.read_text(encoding='utf-8-sig')
if "'smart_continuous_red_team.py'," not in t:
    t=t.replace("    'smart_meta_governor.py',\n", "    'smart_meta_governor.py',\n    'smart_continuous_red_team.py',\n")
marker="    assert deps['smart_contextual_meta_weights.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()\n"
if marker in t and "deps['smart_continuous_red_team.py']" not in t:
    t=t.replace(marker,marker+"    # Red Team may consume the stack for testing, but production signal layers must not depend on Red Team.\n    assert 'smart_continuous_red_team' not in deps['smart_signal_agent.py']\n    assert 'smart_continuous_red_team' not in deps['smart_v2_engine.py']\n")
a.write_text(t,encoding='utf-8')
print('patched')

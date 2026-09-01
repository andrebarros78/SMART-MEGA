from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

cc = ROOT / 'smart_champion_challenger.py'
s = cc.read_text(encoding='utf-8-sig')

repls = [
    ("        'promotion_gate': sha256(Path('smart_promotion_gate.py')),\n",
     "        'promotion_gate': sha256(Path('smart_promotion_gate.py')),\n        'independent_audit': sha256(Path('smart_independent_audit.py')),\n"),
    ("    sequential_snapshot = sequential_freeze_snapshot()\n",
     "    sequential_snapshot = sequential_freeze_snapshot()\n    from smart_independent_audit import policy_snapshot as independent_audit_policy_snapshot\n    independent_audit_snapshot = independent_audit_policy_snapshot()\n"),
    ("        'promotion_gate_sha256': component_hashes['promotion_gate'],\n",
     "        'promotion_gate_sha256': component_hashes['promotion_gate'],\n        'independent_audit_sha256': component_hashes['independent_audit'],\n"),
    ("        'promotion_policy': policy_snapshot(),\n",
     "        'promotion_policy': policy_snapshot(),\n        'independent_audit_policy': independent_audit_snapshot,\n"),
    ("                     'promotion_policy': freeze_obj['promotion_policy']},\n",
     "                     'promotion_policy': freeze_obj['promotion_policy'],\n                     'independent_audit_policy': freeze_obj['independent_audit_policy']},\n"),
]
for old, new in repls:
    if new.strip() in s:
        continue
    if old not in s:
        raise SystemExit('missing marker: ' + old[:90])
    s = s.replace(old, new, 1)
cc.write_text(s, encoding='utf-8')

arch = ROOT / 'test_smart_architecture_alignment.py'
t = arch.read_text(encoding='utf-8-sig')
if "    'smart_promotion_gate.py',\n" not in t:
    marker = "    'smart_sequential_prospective_proof.py',\n"
    if marker not in t:
        raise SystemExit('CORE sequential marker missing')
    t = t.replace(marker, marker + "    'smart_promotion_gate.py',\n", 1)
if "    'smart_independent_audit.py',\n" not in t:
    marker = "    'smart_promotion_gate.py',\n"
    t = t.replace(marker, marker + "    'smart_independent_audit.py',\n", 1)

needle = "    assert 'smart_signal_expansion_governance' not in deps['smart_v2_engine.py']\n"
addition = "    assert deps['smart_independent_audit.py'] & {'smart_champion_challenger','smart_promotion_gate','adjudicate_signal_challenger'} == set()\n"
if addition.strip() not in t:
    if needle not in t:
        raise SystemExit('architecture dependency marker missing')
    t = t.replace(needle, needle + addition, 1)

marker = "        \"'signal_interactions': sha256(Path('smart_signal_interactions.py'))\",\n"
extra = "        \"'promotion_gate': sha256(Path('smart_promotion_gate.py'))\",\n        \"'independent_audit': sha256(Path('smart_independent_audit.py'))\",\n"
if "\"'independent_audit': sha256(Path('smart_independent_audit.py'))\"" not in t:
    if marker not in t:
        raise SystemExit('hash marker missing')
    t = t.replace(marker, marker + extra, 1)

assert_marker = "    assert \"'signal_interactions': freeze_obj['challenger']['signal_interactions']\" in text\n"
assert_extra = "    assert \"'independent_audit_sha256': component_hashes['independent_audit']\" in text\n    assert \"'independent_audit_policy': independent_audit_snapshot\" in text\n"
if "independent_audit_sha256" not in t:
    if assert_marker not in t:
        raise SystemExit('assert marker missing')
    t = t.replace(assert_marker, assert_marker + assert_extra, 1)

arch.write_text(t, encoding='utf-8')
print('P14 integration patched')

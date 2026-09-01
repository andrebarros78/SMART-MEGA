from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
if "'sequential_prospective_proof': sha256(Path('smart_sequential_prospective_proof.py'))" not in s:
    marker="        'signal_expansion_governance': sha256(Path('smart_signal_expansion_governance.py')),\n"
    if marker not in s: raise SystemExit('component marker')
    s=s.replace(marker,marker+"        'sequential_prospective_proof': sha256(Path('smart_sequential_prospective_proof.py')),\n",1)
if 'sequential_snapshot = sequential_freeze_snapshot()' not in s:
    marker="    expansion_registry_hash = sha256(REGISTRY_PATH) if REGISTRY_PATH.exists() else None\n"
    if marker not in s: raise SystemExit('snapshot creation marker')
    s=s.replace(marker,marker+"    from smart_sequential_prospective_proof import freeze_snapshot as sequential_freeze_snapshot\n    sequential_snapshot = sequential_freeze_snapshot()\n",1)
if "'sequential_prospective_proof_sha256'" not in s:
    marker="        'signal_expansion_governance_sha256': component_hashes['signal_expansion_governance'],\n"
    if marker not in s: raise SystemExit('freeze hash marker')
    s=s.replace(marker,marker+"        'sequential_prospective_proof_sha256': component_hashes['sequential_prospective_proof'],\n",1)
if "        'sequential_prospective_proof': sequential_snapshot,\n" not in s:
    marker="        'signal_expansion_governance': expansion_snapshot,\n"
    if marker not in s: raise SystemExit('freeze object marker')
    s=s.replace(marker,marker+"        'sequential_prospective_proof': sequential_snapshot,\n",1)
if "                     'sequential_prospective_proof': sequential_snapshot" not in s:
    marker="                     'signal_expansion_governance': expansion_governance.snapshot()},\n"
    if marker not in s: raise SystemExit('event snapshot marker')
    s=s.replace(marker,"                     'signal_expansion_governance': expansion_governance.snapshot(),\n                     'sequential_prospective_proof': sequential_snapshot},\n",1)
p.write_text(s,encoding='utf-8')
# architecture registry
ap=ROOT/'test_smart_architecture_alignment.py'
t=ap.read_text(encoding='utf-8-sig')
if "'smart_sequential_prospective_proof.py'," not in t:
    marker="    'smart_signal_expansion_governance.py',\n"
    if marker in t: t=t.replace(marker,marker+"    'smart_sequential_prospective_proof.py',\n",1)
ap.write_text(t,encoding='utf-8')
print('patched p12 v2')

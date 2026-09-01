from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
old="        'signal_expansion_governance': sha256(Path('smart_signal_expansion_governance.py')),\n"
new=old+"        'sequential_prospective_proof': sha256(Path('smart_sequential_prospective_proof.py')),\n"
if old not in s: raise SystemExit('component marker missing')
if "'sequential_prospective_proof': sha256" not in s: s=s.replace(old,new,1)
old2="    expansion_registry_hash = write_registry(REGISTRY_PATH, expansion_governance)\n"
new2=old2+"    from smart_sequential_prospective_proof import freeze_snapshot as sequential_freeze_snapshot\n    sequential_snapshot = sequential_freeze_snapshot()\n"
if old2 not in s: raise SystemExit('registry marker missing')
if 'sequential_snapshot = sequential_freeze_snapshot()' not in s: s=s.replace(old2,new2,1)
old3="        'signal_expansion_governance_sha256': component_hashes['signal_expansion_governance'],\n"
new3=old3+"        'sequential_prospective_proof_sha256': component_hashes['sequential_prospective_proof'],\n        'sequential_prospective_proof': sequential_snapshot,\n"
if old3 not in s: raise SystemExit('freeze hash marker missing')
if "'sequential_prospective_proof_sha256'" not in s: s=s.replace(old3,new3,1)
old4="                     'signal_expansion_governance': expansion_governance.snapshot()},\n"
new4="                     'signal_expansion_governance': expansion_governance.snapshot(),\n                     'sequential_prospective_proof': sequential_snapshot},\n"
if old4 not in s: raise SystemExit('snapshot marker missing')
s=s.replace(old4,new4,1)
p.write_text(s,encoding='utf-8')
# architecture registration
ap=ROOT/'test_smart_architecture_alignment.py'
t=ap.read_text(encoding='utf-8-sig')
if "'smart_sequential_prospective_proof.py'," not in t:
    anchor="    'smart_signal_expansion_governance.py',\n"
    if anchor in t: t=t.replace(anchor,anchor+"    'smart_sequential_prospective_proof.py',\n",1)
ap.write_text(t,encoding='utf-8')
print('patched p12 freeze')

from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
repls=[
("        'signal_expansion_governance': sha256(Path('smart_signal_expansion_governance.py')),\n","        'signal_expansion_governance': sha256(Path('smart_signal_expansion_governance.py')),\n        'sequential_prospective_proof': sha256(Path('smart_sequential_prospective_proof.py')),\n"),
("    expansion_registry_hash = sha256(REGISTRY_PATH) if REGISTRY_PATH.exists() else None\n","    expansion_registry_hash = sha256(REGISTRY_PATH) if REGISTRY_PATH.exists() else None\n    from smart_sequential_prospective_proof import freeze_snapshot as sequential_freeze_snapshot\n    sequential_snapshot = sequential_freeze_snapshot()\n"),
("        'signal_expansion_governance_sha256': component_hashes['signal_expansion_governance'],\n","        'signal_expansion_governance_sha256': component_hashes['signal_expansion_governance'],\n        'sequential_prospective_proof_sha256': component_hashes['sequential_prospective_proof'],\n"),
("        'signal_expansion_governance': expansion_snapshot,\n","        'signal_expansion_governance': expansion_snapshot,\n        'sequential_prospective_proof': sequential_snapshot,\n"),
("                     'signal_expansion_governance': expansion_snapshot},\n","                     'signal_expansion_governance': expansion_snapshot,\n                     'sequential_prospective_proof': sequential_snapshot},\n"),
]
for old,new in repls:
    if new.strip() in s: continue
    if old not in s: raise SystemExit('missing marker '+old[:60])
    s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
ap=ROOT/'test_smart_architecture_alignment.py'
t=ap.read_text(encoding='utf-8-sig')
if "'smart_sequential_prospective_proof.py'," not in t:
    marker="    'smart_signal_expansion_governance.py',\n"
    if marker in t: t=t.replace(marker,marker+"    'smart_sequential_prospective_proof.py',\n",1)
ap.write_text(t,encoding='utf-8')
print('patched p12 v3')

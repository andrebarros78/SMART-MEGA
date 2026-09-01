from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
if "        'signal_expansion_governance': expansion_snapshot,\n" not in s:
    marker="        'signal_expansion_registry_sha256': expansion_registry_hash,\n"
    s=s.replace(marker,marker+"        'signal_expansion_governance': expansion_snapshot,\n",1)
old="                     'bounded_online_learning': freeze_obj['challenger']['bounded_online_learning']},\n"
new="                     'bounded_online_learning': freeze_obj['challenger']['bounded_online_learning'],\n                     'signal_expansion_governance': expansion_snapshot},\n"
if old not in s: raise SystemExit('snapshot marker not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('fixed')

from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8')
s=s.replace("                     'multi_challengers': freeze_obj['challenger']['multi_challengers']},\n", "                     'multi_challengers': freeze_obj['challenger']['multi_challengers'],\n                     'meta_governor': freeze_obj['challenger']['meta_governor']},\n")
p.write_text(s,encoding='utf-8')
print('fixed p08 freeze snapshot')
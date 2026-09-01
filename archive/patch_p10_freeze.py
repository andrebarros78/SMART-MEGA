from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("        'meta_governor': sha256(Path('smart_meta_governor.py')),\n", "        'meta_governor': sha256(Path('smart_meta_governor.py')),\n        'bounded_online_learning': sha256(Path('smart_bounded_online_learning.py')),\n")
s=s.replace("        'meta_governor_sha256': component_hashes['meta_governor'],\n", "        'meta_governor_sha256': component_hashes['meta_governor'],\n        'bounded_online_learning_sha256': component_hashes['bounded_online_learning'],\n")
s=s.replace("                     'meta_governor': freeze_obj['challenger']['meta_governor']},\n", "                     'meta_governor': freeze_obj['challenger']['meta_governor'],\n                     'bounded_online_learning': freeze_obj['challenger']['bounded_online_learning']},\n")
p.write_text(s,encoding='utf-8')
print('patched freeze P10')

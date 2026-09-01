from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_champion_challenger.py'; s=p.read_text(encoding='utf-8')
s=s.replace("        'multi_challengers': sha256(Path('smart_multi_challengers.py')),\n", "        'multi_challengers': sha256(Path('smart_multi_challengers.py')),\n        'meta_governor': sha256(Path('smart_meta_governor.py')),\n") if "'multi_challengers': sha256" in s else s.replace("        'signal_interactions': sha256(Path('smart_signal_interactions.py')),\n", "        'signal_interactions': sha256(Path('smart_signal_interactions.py')),\n        'multi_challengers': sha256(Path('smart_multi_challengers.py')),\n        'meta_governor': sha256(Path('smart_meta_governor.py')),\n")
# direct freeze hash fields
if "'multi_challengers_sha256': component_hashes['multi_challengers']" in s and "'meta_governor_sha256'" not in s:
    s=s.replace("        'multi_challengers_sha256': component_hashes['multi_challengers'],\n", "        'multi_challengers_sha256': component_hashes['multi_challengers'],\n        'meta_governor_sha256': component_hashes['meta_governor'],\n")
elif "'meta_governor_sha256'" not in s:
    s=s.replace("        'signal_interactions_sha256': component_hashes['signal_interactions'],\n", "        'signal_interactions_sha256': component_hashes['signal_interactions'],\n        'multi_challengers_sha256': component_hashes['multi_challengers'],\n        'meta_governor_sha256': component_hashes['meta_governor'],\n")
# freeze snapshot
if "'multi_challengers': freeze_obj['challenger']['multi_challengers']" in s and "'meta_governor': freeze_obj['challenger']['meta_governor']" not in s:
    s=s.replace("                     'multi_challengers': freeze_obj['challenger']['multi_challengers'],\n", "                     'multi_challengers': freeze_obj['challenger']['multi_challengers'],\n                     'meta_governor': freeze_obj['challenger']['meta_governor'],\n")
elif "'meta_governor': freeze_obj['challenger']['meta_governor']" not in s:
    s=s.replace("                     'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration']},\n", "                     'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration'],\n                     'multi_challengers': freeze_obj['challenger']['multi_challengers'],\n                     'meta_governor': freeze_obj['challenger']['meta_governor']},\n")
# expose governed top6 in freeze/event
if "'governed_challenger_top6'" not in s:
    s=s.replace("        'signal_state_sha256': state_hash, 'champion': champion, 'challenger': challenger_pred.as_dict(),\n", "        'signal_state_sha256': state_hash, 'champion': champion, 'challenger': challenger_pred.as_dict(),\n        'governed_challenger_top6': challenger_pred.meta_governor['selected_top6'],\n        'governed_challenger_policy': challenger_pred.meta_governor['selected_policy'],\n")
    s=s.replace("        'champion_top6': champion['top6'], 'challenger_top6': freeze_obj['challenger']['top6'],\n", "        'champion_top6': champion['top6'], 'challenger_top6': freeze_obj['challenger']['top6'],\n        'governed_challenger_top6': freeze_obj['governed_challenger_top6'], 'governed_challenger_policy': freeze_obj['governed_challenger_policy'],\n")
p.write_text(s,encoding='utf-8')
# architecture test core + markers
p=ROOT/'test_smart_architecture_alignment.py'; t=p.read_text(encoding='utf-8')
if "'smart_meta_governor.py'" not in t:
    t=t.replace("    'smart_multi_challengers.py',\n", "    'smart_multi_challengers.py',\n    'smart_meta_governor.py',\n") if "'smart_multi_challengers.py'" in t else t.replace("    'smart_rank_score_calibration.py',\n", "    'smart_rank_score_calibration.py',\n    'smart_multi_challengers.py',\n    'smart_meta_governor.py',\n")
if "'smart_meta_governor'" not in t.split("assert {'smart_v2_engine'")[1].split("<= deps['smart_signal_agent.py']")[0]:
    t=t.replace("'smart_rank_score_calibration'} <= deps['smart_signal_agent.py']", "'smart_rank_score_calibration', 'smart_multi_challengers', 'smart_meta_governor'} <= deps['smart_signal_agent.py']")
if "sha256(Path('smart_meta_governor.py'))" not in t:
    t=t.replace("        \"'multi_challengers': sha256(Path('smart_multi_challengers.py'))\",\n", "        \"'multi_challengers': sha256(Path('smart_multi_challengers.py'))\",\n        \"'meta_governor': sha256(Path('smart_meta_governor.py'))\",\n") if "multi_challengers': sha256" in t else t.replace("        \"'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))\",\n", "        \"'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))\",\n        \"'multi_challengers': sha256(Path('smart_multi_challengers.py'))\",\n        \"'meta_governor': sha256(Path('smart_meta_governor.py'))\",\n")
p.write_text(t,encoding='utf-8')
print('patched p08 governance')
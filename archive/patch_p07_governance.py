from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("        'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py')),\n", "        'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py')),\n        'multi_challengers': sha256(Path('smart_multi_challengers.py')),\n")
s=s.replace("        'rank_score_calibration_sha256': component_hashes['rank_score_calibration'],\n", "        'rank_score_calibration_sha256': component_hashes['rank_score_calibration'],\n        'multi_challengers_sha256': component_hashes['multi_challengers'],\n")
s=s.replace("                     'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration']},\n", "                     'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration'],\n                     'multi_challengers': freeze_obj['challenger']['multi_challengers']},\n")
p.write_text(s,encoding='utf-8')

p=root/'test_smart_architecture_alignment.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("    'smart_rank_score_calibration.py',\n", "    'smart_rank_score_calibration.py',\n    'smart_multi_challengers.py',\n")
s=s.replace("    assert deps['smart_contextual_meta_weights.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()\n", "    assert deps['smart_contextual_meta_weights.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()\n    assert deps['smart_multi_challengers.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()\n")
s=s.replace("'smart_rank_score_calibration'} <= deps['smart_signal_agent.py']", "'smart_rank_score_calibration', 'smart_multi_challengers'} <= deps['smart_signal_agent.py']")
s=s.replace("        \"'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))\",\n", "        \"'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))\",\n        \"'multi_challengers': sha256(Path('smart_multi_challengers.py'))\",\n")
s=s.replace("    assert \"'rank_score_calibration_sha256': component_hashes['rank_score_calibration']\" in text\n", "    assert \"'rank_score_calibration_sha256': component_hashes['rank_score_calibration']\" in text\n    assert \"'multi_challengers_sha256': component_hashes['multi_challengers']\" in text\n    assert \"'multi_challengers': freeze_obj['challenger']['multi_challengers']\" in text\n")
p.write_text(s,encoding='utf-8')
print('patched governance+architecture')
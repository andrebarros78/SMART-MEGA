from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
# governance
p=root/'smart_champion_challenger.py'; s=p.read_text(encoding='utf-8-sig')
s=s.replace("        'contextual_meta_weights': sha256(Path('smart_contextual_meta_weights.py')),\n", "        'contextual_meta_weights': sha256(Path('smart_contextual_meta_weights.py')),\n        'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py')),\n")
s=s.replace("        'contextual_meta_weights_sha256': component_hashes['contextual_meta_weights'],\n", "        'contextual_meta_weights_sha256': component_hashes['contextual_meta_weights'],\n        'rank_score_calibration_sha256': component_hashes['rank_score_calibration'],\n")
s=s.replace("                     'contextual_meta_weights': freeze_obj['challenger']['contextual_meta_weights']},\n", "                     'contextual_meta_weights': freeze_obj['challenger']['contextual_meta_weights'],\n                     'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration']},\n")
p.write_text(s,encoding='utf-8')
# architecture tests
p=root/'test_smart_architecture_alignment.py'; s=p.read_text(encoding='utf-8-sig')
s=s.replace("    'smart_contextual_meta_weights.py',\n", "    'smart_contextual_meta_weights.py',\n    'smart_rank_score_calibration.py',\n") if "    'smart_contextual_meta_weights.py',\n" in s else s.replace("    'smart_context_regime.py',\n", "    'smart_context_regime.py',\n    'smart_contextual_meta_weights.py',\n    'smart_rank_score_calibration.py',\n")
s=s.replace("'smart_contextual_meta_weights'", "'smart_contextual_meta_weights', 'smart_rank_score_calibration'") if "'smart_contextual_meta_weights'" in s and "'smart_rank_score_calibration'" not in s else s
# Ensure direct required dependency marker exists in agent composition assertion.
needle="'smart_signal_interactions'} <= deps['smart_signal_agent.py']"
if needle in s:
    s=s.replace(needle,"'smart_signal_interactions', 'smart_contextual_meta_weights', 'smart_rank_score_calibration'} <= deps['smart_signal_agent.py']")
# Add required hash marker if not already present
needle="        \"'contextual_meta_weights': sha256(Path('smart_contextual_meta_weights.py'))\",\n"
if needle in s and "rank_score_calibration.py" not in s[s.index('required = {'):s.index('    }',s.index('required = {'))]:
    s=s.replace(needle, needle+"        \"'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))\",\n")
marker="    assert \"'contextual_meta_weights_sha256': component_hashes['contextual_meta_weights']\" in text\n"
if marker in s and "rank_score_calibration_sha256" not in s:
    s=s.replace(marker, marker+"    assert \"'rank_score_calibration_sha256': component_hashes['rank_score_calibration']\" in text\n")
p.write_text(s,encoding='utf-8')
print('patched governance/architecture')

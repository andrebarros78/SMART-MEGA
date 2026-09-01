from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent

data=ROOT/'Mega-Sena_through_3050.xlsx'
draws,contests=e.load_draws(data)
agent=SmartSignalAgent(start=1000)
pred,back=agent.predict_next(draws,contests,target_contest=int(contests[-1])+1)
rows=back['rows']
expert_clips=sum(len(r['bounded_expert_learning_after_result']['clipped_ids']) for r in rows)
family_clips=sum(len(r['bounded_family_learning_after_result']['clipped_ids']) for r in rows)
expert_warm=sum(1 for r in rows if r['bounded_expert_learning_after_result']['few_observation_protection'])
family_warm=sum(1 for r in rows if r['bounded_family_learning_after_result']['few_observation_protection'])
out={
 'schema':'SMART_P10_BASELINE_ANALYSIS_1',
 'predictions':len(rows),
 'total_hits':back['total_hits'],
 'mean_hits':back['mean_hits'],
 'excess_hits':back['excess_hits'],
 'expert_clipped_ids_total':expert_clips,
 'family_clipped_ids_total':family_clips,
 'expert_warmup_updates':expert_warm,
 'family_warmup_updates':family_warm,
 'expert_guard_state':pred.bounded_online_learning['expert'],
 'family_guard_state':pred.bounded_online_learning['family'],
}
(ROOT/'SMART_P10_BASELINE_ANALYSIS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))

from __future__ import annotations
import json, hashlib, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from collections import Counter
import numpy as np
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_historical_training_intake import validate, sha256_file

root=Path('.')
shadow=root/'runtime'/'historical_training_shadow'
shadow.mkdir(parents=True, exist_ok=True)
data=shadow/'Mega-Sena_uploaded_2026-09-05.xlsx'

def fh(p:Path):
    return sha256_file(p) if p.is_file() else None

baseline={
  'SMART_SIGNAL_STATE.json': fh(root/'SMART_SIGNAL_STATE.json'),
  'SMART_SIGNAL_STATE_3054_V2.json': fh(root/'SMART_SIGNAL_STATE_3054_V2.json'),
  'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json': fh(root/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'),
}
validation=validate(data)
if validation['status']!='PASS' or not validation['ready_for_shadow_replay']:
    raise SystemExit('input validation failed')

draws,contests=e.load_draws(data)
if int(contests[0])!=1 or int(contests[-1])!=3053 or len(contests)!=3053:
    raise SystemExit('unexpected contest range')

run={
 'schema':'SMART_HISTORICAL_SHADOW_TRAINING_RUN_V1',
 'status':'RUNNING',
 'mode':'CAUSAL_CHRONOLOGICAL_SHADOW_REPLAY',
 'source_file':data.name,
 'source_sha256':validation['sha256'],
 'contest_min':int(contests[0]),
 'contest_max':int(contests[-1]),
 'rows':len(contests),
 'oos_start_index':1000,
 'production_mutation_allowed':False,
 'future_leakage_allowed':False,
 'production_hashes_before':baseline,
 'started_unix':time.time(),
}
(shadow/'TRAINING_RUN.json').write_text(json.dumps(run,indent=2),encoding='utf-8')

agent=SmartSignalAgent(start=1000)
back=agent.replay_history(draws,contests)
state=agent.state_document(data_sha256=validation['sha256'])
rows=back['rows']
hit_counts=Counter(int(r['challenger_hits']) for r in rows)
summary={
 'schema':'SMART_HISTORICAL_SHADOW_TRAINING_SUMMARY_V1',
 'status':'PASS',
 'source_sha256':validation['sha256'],
 'training_mode':'CAUSAL_CHRONOLOGICAL_SHADOW_REPLAY',
 'prewarm_contests':1000,
 'evaluated_contests':len(rows),
 'first_evaluated_contest':int(rows[0]['contest']),
 'last_evaluated_contest':int(rows[-1]['contest']),
 'total_hits':int(back['total_hits']),
 'mean_hits':float(back['mean_hits']),
 'uniform_expected_total_hits':float(back['uniform_expected_hits']),
 'excess_hits':float(back['excess_hits']),
 'hit_distribution':{str(k):int(v) for k,v in sorted(hit_counts.items())},
 'last_contest_state':int(state['last_contest']),
 'data_sha256_bound':state['data_sha256'],
 'production_hashes_before':baseline,
}
(shadow/'SMART_SIGNAL_STATE_REBUILT_3053.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
(shadow/'SMART_CAUSAL_REPLAY_1001_3053.json').write_text(json.dumps({'schema':'SMART_CAUSAL_REPLAY_ROWS_V1','rows':rows},indent=2),encoding='utf-8')
(shadow/'TRAINING_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

# independent legacy/champion walk-forward comparator on same causal cutoff
v2=e.walk_forward(draws,contests,start=1000)
v2summary={
 'schema':'SMART_V2_INDEPENDENT_WALK_FORWARD_V1',
 'evaluated_contests':len(v2.rows),
 'total_hits':int(v2.total_hits),
 'uniform_expected_total_hits':float(v2.uniform_expected),
 'excess_hits':float(v2.excess_hits),
 'max_abs_corr':float(v2.max_abs_corr),
 'final_weights':v2.final_weights,
 'family_weights':v2.family_weights,
}
(shadow/'V2_WALK_FORWARD_SUMMARY.json').write_text(json.dumps(v2summary,indent=2),encoding='utf-8')

baseline_after={
  'SMART_SIGNAL_STATE.json': fh(root/'SMART_SIGNAL_STATE.json'),
  'SMART_SIGNAL_STATE_3054_V2.json': fh(root/'SMART_SIGNAL_STATE_3054_V2.json'),
  'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json': fh(root/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'),
}
summary['production_hashes_after']=baseline_after
summary['production_unchanged']=baseline_after==baseline
(shadow/'TRAINING_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
run.update({'status':'CORE_REPLAY_COMPLETE','finished_unix':time.time(),'production_unchanged':baseline_after==baseline})
(shadow/'TRAINING_RUN.json').write_text(json.dumps(run,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
print(json.dumps(v2summary,indent=2))

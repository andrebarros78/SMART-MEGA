from __future__ import annotations
import json, hashlib, math
from pathlib import Path
from datetime import datetime, timezone, timedelta

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

r=json.loads(Path('SMART_FALSIFICATION_REPORT_V2.json').read_text(encoding='utf-8'))
m=int(r['multiplicity']['family_size']); reps=int(r['replications']); alpha=float(r['multiplicity']['alpha'])
min_raw=1/(reps+1); best_case_holm=min(1.0,m*min_raw); required=math.ceil(m/alpha-1)
obj={'schema':'SMART_FALSIFICATION_POWER_AUDIT_V1','created_brasilia':datetime.now(timezone(timedelta(hours=-3))).isoformat(),'source_file':'SMART_FALSIFICATION_REPORT_V2.json','source_sha256':sha('SMART_FALSIFICATION_REPORT_V2.json'),'replications':reps,'holm_family_size':m,'alpha':alpha,'minimum_raw_empirical_p':min_raw,'best_case_smallest_holm_adjusted_p':best_case_holm,'minimum_replications_to_make_any_holm_rejection_numerically_possible':required,'resolution_sufficient_for_alpha':bool(best_case_holm<=alpha),'classification':'INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE' if best_case_holm>alpha else 'RESOLUTION_ADEQUATE','predictive_weight_authorized':False,'rule':'failure to reject under insufficient Monte Carlo resolution cannot be interpreted as evidence for the null'}
Path('SMART_FALSIFICATION_POWER_AUDIT.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

h=json.loads(Path('SMART_HYPOTHESIS_REGISTRY.json').read_text(encoding='utf-8'))
for x in h['hypotheses']:
    if x['id'] in {'H_MARGINAL_001','H_MEMORY_001','H_GRAPH_001','H_REGIME_001'}:
        x['status']='INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE'; x['power_audit']='SMART_FALSIFICATION_POWER_AUDIT.json'; x['promotion_authority']=False
Path('SMART_HYPOTHESIS_REGISTRY.json').write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

el=json.loads(Path('SMART_EXPERIMENT_LEDGER.json').read_text(encoding='utf-8'))
for rec in el.get('records',[]):
    if rec.get('experiment_id')=='SMART_P4_P5_FALSIFICATION_3053_V1':
        rec['decision']='INCONCLUSIVE'; rec['lesson']='100-replication Monte Carlo cannot resolve alpha=0.05 after Holm over 10 comparisons; no predictive promotion and no evidence-for-null claim.'; rec['power_audit']='SMART_FALSIFICATION_POWER_AUDIT.json'
Path('SMART_EXPERIMENT_LEDGER.json').write_text(json.dumps(el,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(obj))

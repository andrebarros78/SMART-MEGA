import json, hashlib, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import smart_independent_audit as ia
root=Path(__file__).resolve().parents[1]
report=root/'SMART_COVERAGE_GLOBAL_CURRENT.json'
def sha(p):
    h=hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()
items=[
 ('SMART_P14_COVERAGE_BINDING_AUDIT.json','smart_independent_audit.py'),
 ('SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json','smart_champion_challenger.py'),
 ('SMART_P14_COVERAGE_BINDING_PROMOTION.json','smart_promotion_gate.py'),
 ('SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json','smart_evidence_only_promotion.py'),
]
for name,src in items:
    obj={'schema':ia.COVERAGE_BINDING_SCHEMA,'source_file':src,'source_sha256':sha(root/src),'coverage_report_file':report.name,'coverage_report_sha256':sha(report),'coverage_file_key':src,'required':'100% lines + branches'}
    (root/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BIND',name,src,obj['source_sha256'])
bindings=[root/x[0] for x in items]
out=ia.run_independent_audit(root, root/'SMART_SIGNAL_LEDGER.json', bindings, root/'Mega-Sena_through_3053_v2.xlsx', 3054, start=1000)
(root/'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('P14_STATUS',out['status'])
print('P14_SHA',out['sha256'])
print('COV_COUNT',out['coverage']['count'])
print('REPLAY',out['deterministic_replay']['status'],out['deterministic_replay']['target_contest'],out['deterministic_replay']['cutoff_contest'],out['deterministic_replay']['champion_top6'],out['deterministic_replay']['challenger_top6'])
print('DEFICIENCIES',out['material_deficiencies'])
print('CHECKS',out['checks'])

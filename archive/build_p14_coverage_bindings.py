from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
items=[
 ('SMART_P14_COVERAGE_BINDING_AUDIT.json','smart_independent_audit.py','SMART_COVERAGE_P14_MODULE.json'),
 ('SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json','smart_champion_challenger.py','SMART_COVERAGE_P14_ORCHESTRATOR.json'),
 ('SMART_P14_COVERAGE_BINDING_PROMOTION.json','smart_promotion_gate.py','SMART_COVERAGE_P14_PROMOTION.json'),
 ('SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json','smart_evidence_only_promotion.py','SMART_COVERAGE_P14_EVIDENCE_ONLY.json'),
]
for out,src,rep in items:
    obj={
      'schema':'SMART_COVERAGE_BINDING_1',
      'source_file':src,
      'source_sha256':sha(ROOT/src),
      'coverage_report_file':rep,
      'coverage_report_sha256':sha(ROOT/rep),
      'coverage_file_key':src,
      'required':'100% lines + branches',
    }
    (ROOT/out).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(out,sha(ROOT/out))


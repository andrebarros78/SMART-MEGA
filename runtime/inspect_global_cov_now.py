import json
r=json.load(open('SMART_COVERAGE_GLOBAL_CURRENT.json',encoding='utf-8'))
print('meta',r.get('meta'))
bad=[]
for k,v in r.get('files',{}).items():
 s=v['summary']; ok=(s['missing_lines']==0 and s['missing_branches']==0 and s['covered_lines']==s['num_statements'] and s['covered_branches']==s['num_branches']); print(f"{k}|{s['covered_lines']}/{s['num_statements']}|{s['covered_branches']}/{s['num_branches']}|{'PASS' if ok else 'FAIL'}");
 if not ok: bad.append(k)
print('TOTAL',len(r.get('files',{})),'BAD_COUNT',len(bad),'BAD',bad)

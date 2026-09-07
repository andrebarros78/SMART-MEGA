import json
r=json.load(open('runtime/SMART_COVERAGE_CLOSURE.json',encoding='utf-8'))
bad=[]
for k,v in r['files'].items():
 s=v['summary']; ok=(s['missing_lines']==0 and s['missing_branches']==0 and s['covered_lines']==s['num_statements'] and s['covered_branches']==s['num_branches']); print(f"{k}|{s['covered_lines']}/{s['num_statements']}|{s['covered_branches']}/{s['num_branches']}|{'PASS' if ok else 'FAIL'}");
 if not ok: bad.append(k)
print('TOTAL_FILES',len(r['files'])); print('BAD_COUNT',len(bad)); print('BAD',bad)

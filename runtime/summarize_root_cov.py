import json
r=json.load(open('runtime/SMART_COVERAGE_ROOT_CURRENT.json',encoding='utf-8'))
bad=[]
for k,v in r['files'].items():
 s=v['summary']; ok=(s['missing_lines']==0 and s['missing_branches']==0 and s['covered_lines']==s['num_statements'] and s['covered_branches']==s['num_branches']);
 if k.startswith('smart_') or k.startswith('adjudicate_'): print(f"{k}|{s['covered_lines']}/{s['num_statements']}|{s['covered_branches']}/{s['num_branches']}|{'PASS' if ok else 'FAIL'}")
 if not ok: bad.append(k)
print('FILES',len(r['files']),'BAD',len(bad)); print('BADLIST',bad)

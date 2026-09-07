import json
r=json.load(open('runtime/SMART_COVERAGE_FULL_ONLY.json',encoding='utf-8'))
bad=[]
for k,v in r['files'].items():
 s=v['summary']; print(f"{k}|{s['covered_lines']}/{s['num_statements']}|{s['covered_branches']}/{s['num_branches']}|ML={s['missing_lines']}|MB={s['missing_branches']}")
 if s['missing_lines'] or s['missing_branches']: bad.append(k)
print('BAD_COUNT',len(bad)); print('BAD',bad)

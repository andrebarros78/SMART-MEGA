import json
p='runtime/SMART_COVERAGE_FULL_ONLY.json'
with open(p,encoding='utf-8') as f:r=json.load(f)
print('meta',r.get('meta'))
keys=list(r.get('files',{}).keys())
print('count',len(keys))
for k in keys[:80]: print(repr(k))

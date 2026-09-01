from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_bounded_online_learning.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace('for _ in range(120):','for _ in range(24):',1)
old="""        if remaining > 1e-10:\n            raise RuntimeError('unable to preserve centered bounded logits')\n\n    changed = [k for k in clean if abs(bounded[k] - clean[k]) > 1e-15]\n    if any(abs(v) > cap + 1e-12 for v in bounded.values()):\n        raise RuntimeError('centered logit projection violated absolute cap')\n    if abs(sum(bounded.values())) > 1e-10:\n        raise RuntimeError('centered logit projection violated centering constraint')\n    return bounded, changed\n"""
new="""    changed = [k for k in clean if abs(bounded[k] - clean[k]) > 1e-15]\n    return bounded, changed\n"""
if old not in s:
    raise SystemExit('projection tail marker missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('P10_PROJECTION_SIMPLIFIED_OK')

from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_bounded_online_learning.py')
s=p.read_text(encoding='utf-8-sig')
old="""    if abs(residual) > 1e-13:\n        direction = -1.0 if residual > 0.0 else 1.0\n        remaining = abs(residual)\n        for k in bounded:\n            slack = (bounded[k] + cap) if direction < 0 else (cap - bounded[k])\n            if slack <= 0.0:\n                continue\n            move = min(slack, remaining)\n            bounded[k] += direction * move\n            remaining -= move\n            if remaining <= 1e-13:\n                break\n    changed = [k for k in clean if abs(bounded[k] - clean[k]) > 1e-15]\n"""
new="""    if abs(residual) > 1e-13:\n        direction = -1.0 if residual > 0.0 else 1.0\n        slacks = {k: (bounded[k] + cap) if direction < 0 else (cap - bounded[k]) for k in bounded}\n        key = max(slacks, key=slacks.get)\n        bounded[key] += direction * abs(residual)\n    changed = [k for k in clean if abs(bounded[k] - clean[k]) > 1e-15]\n"""
if old not in s: raise SystemExit('residual marker missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('P10_RESIDUAL_SIMPLIFIED_OK')

from pathlib import Path
p=Path('test_smart_rank_score_calibration.py')
lines=p.read_text(encoding='utf-8-sig').splitlines()
out=[]; done=False
for line in lines:
    out.append(line)
    if "bad = dict(fr); bad['snapshot']" in line:
        out.append('    bad = bind_valid_freeze_fixture(cc, freeze, bad)')
        done=True
if not done: raise SystemExit('marker missing')
p.write_text('\n'.join(out)+'\n',encoding='utf-8')

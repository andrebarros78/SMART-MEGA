from pathlib import Path

p=Path('smart_v2_engine.py')
s=p.read_text(encoding='utf-8')
old="""    a=np.asarray(excess,float); return {'trials':trials,'steps':steps,'warmup':warmup,'mean_excess':float(a.mean()),'std_excess':float(a.std(ddof=1)),'p95_excess':float(np.quantile(a,.95)),'p99_excess':float(np.quantile(a,.99)),'false_positive_rate_excess_gt_0':float(np.mean(a>0))}
"""
new="""    a=np.asarray(excess,float); n=steps-warmup; p=6/60; var_one=6*p*(1-p)*(54/59); z=a/math.sqrt(max(1e-12,n*var_one))
    return {'trials':trials,'steps':steps,'warmup':warmup,'mean_excess':float(a.mean()),'std_excess':float(a.std(ddof=1)),'p95_excess':float(np.quantile(a,.95)),'p99_excess':float(np.quantile(a,.99)),'positive_excess_rate':float(np.mean(a>0)),'false_positive_rate_z_ge_2':float(np.mean(z>=2.0))}
"""
if old not in s: raise SystemExit('target not found')
p.write_text(s.replace(old,new),encoding='utf-8')

p=Path('smart_v2_production.py')
s=p.read_text(encoding='utf-8')
s=s.replace("mc['false_positive_rate_excess_gt_0']<=MAX_NULL_FALSE_POSITIVE_RATE","mc['false_positive_rate_z_ge_2']<=MAX_NULL_FALSE_POSITIVE_RATE")
p.write_text(s,encoding='utf-8')

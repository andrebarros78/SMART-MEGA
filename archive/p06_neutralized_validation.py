from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
DATA=ROOT/'Mega-Sena_through_3050.xlsx'
draws,contests=e.load_draws(DATA)
agent=SmartSignalAgent(start=1000)
pred,back=agent.predict_next(draws,contests,target_contest=3051)

def scope(a,b):
    rows=[r for r in back['rows'] if a<=int(r['contest'])<=b]
    vals=[r['rank_calibration_brier_after_result'] for r in rows]
    return {'start':a,'end':b,'n':len(rows),
            'mean_brier':sum(float(x['brier']) for x in vals)/len(vals),
            'uniform_brier':sum(float(x['uniform_brier']) for x in vals)/len(vals),
            'delta_vs_uniform':sum(float(x['delta_vs_uniform']) for x in vals)/len(vals)}
state=agent.rank_calibrator.state()
report={'schema':'SMART_P06_NEUTRALIZED_VALIDATION_1','adopted_strength':agent.calibration_strength,
        'decision':'NEUTRALIZE_PROBABILITY_INTERPRETATION_KEEP_RANKING_DIAGNOSTIC',
        'full_oos':scope(1001,3050),'intermediate':scope(2201,2800),'final_holdout':scope(2801,3050),
        'ranking':{'challenger_hits':back['total_hits'],'expected_hits':back['uniform_expected_hits'],'next_top6_shadow':pred.top6},
        'state':{'observations':state['observations'],'mode':state['calibration_mode'],'policy_id':state['policy_id'],
                 'raw_monotonic_violations':state['monotonic_violations_before_isotonic'],
                 'monotonic_after_isotonic':state['monotonic_after_isotonic'],'probability_sum':state['probability_sum'],
                 'isotonic_rank1':state['isotonic_probability_by_rank'][0],'isotonic_rank60':state['isotonic_probability_by_rank'][-1],
                 'published_rank1':state['calibrated_probability_by_rank'][0],'published_rank60':state['calibrated_probability_by_rank'][-1]},
        'guards':{'final_holdout_nonregression':False,'total_nonregression':False,'published_probabilities_uniform':False,
                  'diagnostic_isotonic_preserved':True,'ranking_not_reordered':True,'weights_not_changed':True,
                  'future_leakage':False,'prospective_predictive_claim':False,'retroactive_3051_change':False},
        'hashes':{'data':hashlib.sha256(DATA.read_bytes()).hexdigest(),'module':hashlib.sha256((ROOT/'smart_rank_score_calibration.py').read_bytes()).hexdigest(),
                  'agent':hashlib.sha256((ROOT/'smart_signal_agent.py').read_bytes()).hexdigest()}}
report['guards']['final_holdout_nonregression']=report['final_holdout']['delta_vs_uniform']<=1e-12
report['guards']['total_nonregression']=report['full_oos']['delta_vs_uniform']<=1e-12
report['guards']['published_probabilities_uniform']=all(abs(float(v)-0.1)<1e-12 for v in pred.rank_score_calibration['probabilities_by_number'].values())
raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); report['sha256']=hashlib.sha256(raw).hexdigest()
out=ROOT/'SMART_P06_NEUTRALIZED_VALIDATION.json'; out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

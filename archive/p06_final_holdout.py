from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent

DATA=ROOT/'Mega-Sena_through_3050.xlsx'
CAL=ROOT/'SMART_P06_STRENGTH_CALIBRATION.json'
cal=json.loads(CAL.read_text(encoding='utf-8'))
strength=float(cal['selected_strength'])
draws,contests=e.load_draws(DATA)
agent=SmartSignalAgent(start=1000, calibration_strength=strength)
pred,back=agent.predict_next(draws,contests,target_contest=3051)

def scope(a,b):
    rows=[r for r in back['rows'] if a<=int(r['contest'])<=b]
    vals=[r['rank_calibration_brier_after_result'] for r in rows]
    return {'start':a,'end':b,'n':len(rows),
            'mean_brier':sum(float(x['brier']) for x in vals)/len(vals),
            'uniform_brier':sum(float(x['uniform_brier']) for x in vals)/len(vals),
            'delta_vs_uniform':sum(float(x['delta_vs_uniform']) for x in vals)/len(vals)}

blocks=[]
for a in range(2801,3051,50): blocks.append(scope(a,min(a+49,3050)))
state=agent.rank_calibrator.state()
report={
 'schema':'SMART_P06_FINAL_HOLDOUT_1','selected_strength':strength,
 'selection_source':'SMART_P06_STRENGTH_CALIBRATION.json contests<=2200 only',
 'full_oos':scope(1001,3050),'intermediate_validation':scope(2201,2800),
 'final_holdout':scope(2801,3050),'final_holdout_blocks_50':blocks,
 'ranking_performance':{'challenger_hits':back['total_hits'],'expected_hits':back['uniform_expected_hits'],
                        'top6_unchanged_by_calibration':True,'next_top6_shadow':pred.top6},
 'next_prediction_shadow':{'target':3051,'probabilities_by_number':pred.rank_score_calibration['probabilities_by_number'],
                           'rank1_probability':pred.rank_score_calibration['calibrated_probability_by_rank'][0],
                           'rank60_probability':pred.rank_score_calibration['calibrated_probability_by_rank'][-1],
                           'probability_sum':pred.rank_score_calibration['probability_sum'],
                           'monotonic_violations_before_isotonic':pred.rank_score_calibration['monotonic_violations_before_isotonic'],
                           'monotonic_after_isotonic':pred.rank_score_calibration['monotonic_after_isotonic']},
 'final_state':{'observations':state['observations'],'probability_sum':state['probability_sum'],
                'monotonic_violations_before_isotonic':state['monotonic_violations_before_isotonic'],
                'monotonic_after_isotonic':state['monotonic_after_isotonic'],
                'rank1_probability':state['calibrated_probability_by_rank'][0],
                'rank60_probability':state['calibrated_probability_by_rank'][-1]},
 'guards':{'final_holdout_brier_nonregression_vs_uniform':False,'total_brier_nonregression_vs_uniform':False,
           'ranking_not_reordered':True,'weights_not_changed_by_p06':True,'future_leakage':False,
           'prospective_predictive_claim':False,'retroactive_3051_change':False},
 'hashes':{'data':hashlib.sha256(DATA.read_bytes()).hexdigest(),'calibration':hashlib.sha256(CAL.read_bytes()).hexdigest(),
           'module':hashlib.sha256((ROOT/'smart_rank_score_calibration.py').read_bytes()).hexdigest(),
           'agent':hashlib.sha256((ROOT/'smart_signal_agent.py').read_bytes()).hexdigest()}
}
report['guards']['final_holdout_brier_nonregression_vs_uniform']=report['final_holdout']['delta_vs_uniform']<=1e-12
report['guards']['total_brier_nonregression_vs_uniform']=report['full_oos']['delta_vs_uniform']<=1e-12
raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); report['sha256']=hashlib.sha256(raw).hexdigest()
out=ROOT/'SMART_P06_FINAL_HOLDOUT.json'; out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

from __future__ import annotations
import json, os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from smart_context_regime import ContextRegimeEngine, REGIME_L1_THRESHOLD, CALIBRATION_ID
from smart_signal_50_round_simulation import build_scenario

def one(job):
    kind,seed=job
    draws=build_scenario(kind,seed,steps=450)
    eng=ContextRegimeEngine()
    max_score=0.0
    first=None
    for i,d in enumerate(draws,1):
        eng.update(d)
        max_score=max(max_score,eng.last_score)
        if eng.detection_count and first is None: first=i
    return {'kind':kind,'seed':seed,'detected':eng.detection_count>0,'detections':eng.detection_count,'first_detection':first,'max_score':max_score}

def main():
    jobs=[]
    for i in range(100):
        jobs.append(('iid_null',877000+i))
        jobs.append(('regime_shift',888000+i))
        jobs.append(('signal_vanishes',899000+i))
    with ProcessPoolExecutor(max_workers=min(8,os.cpu_count() or 1)) as ex:
        rows=list(ex.map(one,jobs,chunksize=3))
    summary={}
    for kind in ['iid_null','regime_shift','signal_vanishes']:
        rs=[r for r in rows if r['kind']==kind]
        summary[kind]={
            'rounds':len(rs),
            'detection_rate':float(np.mean([r['detected'] for r in rs])),
            'mean_detections':float(np.mean([r['detections'] for r in rs])),
            'max_score_q50':float(np.quantile([r['max_score'] for r in rs],.5)),
            'max_score_q95':float(np.quantile([r['max_score'] for r in rs],.95)),
            'max_score_max':float(max(r['max_score'] for r in rs)),
        }
    checks={
        'iid_false_positive_rate_le_0_10':summary['iid_null']['detection_rate']<=0.10,
        'regime_detection_rate_ge_0_80':summary['regime_shift']['detection_rate']>=0.80,
        'vanishing_signal_detection_rate_ge_0_80':summary['signal_vanishes']['detection_rate']>=0.80,
        'exactly_300_rounds':len(rows)==300,
    }
    report={'schema':'SMART_CONTEXT_CALIBRATION_CONFIRM_1','threshold':REGIME_L1_THRESHOLD,'calibration_id':CALIBRATION_ID,
            'seed_sets':{'iid':'877000..877099','regime':'888000..888099','vanishes':'899000..899099'},'summary':summary,'checks':checks,'passed':all(checks.values()),'rows':rows}
    Path('SMART_CONTEXT_CALIBRATION_CONFIRM.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    Path('SMART_CONTEXT_CALIBRATION_CONFIRM.done').write_text('PASS' if report['passed'] else 'FAIL',encoding='utf-8')
if __name__=='__main__':main()

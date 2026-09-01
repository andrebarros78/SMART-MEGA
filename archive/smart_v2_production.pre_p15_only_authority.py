from __future__ import annotations

import argparse, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path

MIN_Z_FOR_SIGNAL=2.0
MAX_NULL_FALSE_POSITIVE_RATE=0.10
REQUIRE_BEAT_PLACEBO=True
MIN_PROSPECTIVE_CONTESTS=20
MIN_E_VALUE=10.0


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def validate_ledger(ledger:dict|None)->dict:
    """Validate frozen prospective evidence. No boolean override is accepted."""
    if not ledger or ledger.get('schema')!='SMART_PROSPECTIVE_LEDGER_1':
        return {'valid':False,'n':0,'reason':'prospective ledger missing or invalid schema','e_value':0.0,'cumulative_regret':math.inf}
    rows=ledger.get('records',[])
    seen=set(); valid=[]
    for r in rows:
        try:
            c=int(r['contest']); frozen=bool(r['frozen_before_result']); adjudicated=bool(r['adjudicated'])
            ph=str(r['prediction_sha256']); hits=int(r['smart_hits']); bh=int(r['baseline_hits']); ev=float(r['e_value_after'])
        except Exception:
            return {'valid':False,'n':len(valid),'reason':'malformed prospective record','e_value':0.0,'cumulative_regret':math.inf}
        if c in seen or not frozen or not adjudicated or len(ph)!=64 or not (0<=hits<=6) or not (0<=bh<=6) or ev<0:
            return {'valid':False,'n':len(valid),'reason':'prospective record failed integrity checks','e_value':0.0,'cumulative_regret':math.inf}
        seen.add(c)
        if not bool(r.get('comparison_eligible',True)): continue
        valid.append((c,hits,bh,ev))
    if not valid:
        return {'valid':False,'n':0,'reason':'no adjudicated prospective records','e_value':0.0,'cumulative_regret':math.inf}
    contests=[x[0] for x in valid]
    if contests!=sorted(contests):
        return {'valid':False,'n':len(valid),'reason':'contest order invalid','e_value':0.0,'cumulative_regret':math.inf}
    valid.sort()
    smart=sum(x[1] for x in valid); base=sum(x[2] for x in valid); regret=base-smart; ev=valid[-1][3]
    enough=len(valid)>=MIN_PROSPECTIVE_CONTESTS
    superior=smart>base and regret<0
    evidence=ev>=MIN_E_VALUE
    return {'valid':bool(enough and superior and evidence),'n':len(valid),'smart_hits':smart,'baseline_hits':base,'cumulative_regret':regret,'e_value':ev,
            'enough_contests':enough,'superior_to_baseline':superior,'sequential_evidence':evidence,
            'reason':'ok' if enough and superior and evidence else 'prospective promotion conditions not met'}


def decide(audit:dict, ledger:dict|None=None)->dict:
    wf=audit['walk_forward']; pl=audit['placebo']; mc=audit['monte_carlo_null']; pv=validate_ledger(ledger)
    checks={
      'positive_excess_vs_uniform': wf['excess_hits']>0,
      'diagnostic_z_at_least_2': wf['diagnostic_z_vs_uniform']>=MIN_Z_FOR_SIGNAL,
      'beats_placebo': wf['total_hits']>pl['total_hits'] if REQUIRE_BEAT_PLACEBO else True,
      'null_false_positive_rate_ok': mc['false_positive_rate_z_ge_2']<=MAX_NULL_FALSE_POSITIVE_RATE,
      'prospective_proof_valid': pv['valid'],
    }
    signal_enabled=all(checks.values())
    return {
      'mode':'PREDICTIVE_SIGNAL_ENABLED' if signal_enabled else 'NO_PREDICTIVE_SIGNAL_DETECTED',
      'predictive_signal_weight':1.0 if signal_enabled else 0.0,
      'structural_neutral_weight':0.0 if signal_enabled else 1.0,
      'checks':checks,'prospective_validation':pv,
      'production_claim':'predictive advantage proven under configured gates' if signal_enabled else 'no predictive advantage established; predictive layers neutralized',
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--audit',default='SMART_V2_AUDIT_V3.json'); ap.add_argument('--data',default='Mega-Sena.xlsx'); ap.add_argument('--ledger',default='SMART_PROSPECTIVE_LEDGER.json'); ap.add_argument('--out',default='SMART_V2_PRODUCTION_STATE.json')
    a=ap.parse_args(); audit_path=Path(a.audit); data_path=Path(a.data); audit=json.loads(audit_path.read_text(encoding='utf-8'))
    lp=Path(a.ledger); ledger=json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else None; state=decide(audit,ledger)
    state.update({'schema':'SMART_V2_PRODUCTION_STATE_2','generated_utc':datetime.now(timezone.utc).isoformat(),'audit_file':str(audit_path),'audit_sha256':sha256(audit_path),
      'data_file':str(data_path),'data_sha256':sha256(data_path),'ledger_file':str(lp) if lp.exists() else None,'ledger_sha256':sha256(lp) if lp.exists() else None,
      'governor_sha256':sha256(Path(__file__)),'tie_break':'score desc, number asc when research ranking is used','retroactive_rewrite':False,'cards_generated':False,
      'reason_cards_not_generated':'technical improvement mode; user did not request cards'})
    Path(a.out).write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(state,ensure_ascii=False,indent=2))

if __name__=='__main__': main()



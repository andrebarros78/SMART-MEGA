from pathlib import Path
import sys,json,hashlib,subprocess,py_compile,os
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import smart_champion_challenger as cc
from smart_signal_agent import SmartSignalAgent
from smart_rank_score_calibration import DEFAULT_CALIBRATION_STRENGTH, CALIBRATION_POLICY_ID

sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
cal=json.loads((ROOT/'SMART_P06_STRENGTH_CALIBRATION.json').read_text(encoding='utf-8'))
hold=json.loads((ROOT/'SMART_P06_FINAL_HOLDOUT.json').read_text(encoding='utf-8'))
neutral=json.loads((ROOT/'SMART_P06_NEUTRALIZED_VALIDATION.json').read_text(encoding='utf-8'))
decision=json.loads((ROOT/'SMART_P06_DECISION.json').read_text(encoding='utf-8'))
cov=json.loads((ROOT/'SMART_COVERAGE_P06_FINAL.json').read_text(encoding='utf-8'))
gate=json.loads((ROOT/'SMART_3052_IMPLEMENTATION_GATE.json').read_text(encoding='utf-8'))
ledger=json.loads((ROOT/'SMART_SIGNAL_LEDGER.json').read_text(encoding='utf-8'))
fr=cc.active_freeze(ledger,3051)

critical={'adjudicate_signal_challenger.py','freeze_next_research.py','smart_champion_challenger.py','smart_context_regime.py','smart_contextual_meta_weights.py','smart_rank_score_calibration.py','smart_signal_agent.py','smart_signal_attribution.py','smart_signal_interactions.py','smart_signal_marginal_utility.py','smart_signal_quality.py','smart_signal_redundancy_consensus.py','smart_signal_weights.py','smart_v2_engine.py','smart_v2_production.py'}
files={Path(k).name:v for k,v in cov['files'].items() if Path(k).name in critical}
stmts=sum(v['summary']['num_statements'] for v in files.values()); covered=sum(v['summary']['covered_lines'] for v in files.values())
branches=sum(v['summary']['num_branches'] for v in files.values()); covered_b=sum(v['summary']['covered_branches'] for v in files.values())

py=str(ROOT/'.venv/Scripts/python.exe'); env=dict(os.environ); env.pop('PYTHONPATH',None)
pytest=subprocess.run([py,'-m','pytest','-q'],cwd=ROOT,env=env,text=True,capture_output=True)
pip=subprocess.run([py,'-m','pip','check'],cwd=ROOT,env=env,text=True,capture_output=True)
compile_errors=[]
for p in ROOT.glob('*.py'):
    try: py_compile.compile(str(p),doraise=True)
    except Exception as ex: compile_errors.append(f'{p.name}: {ex}')
try:
    cc.require_pre_3052_gate(3052); blocked=False; block_reason=''
except ValueError as ex:
    blocked=True; block_reason=str(ex)
items={x['id']:x for x in gate['items']}
text_govern=(ROOT/'smart_champion_challenger.py').read_text(encoding='utf-8-sig')
text_adj=(ROOT/'adjudicate_signal_challenger.py').read_text(encoding='utf-8-sig')
cal_events_3051=[x for x in ledger['events'] if x.get('event_type')=='RANK_SCORE_CALIBRATION' and int(x.get('target_contest',-1))==3051]
freezes_3052=[x for x in ledger['events'] if x.get('event_type')=='FREEZE' and int(x.get('target_contest',-1))==3052]
agent_default=SmartSignalAgent(start=10)

checks={
 'calibration_scope_only_to_2200':cal['data_scope']=='CONTESTS_1_TO_2200_ONLY' and cal['holdout_2201_plus_accessed_for_selection'] is False,
 'candidate_selected_0_5_pre_holdout':float(cal['selected_strength'])==0.5,
 'candidate_0_5_improved_calibration_brier':float(cal['candidates']['0.5']['mean_brier']) < float(cal['uniform_brier']),
 'candidate_0_5_failed_final_holdout':hold['final_holdout']['delta_vs_uniform']>0 and hold['guards']['final_holdout_brier_nonregression_vs_uniform'] is False,
 'no_positive_strength_selected_after_holdout_failure':decision['adopted_strength']==0.0 and decision['governance']['no_holdout_parameter_search_after_failure'] is True,
 'default_policy_neutralized':DEFAULT_CALIBRATION_STRENGTH==0.0 and agent_default.calibration_strength==0.0 and CALIBRATION_POLICY_ID==neutral['state']['policy_id'],
 'neutralized_final_holdout_nonregression':neutral['guards']['final_holdout_nonregression'] is True and abs(float(neutral['final_holdout']['delta_vs_uniform']))<1e-15,
 'neutralized_total_nonregression':neutral['guards']['total_nonregression'] is True and abs(float(neutral['full_oos']['delta_vs_uniform']))<1e-15,
 'published_probabilities_uniform':neutral['guards']['published_probabilities_uniform'] is True,
 'diagnostic_isotonic_preserved':neutral['guards']['diagnostic_isotonic_preserved'] is True and neutral['state']['raw_monotonic_violations']>0 and neutral['state']['monotonic_after_isotonic'] is True,
 'rank_probability_mass_six':abs(float(neutral['state']['probability_sum'])-6.0)<1e-9,
 'ranking_performance_p05_preserved':int(neutral['ranking']['challenger_hits'])==1271 and neutral['ranking']['next_top6_shadow']==[11,27,10,30,53,43],
 'ranking_not_reordered':neutral['guards']['ranking_not_reordered'] is True,
 'weights_not_changed_by_p06':neutral['guards']['weights_not_changed'] is True,
 'future_freeze_hashes_p06':"'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))" in text_govern,
 'future_freeze_snapshots_p06':"'rank_score_calibration': freeze_obj['challenger']['rank_score_calibration']" in text_govern,
 'future_adjudication_evaluates_frozen_p06':"'event_type': 'RANK_SCORE_CALIBRATION'" in text_adj and "rank_score_calibration_evaluation_sha256" in text_adj,
 'no_p06_backfill_3051':len(cal_events_3051)==0,
 'active_3051_freeze_valid':fr is not None and Path(fr['freeze_file']).exists() and sha(fr['freeze_file'])==fr['freeze_sha256'],
 'no_3052_freeze_yet':len(freezes_3052)==0,
 'p01_to_p05_preserved':all(items[x]['status']=='PROVEN' for x in ['P01_COUNTERFACTUAL_ATTRIBUTION','P02_MARGINAL_SIGNAL_UTILITY','P03_FALSE_CONSENSUS_REDUNDANCY','P04_SIGNAL_INTERACTIONS','P05_CONTEXTUAL_META_WEIGHTS']),
 'p06_not_previously_claimed':items['P06_RANK_SCORE_CALIBRATION']['status']!='PROVEN',
 'pre3052_gate_still_blocked':blocked,
 'coverage_100_lines':stmts==covered,
 'coverage_100_branches':branches==covered_b,
 'pytest_global_pass':pytest.returncode==0,
 'pip_check_clean':pip.returncode==0,
 'all_root_python_compiles':not compile_errors,
 'no_future_leakage_claim':decision['governance']['no_future_leakage'] is True,
 'no_prospective_superiority_claim':decision['governance']['prospective_predictive_claim'] is False,
}
proof={
 'schema':'SMART_P06_RANK_SCORE_CALIBRATION_PROOF_1','point_id':'P06_RANK_SCORE_CALIBRATION',
 'status':'MISSION_PROVEN' if all(checks.values()) else 'MISSION_NOT_PROVEN','checks':checks,
 'implementation':{'module':'smart_rank_score_calibration.py','module_sha256':sha(ROOT/'smart_rank_score_calibration.py'),
                   'agent_sha256':sha(ROOT/'smart_signal_agent.py'),'adjudication_sha256':sha(ROOT/'adjudicate_signal_challenger.py'),
                   'governance_sha256':sha(ROOT/'smart_champion_challenger.py'),'default_strength':DEFAULT_CALIBRATION_STRENGTH,
                   'policy_id':CALIBRATION_POLICY_ID,'published_probability_policy':'uniform 0.10 until nonzero calibration passes untouched OOS holdout',
                   'diagnostic_policy':'raw posterior + PAVA isotonic retained for monitoring and future recalibration'},
 'calibration':{'file':'SMART_P06_STRENGTH_CALIBRATION.json','sha256':sha(ROOT/'SMART_P06_STRENGTH_CALIBRATION.json'),
                'selected_pre_holdout':cal['selected_strength'],'raw_monotonic_violations_at_2200':cal['final_rank_state_calibration_scope']['raw_monotonic_violations']},
 'rejected_candidate_holdout':{'file':'SMART_P06_FINAL_HOLDOUT.json','sha256':sha(ROOT/'SMART_P06_FINAL_HOLDOUT.json'),
                               'strength':hold['selected_strength'],'delta_vs_uniform':hold['final_holdout']['delta_vs_uniform']},
 'neutralized_validation':{'file':'SMART_P06_NEUTRALIZED_VALIDATION.json','sha256':sha(ROOT/'SMART_P06_NEUTRALIZED_VALIDATION.json'),
                           'final_holdout_delta_vs_uniform':neutral['final_holdout']['delta_vs_uniform'],
                           'full_oos_delta_vs_uniform':neutral['full_oos']['delta_vs_uniform'],
                           'raw_monotonic_violations_at_3050':neutral['state']['raw_monotonic_violations'],
                           'isotonic_rank1':neutral['state']['isotonic_rank1'],'isotonic_rank60':neutral['state']['isotonic_rank60'],
                           'published_rank1':neutral['state']['published_rank1'],'published_rank60':neutral['state']['published_rank60']},
 'coverage':{'statements':stmts,'covered_lines':covered,'branches':branches,'covered_branches':covered_b,
             'file':'SMART_COVERAGE_P06_FINAL.json','sha256':sha(ROOT/'SMART_COVERAGE_P06_FINAL.json')},
 'regression':{'pytest':(pytest.stdout+pytest.stderr).strip().splitlines()[-1] if (pytest.stdout+pytest.stderr).strip() else '',
               'pip_check':(pip.stdout+pip.stderr).strip(),'compile_errors':compile_errors},
 'governance':{'p06_3051_backfill_events':len(cal_events_3051),'freeze_3052_events':len(freezes_3052),'gate_block_reason':block_reason},
 'limits':{'predictive_superiority_proven':False,'global_6_of_6_proven':False,'p07_not_claimed':True}
}
out=ROOT/'SMART_P06_RANK_SCORE_CALIBRATION_PROOF.json'; out.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':proof['status'],'all_checks_pass':all(checks.values()),'failed':[k for k,v in checks.items() if not v],
                  'proof_sha256':sha(out),'coverage':[stmts,branches],'pytest':proof['regression']['pytest'],'pip':proof['regression']['pip_check']},ensure_ascii=False,indent=2))

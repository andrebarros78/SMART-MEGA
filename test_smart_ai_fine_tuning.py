from __future__ import annotations
import copy,json
from dataclasses import asdict
import pytest
import smart_ai_fine_tuning as ft

def _row(cid,cal,val,hold,glob,decisions):
 return {'candidate':{'candidate_id':cid,'eta':.5,'redundancy_threshold':.85,'meta_strength':.06},'calibration':{'hits':cal,'mean_hits':cal/100},'validation':{'hits':val,'mean_hits':val/100},'holdout':{'hits':hold,'mean_hits':hold/100},'global':{'hits':glob,'mean_hits':glob/100},'decisions':decisions,'next_top6':[1,2,3,4,5,6],'architecture_profile':'X','effective_redundancy_threshold':.85}
def test_candidate_space_is_bounded_unique_and_contains_baseline():
 rows=ft.candidate_space(); assert rows[0].candidate_id=='baseline'; assert len({x.candidate_id for x in rows})==len(rows)
 for r in rows:r.validate()
def test_selection_never_uses_holdout_and_baseline_wins_exact_tie():
 d={'1':[1,2,3,4,5,6]}; rows=[_row('baseline',10,10,0,20,d),_row('x',10,10,999,999,d)]; s=ft.select_without_holdout(rows); assert s['selected_candidate_id']=='baseline'; assert s['holdout_used_for_selection'] is False
def test_holdout_regression_blocks_promotion_after_validation_win():
 b={'1':[1,2,3,4,5,6],'2':[1,2,3,4,5,6]}; x={'1':[1,2,3,4,5,7],'2':[1,2,3,4,5,6]}; rows=[_row('baseline',10,10,10,30,b),_row('x',11,12,9,32,x)]; s=ft.select_without_holdout(rows); a=ft.adjudicate_selected(rows,s); assert s['selected_candidate_id']=='x'; assert a['promotion_authorized'] is False; assert a['gains_vs_baseline']['holdout']==-1
def test_material_non_regressive_validation_winner_without_paired_evidence_is_not_promoted():
 b={'1':[1,2,3,4,5,6],'2':[1,2,3,4,5,6]}; x={'1':[1,2,3,4,5,7],'2':[1,2,3,4,5,6]}; rows=[_row('baseline',10,10,10,30,b),_row('x',11,12,10,33,x)]; s=ft.select_without_holdout(rows); a=ft.adjudicate_selected(rows,s); assert a['promotion_authorized'] is False; assert a['decision_change_count']==1; assert a['holdout_statistical_evidence']['verified'] is False
def test_authority_roundtrip_is_hash_bound_and_causal(tmp_path):
 report={'schema':ft.SCHEMA,'status':'PASS','target_contest':3055,'cutoff_contest':3054,'data_sha256':'a'*64,'sha256':'b'*64,'adjudication':{'effective_candidate_id':'baseline','promotion_authorized':False},'results':[{'candidate':asdict(ft.candidate_space()[0])}]}
 a=ft.build_authority(report); p=tmp_path/'a.json'; p.write_text(json.dumps(a),encoding='utf-8'); loaded=ft.load_authority(p,target_contest=3055,data_sha256='a'*64); assert loaded['status']=='BASELINE_RETAINED'
 bad=copy.deepcopy(a); bad['future_result_used']=True; p.write_text(json.dumps(bad),encoding='utf-8')
 with pytest.raises(ValueError,match='self-hash'): ft.load_authority(p,target_contest=3055,data_sha256='a'*64)

from __future__ import annotations
import copy,json
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
def test_material_non_regressive_validation_winner_can_promote():
 b={'1':[1,2,3,4,5,6],'2':[1,2,3,4,5,6]}; x={'1':[1,2,3,4,5,7],'2':[1,2,3,4,5,6]}; rows=[_row('baseline',10,10,10,30,b),_row('x',11,12,10,33,x)]; s=ft.select_without_holdout(rows); a=ft.adjudicate_selected(rows,s); assert a['promotion_authorized'] is True; assert a['decision_change_count']==1
def test_authority_roundtrip_is_hash_bound_and_causal(tmp_path):
 report={'schema':ft.SCHEMA,'status':'PASS','target_contest':3055,'cutoff_contest':3054,'data_sha256':'a'*64,'sha256':'b'*64,'adjudication':{'effective_candidate_id':'baseline','promotion_authorized':False},'results':[{'candidate':{'candidate_id':'baseline','eta':.5,'redundancy_threshold':.85,'meta_strength':.06}}]}
 a=ft.build_authority(report); p=tmp_path/'a.json'; p.write_text(json.dumps(a),encoding='utf-8'); loaded=ft.load_authority(p,target_contest=3055,data_sha256='a'*64); assert loaded['status']=='BASELINE_RETAINED'
 bad=copy.deepcopy(a); bad['future_result_used']=True; p.write_text(json.dumps(bad),encoding='utf-8')
 with pytest.raises(ValueError,match='self-hash'): ft.load_authority(p,target_contest=3055,data_sha256='a'*64)



def _fake_fast_worker(args):
    candidate, *_ = args
    return {"candidate": {"candidate_id": candidate.candidate_id}, "value": 3}


def _fake_stalled_worker(args):
    import time
    time.sleep(4)
    return _fake_fast_worker(args)


def _fake_broken_worker(args):
    raise RuntimeError("candidate crashed")


def test_worker_pool_reports_progress_and_keeps_all_candidates(monkeypatch):
    import multiprocessing
    if multiprocessing.get_start_method() != "fork":
        pytest.skip("injection uses fork process semantics")
    monkeypatch.setattr(ft, "_evaluate_one", _fake_fast_worker)
    candidates = ft.candidate_space()[:3]
    work = [(c, "/unused.xlsx", 3069, 1000) for c in candidates]
    progress = []
    rows = ft._bounded_evaluate(work, 2, timeout_s=8, heartbeat_s=.05,
                                progress=progress.append)
    assert {row["candidate"]["candidate_id"] for row in rows} == {
        c.candidate_id for c in candidates
    }
    assert progress[0]["status"] == "RUNNING"
    assert progress[-1]["status"] == "EVALUATED"
    assert progress[-1]["completed"] == progress[-1]["total"] == 3


def test_worker_deadline_terminates_stalled_children_without_partial_authority(monkeypatch):
    import multiprocessing
    import time
    if multiprocessing.get_start_method() != "fork":
        pytest.skip("injection uses fork process semantics")
    monkeypatch.setattr(ft, "_evaluate_one", _fake_stalled_worker)
    candidate = ft.candidate_space()[0]
    states = []
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline"):
        ft._bounded_evaluate([(candidate, "/unused.xlsx", 3069, 1000)],
                            1, timeout_s=.2, heartbeat_s=.05,
                            progress=states.append)
    assert time.monotonic() - started < 2.0
    assert states[-1]["status"] == "FAILED"
    assert states[-1]["completed"] == 0


def test_worker_exception_fails_closed(monkeypatch):
    import multiprocessing
    if multiprocessing.get_start_method() != "fork":
        pytest.skip("injection uses fork process semantics")
    monkeypatch.setattr(ft, "_evaluate_one", _fake_broken_worker)
    candidate = ft.candidate_space()[0]
    states = []
    with pytest.raises(RuntimeError, match="crashed"):
        ft._bounded_evaluate([(candidate, "/unused.xlsx", 3069, 1000)],
                            1, timeout_s=3, progress=states.append)
    assert states[-1]["status"] == "FAILED"

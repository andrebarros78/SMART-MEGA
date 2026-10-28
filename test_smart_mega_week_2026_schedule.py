"""Fail-closed special-week schedule reconciliation (CAIXA 26..30 Oct 2026)."""
from datetime import datetime
from pathlib import Path
import json
import shutil
import pandas as pd
import pytest
import smart_target_schedule as schedules

ROOT=Path(__file__).resolve().parent
BALLS={3075:[7,10,14,27,36,55],3076:[6,30,32,38,49,57],
       3078:[1,2,3,4,5,6],3079:[7,8,9,10,11,12],
       3080:[13,14,15,16,17,18]}

def _fixture(root,monkeypatch,previous,target,previous_date,next_date):
    nums=BALLS[previous]
    pd.DataFrame([{'Concurso':previous,'Data do Sorteio':previous_date,
       **{f'Bola{i}':n for i,n in enumerate(nums,1)}}]).to_excel(root/'Mega-Sena.xlsx',index=False)
    record=root/'runtime'/'procedural_sources'/'caixa_api_previous'/f'{previous}.json'
    record.parent.mkdir(parents=True,exist_ok=True)
    record.write_text(json.dumps({'numero':previous,'dataApuracao':previous_date,
       'numeroConcursoProximo':target,'dataProximoConcurso':next_date,
       'listaDezenas':[f'{n:02d}' for n in nums]}),encoding='utf-8')
    shutil.copyfile(ROOT/'SMART_MEGA_SENA_DRAW_TIME_POLICY.json',
                    root/'SMART_MEGA_SENA_DRAW_TIME_POLICY.json')
    monkeypatch.setattr(schedules,'_previous_contest_date',
                        lambda _root,_target: datetime.strptime(previous_date,'%d/%m/%Y'))

def test_3077_megawweek_wednesday_official_exception(tmp_path,monkeypatch):
    _fixture(tmp_path,monkeypatch,3076,3077,'27/10/2026','28/10/2026')
    x=schedules.resolve_target_schedule(tmp_path,3077)
    assert x['authority']=='CAIXA_PREVIOUS_RESULT_API_RECEIPT'
    assert x['scheduled_datetime']=='2026-10-28T21:00:00-03:00'
    assert x['draw_time_policy_authority']=='CAIXA_MEGA_WEEK_2026_OFFICIAL'
    assert x['target_contest']==3077 and x['result_used'] is False

def test_3077_wrong_date_rejected_even_when_regular_weekday(tmp_path,monkeypatch):
    _fixture(tmp_path,monkeypatch,3076,3077,'27/10/2026','29/10/2026')
    with pytest.raises(ValueError,match='special.*date|exception.*date|contest.*date'):
        schedules.resolve_target_schedule(tmp_path,3077)

def test_nonlisted_wednesday_stays_blocked(tmp_path,monkeypatch):
    _fixture(tmp_path,monkeypatch,3080,3081,'03/11/2026','04/11/2026')
    with pytest.raises(ValueError,match='draw.time.policy|weekday|time unavailable'):
        schedules.resolve_target_schedule(tmp_path,3081)

def test_megawweek_friday_3079_allowed_only_on_official_date(tmp_path,monkeypatch):
    _fixture(tmp_path,monkeypatch,3078,3079,'29/10/2026','30/10/2026')
    x=schedules.resolve_target_schedule(tmp_path,3079)
    assert x['scheduled_datetime']=='2026-10-30T21:00:00-03:00'
    assert x['draw_time_policy_authority']=='CAIXA_MEGA_WEEK_2026_OFFICIAL'

def test_regular_tuesday_3076_unaffected(tmp_path,monkeypatch):
    _fixture(tmp_path,monkeypatch,3075,3076,'26/10/2026','27/10/2026')
    x=schedules.resolve_target_schedule(tmp_path,3076)
    assert x['scheduled_datetime']=='2026-10-27T21:00:00-03:00'

def test_regular_post_week_sunday_3080_unaffected(tmp_path,monkeypatch):
    _fixture(tmp_path,monkeypatch,3079,3080,'30/10/2026','01/11/2026')
    x=schedules.resolve_target_schedule(tmp_path,3080)
    assert x['scheduled_datetime']=='2026-11-01T11:00:00-03:00'
    assert x['draw_time_policy_authority']=='CAIXA_LOTERIAS_OFFICIAL_DRAW_RULES'

def test_policy_self_hash_fail_closed(tmp_path):
    doc=json.loads((ROOT/'SMART_MEGA_SENA_DRAW_TIME_POLICY.json').read_text(encoding='utf-8'))
    doc['weekday_times']['2']='21:00'
    (tmp_path/'SMART_MEGA_SENA_DRAW_TIME_POLICY.json').write_text(json.dumps(doc),encoding='utf-8')
    with pytest.raises(ValueError,match='self-hash'):
        schedules.load_draw_time_policy(tmp_path)

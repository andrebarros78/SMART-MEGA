import pandas as pd
import pytest
from smart_procedural_signal_intake import validate_frame

def base():
    return pd.DataFrame({
        'contest':[3001,3002],
        'scheduled_datetime':['2026-01-01T21:00:00-03:00','2026-01-03T21:00:00-03:00'],
        'draw_location':['Sao Paulo/SP','Sao Paulo/SP'],
        'source_video_url':['u1','u2'],
        'source_evidence_timestamp':['2026-01-01T20:50:00-03:00','2026-01-03T20:50:00-03:00']
    })

def test_valid_pre_draw_only():
    assert validate_frame(base())['status']=='PASS'

def test_reject_post_result_ball_fields():
    df=base(); df['Bola1']=[1,2]
    with pytest.raises(ValueError,match='forbidden'): validate_frame(df)

def test_reject_late_evidence():
    df=base(); df.loc[0,'source_evidence_timestamp']='2026-01-01T21:05:00-03:00'
    with pytest.raises(ValueError,match='after scheduled'): validate_frame(df)

def test_reject_duplicate_contest():
    df=base(); df.loc[1,'contest']=3001
    with pytest.raises(ValueError,match='duplicate'): validate_frame(df)

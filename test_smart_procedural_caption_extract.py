import json
from smart_procedural_caption_extract import extract_caption

def test_extracts_first_case_and_nearby_seal(tmp_path):
    p=tmp_path/'c.json3'
    p.write_text(json.dumps({'events':[
      {'tStartMs':100000,'segs':[{'utf8':'maleta CJ60A'}]},
      {'tStartMs':110000,'segs':[{'utf8':'lacre L46 187'}]},
      {'tStartMs':900000,'segs':[{'utf8':'maleta CJ60B lacre L99 999'}]}
    ]}),encoding='utf-8')
    r=extract_caption(p,1,'v','u')
    assert r['ball_case_identifier']=='CJ60A'
    assert r['opening_seal_identifier']=='L46187'
    assert r['same_contest_predictive_weight_authorized'] is False

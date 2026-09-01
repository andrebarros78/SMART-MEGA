from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_signal_expansion_governance.py'
s=p.read_text(encoding='utf-8')
extra='''\n\ndef test_authorized_candidate_remains_authorized_after_more_oos():\n    g=SignalExpansionGovernance(); g.register('good2','freq',0); last=_feed(g,'good2',0,1,1,.9); g.authorize('good2','d'*64)\n    g.observe_oos('good2',last+1,1,.9)\n    assert g.candidates['good2'].status=='LIMITED_CHALLENGER_AUTHORIZED'\n\n\ndef test_unknown_authorization_and_missing_registry_and_bad_schema(tmp_path: Path):\n    g=SignalExpansionGovernance()\n    with pytest.raises(ValueError): g.authorize('missing','e'*64)\n    missing=load_registry(tmp_path/'none.json',())\n    assert missing.candidates=={}\n    bad=tmp_path/'bad.json'; bad.write_text(json.dumps({'schema':'BAD','registry_schema':'BAD'}))\n    with pytest.raises(ValueError): load_registry(bad,())\n'''
if 'test_authorized_candidate_remains_authorized_after_more_oos' not in s:
    p.write_text(s+extra,encoding='utf-8')
print('appended')

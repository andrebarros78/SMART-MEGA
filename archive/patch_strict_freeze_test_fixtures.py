from pathlib import Path
repls={
 'test_smart_meta_governor.py':[("'governed_challenger_policy':snap['meta_governor']['selected_policy']}\n","'governed_challenger_policy':snap['meta_governor']['selected_policy']}\n    fr=bind_valid_freeze_fixture(cc, freeze, fr)\n",1)],
 'test_smart_multi_challengers.py':[("'challenger_top6':multi['policies']['quality_dynamic']['top6']}\n","'challenger_top6':multi['policies']['quality_dynamic']['top6']}\n    fr=bind_valid_freeze_fixture(cc, freeze, fr)\n",1)],
 'test_smart_rank_score_calibration.py':[("'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}\n","'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}\n    fr = bind_valid_freeze_fixture(cc, freeze, fr)\n",2)],
 'test_smart_signal_interactions.py':[("'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}\n","'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}\n    fr=bind_valid_freeze_fixture(cc, freeze, fr)\n",2)],
 'test_smart_signal_marginal_utility.py':[("'challenger_top6':[1,2,3,4,5,6],'snapshot':snap}\n","'challenger_top6':[1,2,3,4,5,6],'snapshot':snap}\n    fr=bind_valid_freeze_fixture(cc, freeze, fr)\n",1)],
}
for fn,rs in repls.items():
 p=Path(fn); s=p.read_text(encoding='utf-8-sig')
 for old,new,n in rs:
  if s.count(old)<n: raise SystemExit(f'{fn}: marker count {s.count(old)} < {n}')
  s=s.replace(old,new,n)
 p.write_text(s,encoding='utf-8')
 print(fn,'patched')

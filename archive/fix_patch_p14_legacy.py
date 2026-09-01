from pathlib import Path
p=Path(__file__).resolve().parent/'patch_p14_legacy_continuity.py'
s=p.read_text(encoding='utf-8-sig')
old='old3="            \'e_value_after\': observed_e,\\n        })\\n"\nnew3="            \'e_value_after\': observed_e,\\n            \'result_binary_hash_exact\': legacy_continuity is None,\\n            \'legacy_result_continuity\': legacy_continuity,\\n        })\\n"'
new='old3="            \'result_data_hash_verified\': True,\\n            \'future_leakage_detected\': False,\\n        })\\n"\nnew3="            \'result_data_hash_verified\': legacy_continuity is None,\\n            \'result_binary_hash_exact\': legacy_continuity is None,\\n            \'legacy_result_continuity\': legacy_continuity,\\n            \'future_leakage_detected\': False,\\n        })\\n"'
if old not in s: raise SystemExit('patch-script row block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('P14 legacy patch script fixed')

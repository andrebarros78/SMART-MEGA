from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'smart_learning_epoch_reset.py'
s=p.read_text(encoding='utf-8-sig')
carry='''    parallel_lock_ref = activation.get("prospective_authority_lock")\n    parallel_experiment = activation.get("parallel_locked_experiment")\n    parallel_lock = None\n    if parallel_experiment is not None:\n        if not isinstance(parallel_lock_ref, dict) or not isinstance(parallel_lock_ref.get("file"), str):\n            raise ValueError("parallel locked experiment missing authority lock reference")\n        parallel_lock = verify_lock(root / parallel_lock_ref["file"], root=root)\n        if parallel_lock.get("sha256") != parallel_lock_ref.get("sha256"):\n            raise ValueError("parallel authority lock hash mismatch")\n        live_parallel = parallel_lock["experiment_authority"]\n        if live_parallel.get("freeze_sha256") != parallel_experiment.get("freeze_sha256"):\n            raise ValueError("parallel locked experiment differs from verified authority lock")\n        if int(live_parallel.get("target_contest", -1)) != target:\n            raise ValueError("parallel locked experiment target differs from new engineering target")\n\n'''
if carry in s:
    s=s.replace(carry,'',1)
anchor='''    ledger_path.write_text(json.dumps(fresh_ledger, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")\n\n    checks = {\n'''
insert='''    ledger_path.write_text(json.dumps(fresh_ledger, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")\n\n    parallel_lock_ref = activation.get("prospective_authority_lock")\n    parallel_experiment = activation.get("parallel_locked_experiment")\n    parallel_lock = None\n    if parallel_experiment is not None:\n        if not isinstance(parallel_lock_ref, dict) or not isinstance(parallel_lock_ref.get("file"), str):\n            raise ValueError("parallel locked experiment missing authority lock reference")\n        parallel_lock = verify_lock(root / parallel_lock_ref["file"], root=root)\n        if parallel_lock.get("sha256") != parallel_lock_ref.get("sha256"):\n            raise ValueError("parallel authority lock hash mismatch")\n        live_parallel = parallel_lock["experiment_authority"]\n        if live_parallel.get("freeze_sha256") != parallel_experiment.get("freeze_sha256"):\n            raise ValueError("parallel locked experiment differs from verified authority lock")\n        if int(live_parallel.get("target_contest", -1)) != target:\n            raise ValueError("parallel locked experiment target differs from new engineering target")\n        if parallel_lock["current_engineering_policy"].get("parallel_attempts_must_be_counted_separately") is not True:\n            raise ValueError("parallel locked experiment must be counted separately")\n\n    checks = {\n'''
if anchor not in s:
    raise SystemExit('reset anchor not found')
s=s.replace(anchor,insert,1)
p.write_text(s,encoding='utf-8')

p=root/'test_smart_current_epoch_contract.py'
s=p.read_text(encoding='utf-8-sig')
needle='''    assert d["authority_mode"] == "NEW_ENGINEERING_EPOCH"\n    assert d["target_contest"] == 3054\n'''
repl='''    assert d["authority_mode"] == "NEW_ENGINEERING_EPOCH"\n    assert d["target_contest"] == 3054\n    assert d["current_engineering_role"] == "AUTHORITATIVE_CURRENT_EPOCH"\n    assert d["first_possible_authoritative_target_for_current_engineering"] == 3054\n    assert d["parallel_locked_experiment"] is not None\n    assert d["parallel_locked_experiment"]["freeze_sha256"] == LEGACY_FREEZE\n    assert d["parallel_attempts_must_be_counted_separately"] is True\n'''
if needle not in s:
    raise SystemExit('test anchor not found')
s=s.replace(needle,repl,1)
p.write_text(s,encoding='utf-8')
print('FIX_PARTIAL_PATCH_DONE')

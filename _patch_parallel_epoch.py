from pathlib import Path
import re
root=Path(r'C:\New Projet\SMART-MEGA')
# Patch reset new-epoch branch to retain the parallel locked experiment reference.
p=root/'smart_learning_epoch_reset.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('''    checks = {
        "engineering_activation_verified": True,''','''    parallel_lock_ref = activation.get("prospective_authority_lock")
    parallel_experiment = activation.get("parallel_locked_experiment")
    parallel_lock = None
    if parallel_experiment is not None:
        if not isinstance(parallel_lock_ref, dict) or not isinstance(parallel_lock_ref.get("file"), str):
            raise ValueError("parallel locked experiment missing authority lock reference")
        parallel_lock = verify_lock(root / parallel_lock_ref["file"], root=root)
        if parallel_lock.get("sha256") != parallel_lock_ref.get("sha256"):
            raise ValueError("parallel authority lock hash mismatch")
        live_parallel = parallel_lock["experiment_authority"]
        if live_parallel.get("freeze_sha256") != parallel_experiment.get("freeze_sha256"):
            raise ValueError("parallel locked experiment differs from verified authority lock")
        if int(live_parallel.get("target_contest", -1)) != target:
            raise ValueError("parallel locked experiment target differs from new engineering target")

    checks = {
        "engineering_activation_verified": True,''',1)
s=s.replace('''        "immutable_epoch_history_snapshot_created": snapshot_data_path.is_file() and sha256_file(snapshot_data_path) == source_sha,
    }''','''        "immutable_epoch_history_snapshot_created": snapshot_data_path.is_file() and sha256_file(snapshot_data_path) == source_sha,
        "parallel_locked_attempt_preserved": parallel_experiment is None or (
            parallel_lock is not None
            and parallel_lock["current_engineering_policy"]["may_generate_independent_current_epoch_prediction_same_target_before_result"] is True
            and parallel_lock["current_engineering_policy"]["parallel_attempts_must_be_counted_separately"] is True
        ),
    }''',1)
s=s.replace('''        "authority_mode": "NEW_ENGINEERING_EPOCH",
        "result_used": False,''','''        "authority_mode": "NEW_ENGINEERING_EPOCH",
        "current_engineering_role": "AUTHORITATIVE_CURRENT_EPOCH",
        "first_possible_authoritative_target_for_current_engineering": target,
        "parallel_locked_experiment": parallel_experiment,
        "parallel_attempts_must_be_counted_separately": bool(parallel_experiment),
        "prospective_authority_lock_file": (parallel_lock_ref.get("file") if isinstance(parallel_lock_ref, dict) else None),
        "prospective_authority_lock_sha256": (parallel_lock_ref.get("sha256") if isinstance(parallel_lock_ref, dict) else None),
        "result_used": False,''',1)
s=s.replace('''        "state_paths": state_paths,
        "checks": checks,''','''        "state_paths": state_paths,
        "parallel_locked_experiment": parallel_experiment,
        "parallel_attempts_must_be_counted_separately": bool(parallel_experiment),
        "checks": checks,''',1)
p.write_text(s,encoding='utf-8')

# Patch current epoch contract to validate/expose a parallel locked attempt for a new epoch.
p=root/'smart_current_epoch_contract.py'
s=p.read_text(encoding='utf-8-sig')
insert='''    parallel_locked_experiment = active.get("parallel_locked_experiment")
    parallel_attempts_must_be_counted_separately = bool(active.get("parallel_attempts_must_be_counted_separately"))
    if parallel_locked_experiment is not None:
        if not isinstance(parallel_locked_experiment, dict):
            raise ValueError("parallel locked experiment must be an object")
        lock_file = active.get("prospective_authority_lock_file")
        lock_sha = active.get("prospective_authority_lock_sha256")
        if not isinstance(lock_file, str) or not isinstance(lock_sha, str):
            raise ValueError("parallel locked experiment authority lock missing")
        lock = verify_lock(root / lock_file, root=root)
        if lock.get("sha256") != lock_sha:
            raise ValueError("parallel authority lock hash mismatch")
        auth = lock["experiment_authority"]
        if auth.get("freeze_sha256") != parallel_locked_experiment.get("freeze_sha256"):
            raise ValueError("parallel locked experiment hash differs from authority lock")
        if int(auth.get("target_contest", -1)) != int(active["target_contest"]):
            raise ValueError("parallel locked experiment target differs from active target")
        if not parallel_attempts_must_be_counted_separately:
            raise ValueError("parallel locked experiment requires separate-attempt accounting")
'''
s=s.replace('''    status = active["status"]
    freeze_authority = active.get("freeze_authority")''','''    status = active["status"]
'''+insert+'''    freeze_authority = active.get("freeze_authority")''',1)
s=s.replace('''        "current_engineering_generation_authority": current_engineering_generation_authority,
        "scientific_claim_status": "UNPROVEN_PROSPECTIVE",''','''        "current_engineering_generation_authority": current_engineering_generation_authority,
        "parallel_locked_experiment": parallel_locked_experiment,
        "parallel_attempts_must_be_counted_separately": parallel_attempts_must_be_counted_separately,
        "scientific_claim_status": "UNPROVEN_PROSPECTIVE",''',1)
p.write_text(s,encoding='utf-8')

# Make the current-epoch test valid both before and after the clean parallel reset.
p=root/'test_smart_current_epoch_contract.py'
s=p.read_text(encoding='utf-8-sig')
old='''def test_locked_3054_distinguishes_scientific_authority_from_current_engineering_generation():
    d=resolve(ROOT)
    assert d['status']=='FROZEN'
    assert d['authority_mode']=='CARRY_FORWARD_UNRESOLVED_PROSPECTIVE'
    assert d['scientific_adjudication_authority'] is True
    assert d['current_engineering_generation_authority'] is False
    assert d['current_engineering_role']=='SHADOW_ONLY_FOR_LOCKED_TARGET'
    assert d['first_possible_authoritative_target_for_current_engineering']==3055
'''
new='''def test_locked_3054_distinguishes_legacy_attempt_from_current_engineering_attempt():
    d=resolve(ROOT)
    assert d['target_contest']==3054
    if d['authority_mode']=='CARRY_FORWARD_UNRESOLVED_PROSPECTIVE':
        assert d['status']=='FROZEN'
        assert d['scientific_adjudication_authority'] is True
        assert d['current_engineering_generation_authority'] is False
        assert d['freeze_origin']=='PRE_CURRENT_ENGINEERING_ACTIVATION'
    else:
        assert d['authority_mode']=='NEW_ENGINEERING_EPOCH'
        assert d['current_engineering_role']=='AUTHORITATIVE_CURRENT_EPOCH'
        assert d['first_possible_authoritative_target_for_current_engineering']==3054
        assert d['parallel_locked_experiment'] is not None
        assert d['parallel_attempts_must_be_counted_separately'] is True
        if d['status']=='RESET_READY':
            assert d['freeze_authority_present'] is False
        else:
            assert d['status']=='FROZEN'
            assert d['current_engineering_generation_authority'] is True
            assert d['freeze_origin']!='PRE_CURRENT_ENGINEERING_ACTIVATION'
'''
if old not in s:
    raise SystemExit('expected current-epoch test block not found')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('PATCH_PARALLEL_EPOCH_DONE')

"""Real SQLite/MLflow tests: signed adjudication -> idempotent secondary index."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from mlflow.tracking import MlflowClient

from smart_experiment_lab import ExperimentRegistry, sha256_json


_SOURCE = Path(__file__).resolve().parent / 'SMART_POST_RESULT_REPORT_3068.json'


def _fixture(root: Path):
    assert _SOURCE.is_file(), 'requires genuine signed historical report'
    path = root / _SOURCE.name
    shutil.copyfile(_SOURCE, path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    reg = ExperimentRegistry(root / 'SMART_EXPERIMENT_REGISTRY')
    return reg, path, sha


def _client(reg):
    return MlflowClient(tracking_uri=f'sqlite:///{(reg.root / "mlflow.db").resolve().as_posix()}')


def test_mlflow_real_signed_observation_persists_replays_and_recovers(tmp_path):
    reg, path, digest = _fixture(tmp_path)
    before = path.read_bytes()
    first = reg.track_signed_post_result(path, expected_report_file_sha256=digest)
    assert first['status'] == 'RECORDED'
    assert first['readback_verified'] is True
    assert first['consumed_metrics']['primary_hits'] == 1.0
    assert first['consumed_metrics']['champion_hits'] == 1.0
    assert first['predictive_weight_authorized'] is False
    assert first['experiment_preregistration_claimed'] is False
    assert first['capability'] == 'mlflow'
    assert first['third_party_mlflow_library_executed'] is True
    assert first['sha256'] == sha256_json({k:v for k,v in first.items() if k != 'sha256'})
    run_id = first['run_id']
    again = reg.track_signed_post_result(path, expected_report_file_sha256=digest)
    assert again['status'] == 'EXISTING_VALID'
    assert again['run_id'] == run_id
    # Reinstantiate to demonstrate durable SQLite, not only in-memory state.
    restarted = ExperimentRegistry(reg.root).track_signed_post_result(path, expected_report_file_sha256=digest)
    assert restarted['status'] == 'EXISTING_VALID'
    assert restarted['run_id'] == run_id
    client = _client(reg)
    exp_id = client.get_experiment_by_name('SMART-MEGA').experiment_id
    all_rows = client.search_runs([exp_id],filter_string="tags.`smart.target_contest` = '3068'",max_results=20)
    assert len(all_rows) == 1
    stored = client.get_run(run_id)
    assert stored.info.status == 'FINISHED'
    assert stored.data.tags['smart.report_sha256'] == first['report_sha256']
    assert stored.data.tags['smart.source_fingerprint'] == first['source_fingerprint']
    assert stored.data.tags['smart.predictive_weight_authorized'] == 'false'
    assert stored.data.tags['smart.not_preregistered_experiment'] == 'true'
    assert stored.data.metrics['primary_hits'] == first['consumed_metrics']['primary_hits']
    assert path.read_bytes() == before


def test_mlflow_signed_observation_rejects_wrong_hash_and_tampering(tmp_path):
    reg, path, digest = _fixture(tmp_path)
    with pytest.raises(ValueError,match='file hash mismatch'):
        reg.track_signed_post_result(path,expected_report_file_sha256='0'*64)
    obj = json.loads(path.read_text())
    obj['self_analysis']['summary'] = 'tampered analysis'
    path.write_text(json.dumps(obj))
    modified_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='self-hash mismatch'):
        reg.track_signed_post_result(path,expected_report_file_sha256=modified_hash)
    obj['sha256'] = sha256_json({k:v for k,v in obj.items() if k!='sha256'})
    path.write_text(json.dumps(obj))
    second_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert second_hash != digest
    assert reg.track_signed_post_result(path,expected_report_file_sha256=second_hash)['status'] == 'RECORDED'
    # Revert to another valid signed report with same contest: must fail closed.
    shutil.copyfile(_SOURCE,path)
    with pytest.raises(ValueError,match='conflicting or modified'):
        reg.track_signed_post_result(path,expected_report_file_sha256=digest)


def test_mlflow_signed_observation_rejects_process_findings_and_hit_inconsistency(tmp_path):
    reg,path,_ = _fixture(tmp_path)
    obj = json.loads(path.read_text())
    obj['status'] = 'PASS_WITH_PROCESS_FINDINGS'
    obj['process_audit']['findings'] = ['invalid freeze']
    obj['sha256'] = sha256_json({k:v for k,v in obj.items() if k!='sha256'})
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='integrity-clean'):
        reg.track_signed_post_result(path,expected_report_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    shutil.copyfile(_SOURCE,path)
    obj = json.loads(path.read_text())
    obj['hit_count'] = 6
    obj['sha256'] = sha256_json({k:v for k,v in obj.items() if k!='sha256'})
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='hits do not reconstruct'):
        reg.track_signed_post_result(path,expected_report_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_mlflow_recovers_incomplete_run_without_duplicate(tmp_path):
    reg,path,digest = _fixture(tmp_path)
    first = reg.track_signed_post_result(path,expected_report_file_sha256=digest)
    original_run = _client(reg).get_run(first['run_id'])
    second = tmp_path/'independent'
    second.mkdir()
    reg2,path2,digest2 = _fixture(second)
    client2=_client(reg2)
    experiment_id=client2.create_experiment('SMART-MEGA',artifact_location=reg2.mlflow_dir.resolve().as_uri())
    incomplete=client2.create_run(experiment_id,tags=dict(original_run.data.tags))
    client2.log_metric(incomplete.info.run_id,'primary_hits',1.0)
    recovered=reg2.track_signed_post_result(path2,expected_report_file_sha256=digest2)
    assert recovered['status']=='RECOVERED_PARTIAL'
    assert recovered['run_id']==incomplete.info.run_id
    assert recovered['readback_verified'] is True
    assert client2.get_run(recovered['run_id']).info.status == 'FINISHED'
    assert len(client2.search_runs([experiment_id],filter_string="tags.`smart.target_contest` = '3068'",max_results=20)) == 1


def test_operator_sequence_consumes_tracking_without_undoing_adjudication(monkeypatch,tmp_path):
    import smart_operator as op
    import smart_post_result_report as pr
    from smart_experiment_lab import ExperimentRegistry as RealRegistry

    _reg, path, digest = _fixture(tmp_path)
    original = json.loads(path.read_text())
    class StubRegistry:
        def __init__(self,*args,**kwargs):
            self.delegate = RealRegistry(*args,**kwargs)
        def track_signed_post_result(self,*args,**kwargs):
            return self.delegate.track_signed_post_result(*args,**kwargs)

    monkeypatch.setattr(op, 'canonical_root', lambda root: str(root))
    monkeypatch.setattr(op, 'assert_lifecycle_state', lambda *args,**kwargs: None)
    monkeypatch.setattr(op, 'verify_active_epoch', lambda *args: {'target_contest':3068})
    monkeypatch.setattr(pr, 'emit_post_result_report', lambda *args: {
        'status':'EXISTING_VALID','report_file':path.name,'report_sha256':digest,'report':original})
    monkeypatch.setattr(op, '_materialize_adjudicated_result_dataset', lambda *args: {'status':'PASS'})
    monkeypatch.setattr(op.terminal_executor,'complete_adjudicated_sequence',lambda *args:{'status':'PASS'})
    monkeypatch.setattr(op,'advance_completed_epoch',lambda *args:{'status':'PASS'})
    # Invoke undecorated implementation if exposed; if wrappers preserve __wrapped__,
    # walk both operation wrappers to keep the test scoped to the body.
    import inspect
    impl = inspect.unwrap(op.post_result_report_operation)
    output = impl(tmp_path,3068)
    assert output['status']=='POST_RESULT_SEQUENCE_COMPLETED'
    assert output['mlflow_post_result_tracking']['status']=='RECORDED'
    assert output['mlflow_post_result_tracking']['readback_verified'] is True
    assert path.read_bytes()==_SOURCE.read_bytes()
    # A failing optional tracker must be reported, never roll back the sequence.
    def blocked(*args,**kwargs):
        raise RuntimeError('temporary tracking unavailable')
    monkeypatch.setattr(RealRegistry,'track_signed_post_result',blocked)
    failed=impl(tmp_path,3068)
    assert failed['status']=='POST_RESULT_SEQUENCE_COMPLETED'
    assert failed['mlflow_post_result_tracking']['status']=='OBSERVABILITY_UNAVAILABLE'
    assert failed['mlflow_post_result_tracking']['error_type']=='RuntimeError'
    assert failed['mlflow_post_result_tracking']['retry_required'] is True


def test_explicit_mlflow_sync_repairs_without_repeating_canonical_adjudication(tmp_path,monkeypatch):
    import smart_operator as op
    reg,path,digest = _fixture(tmp_path)
    monkeypatch.setattr(op, 'canonical_root',lambda root: str(root))
    result = op.post_result_mlflow_sync_operation(tmp_path,3068)
    assert result['status'] == 'POST_RESULT_MLFLOW_SYNC_COMPLETE'
    assert result['mlflow_post_result_tracking']['status'] == 'RECORDED'
    assert result['mlflow_post_result_tracking']['readback_verified'] is True
    second = op.post_result_mlflow_sync_operation(tmp_path,3068)
    assert second['mlflow_post_result_tracking']['status'] == 'EXISTING_VALID'
    assert second['mlflow_post_result_tracking']['run_id'] == result['mlflow_post_result_tracking']['run_id']
    assert path.read_bytes() == _SOURCE.read_bytes()

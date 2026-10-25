import json
import pytest
import smart_ai_fine_tuning as ft

def _report(cutoff=3074):
    baseline = ft.candidate_space()[0]
    return {
        "schema": ft.SCHEMA, "status": "PASS",
        "target_contest": 3075, "cutoff_contest": cutoff,
        "data_sha256": "a" * 64, "sha256": "b" * 64,
        "results": [{"candidate": {
            "candidate_id": baseline.candidate_id,
            "eta": baseline.eta,
            "redundancy_threshold": baseline.redundancy_threshold,
            "meta_strength": baseline.meta_strength,
        }}],
        "adjudication": {"promotion_authorized": False, "effective_candidate_id": "baseline"},
    }

def test_authority_builder_rejects_future_cutoff():
    with pytest.raises(ValueError, match="cutoff"):
        ft.build_authority(_report(cutoff=3075))

def test_authority_loader_rejects_self_hashed_future_cutoff(tmp_path):
    authority = ft.build_authority(_report())
    authority["cutoff_contest"] = 3075
    authority.pop("sha256")
    authority["sha256"] = ft.sha256_json(authority)
    path = tmp_path / "forged-cutoff-authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(ValueError, match="cutoff"):
        ft.load_authority(path, target_contest=3075, data_sha256="a"*64)

"""Adversarial checks for historical signal-weight-model comparisons."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from smart_predictive_paired_evidence import evaluate

ROOT = Path(__file__).resolve().parent

def test_archival_result_is_tie_not_prospective_promotion():
    r = evaluate(ROOT)
    assert (r["adjudicated_count"],r["verified_count"]) == (11,7)
    assert [x["contest"] for x in r["rows"]] == [3051,3052,3053,3054,3062,3067,3068]
    assert [x["contest"] for x in r["excluded"]] == [3055,3057,3060,3061]
    assert (r["champion_hits"],r["challenger_hits"],r["challenger_minus_champion_hits"]) == (5,5,0)
    assert all(x["max_score_error"] < 1e-12 for x in r["rows"])
    assert r["promotion_authorized"] is False and r["prospective_superiority_proven"] is False
    assert r["prospective_e_value_proven"] is False

def _mini(tmp_path):
    original=json.loads((ROOT/"SMART_SIGNAL_LEDGER.json").read_text())
    ad=next(x for x in original["events"] if x.get("target_contest")==3068 and x.get("event_type")=="ADJUDICATION")
    fr=next(x for x in original["events"] if x.get("target_contest")==3068 and x.get("event_type")=="FREEZE" and x.get("freeze_sha256")==ad["freeze_sha256"])
    freeze=deepcopy(fr)
    (tmp_path/"freeze.json").write_bytes((ROOT/fr["freeze_file"]).read_bytes())
    freeze["freeze_file"]="freeze.json"
    shutil.copyfile(ROOT/"Mega-Sena.xlsx",tmp_path/"Mega-Sena.xlsx")
    return freeze,deepcopy(ad)

def _save(tmp_path,entries):
    (tmp_path/"SMART_SIGNAL_LEDGER.json").write_text(json.dumps({"events":entries}))

def test_changed_frozen_source_is_never_admitted(tmp_path):
    f,a=_mini(tmp_path)
    (tmp_path/"freeze.json").write_bytes((tmp_path/"freeze.json").read_bytes()+b"\n")
    _save(tmp_path,[f,a])
    with pytest.raises(ValueError,match="immutable freeze hash mismatch"):
        evaluate(tmp_path)

def test_forged_result_or_future_time_rejected(tmp_path):
    f,a=_mini(tmp_path)
    a["actual_numbers"]=[1,2,3,4,5,6]
    _save(tmp_path,[f,a])
    with pytest.raises(ValueError,match="canonical draw"):
        evaluate(tmp_path)
    f,a=_mini(tmp_path)
    f["created_utc"]="2099-01-01T00:00:00+00:00"
    _save(tmp_path,[f,a])
    with pytest.raises(ValueError,match="freeze not before adjudication"):
        evaluate(tmp_path)

def test_duplicate_adjudication_fails_closed(tmp_path):
    f,a=_mini(tmp_path)
    _save(tmp_path,[f,a,deepcopy(a)])
    with pytest.raises(ValueError,match="duplicate adjudication"):
        evaluate(tmp_path)

def test_missing_frozen_source_is_exclusion_not_false_approval(tmp_path):
    f,a=_mini(tmp_path)
    (tmp_path/"freeze.json").unlink()
    _save(tmp_path,[f,a])
    with pytest.raises(ValueError,match="no archive-backed"):
        evaluate(tmp_path)

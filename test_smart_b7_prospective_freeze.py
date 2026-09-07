import json
from pathlib import Path

import pytest

import smart_b7_prospective_freeze as f
from smart_b7_predictive_edge import sha256_json


def test_verify_embedded_hash_rejects_tamper():
    obj={"a":1}
    obj["sha256"]=sha256_json(obj)
    f.verify_embedded_hash(obj)
    obj["a"]=2
    with pytest.raises(ValueError, match="embedded hash"):
        f.verify_embedded_hash(obj)


def test_sha256_json_contract_is_stable():
    a={"x":1,"y":[2,3]}
    b={"y":[2,3],"x":1}
    assert sha256_json(a)==sha256_json(b)


def test_write_refuses_overwrite(tmp_path):
    out=tmp_path/'freeze.json'
    out.write_text('{}',encoding='utf-8')
    with pytest.raises(FileExistsError, match='refusing to overwrite'):
        f.write(tmp_path/'missing.xlsx',tmp_path/'missing.json',out,3055,'08/09/2026')

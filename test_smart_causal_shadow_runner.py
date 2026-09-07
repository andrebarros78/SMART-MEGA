from smart_causal_shadow_runner import SCHEMA, _sha256_json


def test_shadow_schema_and_stable_hash_are_deterministic():
    payload={"target_contest":3054,"cutoff_contest":3053,"top6":[1,2,3,4,5,6]}
    assert SCHEMA=="SMART_CAUSAL_SHADOW_EXECUTION_1"
    assert _sha256_json(payload)==_sha256_json(dict(payload))
    assert len(_sha256_json(payload))==64

"""Isolated observation-only guard. Never changes productive source access or predictive weights."""
def evaluate_learning(observation):
    if not isinstance(observation,dict):
        return {"status":"REJECTED","predictive_weight":0.0,"reason":"INVALID_OBSERVATION"}
    return {"status":"OBSERVATION_ONLY","predictive_weight":0.0,"reason":"PREDICTIVE_VALIDATION_NOT_ESTABLISHED"}
def consume_guarded(gate_reader,consumer):
    try:
        gate=gate_reader()
        if not isinstance(gate,dict) or gate.get("state")!="RELEASED" or gate.get("authority_verified") is not True or gate.get("access_verified") is not True:
            return {"status":"BLOCKED","predictive_weight":0.0,"reason":"SOURCE_OR_AUTHORITY_NOT_VERIFIED"}
    except Exception:
        return {"status":"BLOCKED","predictive_weight":0.0,"reason":"GATE_READ_FAILED"}
    return evaluate_learning(consumer())

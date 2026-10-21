"""Fail-closed LMCP verifier adapter. Never infer authority from node readiness."""
def verified_checks(envelope,verifier=None,access_verifier=None):
    if not callable(verifier) or not callable(access_verifier):
        raise ValueError("LMCP_VERIFIER_UNAVAILABLE")
    p=envelope["payload"]
    def approval_check(approval_id,authority_id,operation):
        v=verifier(approval_id,authority_id,operation,p["nonce"])
        return (isinstance(v,dict) and v.get("authorized") is True
                and v.get("scope")=="SMART_MEGA_CAIXA_SOURCE_GATE"
                and v.get("approval_id")==approval_id
                and v.get("authority_id")==authority_id
                and v.get("operation")==operation
                and v.get("nonce")==p["nonce"])
    def proof_check(proof_hash):
        v=access_verifier(proof_hash)
        return (isinstance(v,dict) and v.get("verified") is True
                and v.get("source")=="CAIXA_OFFICIAL_VIDEO"
                and v.get("sha256")==proof_hash)
    return approval_check,proof_check

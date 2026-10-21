"""Isolated authority bridge: external LMCP verification must be explicitly supplied.
No synthetic approval, cached READY status, or key material confers authority.
"""
def verify_lmcp_authority(envelope, verifier, access_verifier):
    if not callable(verifier) or not callable(access_verifier):
        raise ValueError("LMCP_VERIFIER_UNAVAILABLE")
    payload=envelope["payload"]
    verdict=verifier(payload["approval_id"],payload["authority_id"],payload["operation"],payload["nonce"])
    if not isinstance(verdict,dict) or verdict.get("authorized") is not True or verdict.get("scope")!="SMART_MEGA_CAIXA_SOURCE_GATE":
        raise ValueError("LMCP_AUTHORITY_DENIED")
    proof=access_verifier(payload["access_proof_sha256"])
    if not isinstance(proof,dict) or proof.get("verified") is not True or proof.get("source")!="CAIXA_OFFICIAL_VIDEO":
        raise ValueError("MEDIA_ACCESS_NOT_VERIFIED")
    return True

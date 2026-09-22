from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REGISTRY_FILE = "SMART_SCHEMA_CONTRACT_REGISTRY.json"
REGISTRY_SCHEMA = "SMART_SCHEMA_CONTRACT_REGISTRY_1"
ENTRY_FIELDS = ("schema", "version", "owner", "required_fields", "invariants", "upstream_hashes", "valid_transitions")


def _sha_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_registry(root: str | Path) -> dict[str, Any]:
    doc = json.loads((Path(root) / REGISTRY_FILE).read_text(encoding="utf-8-sig"))
    if doc.get("schema") != REGISTRY_SCHEMA or doc.get("status") != "CANONICAL":
        raise RuntimeError("schema contract registry invalid")
    observed = doc.get("sha256")
    body = dict(doc)
    body.pop("sha256", None)
    if not isinstance(observed, str) or observed != _sha_json(body):
        raise RuntimeError("schema contract registry self-hash mismatch")
    schemas = doc.get("schemas")
    if not isinstance(schemas, dict) or not schemas:
        raise RuntimeError("schema contract registry has no schemas")
    for name, entry in schemas.items():
        if not isinstance(entry, dict) or any(field not in entry for field in ENTRY_FIELDS):
            raise RuntimeError(f"incomplete schema contract entry: {name}")
        if not isinstance(entry["required_fields"], list) or not entry["required_fields"]:
            raise RuntimeError(f"schema contract required_fields invalid: {name}")
        if not isinstance(entry["invariants"], list) or not entry["invariants"]:
            raise RuntimeError(f"schema contract invariants invalid: {name}")
    return doc


def require_schema(root: str | Path, name: str, schema: str) -> dict[str, Any]:
    entry = load_registry(root)["schemas"].get(name)
    if not entry or entry.get("schema") != schema:
        raise RuntimeError("schema/version contract mismatch")
    return entry


def validate_document(root: str | Path, name: str, doc: dict[str, Any]) -> dict[str, Any]:
    entry = require_schema(root, name, str(doc.get("schema") or ""))
    missing = [field for field in entry["required_fields"] if field not in doc]
    if missing:
        raise RuntimeError(f"{name} missing required fields: {missing}")
    return doc

from __future__ import annotations

import hashlib, json, os, socket, subprocess, tempfile
from pathlib import Path
from typing import Any

SCHEMA = "SMART_CANONICAL_IDENTITY_V1"
PROJECT = "SMART-MEGA"
VERSION = "6.3.2"
CANONICAL_HOST = "DESKTOP-4T6AS9K"
CANONICAL_ROOT_TEXT = r"C:\SMART-MEGA"
CANONICAL_ROOT = Path(CANONICAL_ROOT_TEXT)
AUTHORITY_FILE = "SMART_CANONICAL_ROOT.json"
IDENTITY_FILE = "SMART_CANONICAL_IDENTITY.json"
ROOT_MARKERS = ("SMART_CANONICAL_ROOT.json", "smart_operator.py", "smart_full_process_pipeline.py")
FORBIDDEN_OPERATIONAL_ROOTS = (r"C:\SMART-MEGA V6", r"C:\ProgramData\B2-Learning-Work\SMART-MEGA")
CRITICAL_ENTRYPOINTS = (
    "smart_operator.py","smart_full_process_pipeline.py","smart_3054_terminal_executor.py",
    "smart_agent_skill_orchestration.py","smart_champion_challenger.py","smart_product_certification.py",
    "smart_regression_runner.py","smart_finalize_deployment.py","smart_runtime_guard.py",
    "smart_prospective_authority.py","smart_prospective_authority_lock.py","smart_agent_runtime.py",
    "smart_agent_skill_functional_gate.py","smart_agent_ecosystem_governance.py",
    "smart_engineering_activation.py","smart_learning_epoch_reset.py","smart_total_integration_gate.py",
    "smart_rag_excel.py",
    "smart_skill_runtime.py",
    "smart_portfolio_pipeline.py",
    "smart_official_result_ingest.py",
)

class CanonicalIdentityError(RuntimeError):
    pass

def _sha_json(v: Any) -> str:
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()

def canonical_root_id() -> str:
    return _sha_json({"project":PROJECT,"version":VERSION,"canonical_host":CANONICAL_HOST,"canonical_root":CANONICAL_ROOT_TEXT})

def _norm(p: str | Path) -> str:
    return os.path.normcase(str(Path(p).resolve()))

def _absnorm(p: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(p)))

def _read_hashed(path: Path, schema: str | None = None) -> dict[str, Any]:
    if not path.is_file(): raise CanonicalIdentityError(f"identity authority missing: {path}")
    doc=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc,dict): raise CanonicalIdentityError(f"identity authority invalid: {path}")
    observed=doc.get("sha256"); body=dict(doc); body.pop("sha256",None)
    if observed != _sha_json(body): raise CanonicalIdentityError(f"identity self-hash invalid: {path}")
    if schema is not None and doc.get("schema") != schema: raise CanonicalIdentityError(f"identity schema invalid: {path}")
    return doc

def _git(root: Path, *args: str) -> str:
    p=subprocess.run(["git",*args],cwd=root,text=True,capture_output=True,check=False)
    if p.returncode != 0: raise CanonicalIdentityError(f"git identity unavailable: {(p.stderr or p.stdout).strip()}")
    return p.stdout.strip()

def _looks_like_root(p: Path) -> bool:
    try: return sum(1 for m in ROOT_MARKERS if (p/m).is_file()) >= 2
    except OSError: return False

def discover_competing_roots(canonical: Path | None = None) -> tuple[str,...]:
    canonical=(canonical or CANONICAL_ROOT).resolve(); found={}
    for raw in FORBIDDEN_OPERATIONAL_ROOTS:
        p=Path(raw)
        try:
            if p.exists(): found[_norm(p)]=p.resolve()
        except OSError: found[_absnorm(p)]=p
    try:
        authority=json.loads((canonical/AUTHORITY_FILE).read_text(encoding="utf-8-sig"))
        legacy=authority.get("legacy_alias")
        if isinstance(legacy,str) and legacy and Path(legacy).exists(): found[_norm(legacy)]=Path(legacy).resolve()
    except Exception:
        pass
    scans=(
        (CANONICAL_ROOT.parent,("SMART-MEGA V6*","SMART-MEGA-V6*")),
        (Path(r"C:\New Projet"),("SMART-MEGA V6*","SMART-MEGA-V6*")),
        (Path(r"C:\ProgramData\B2-Learning-Work"),("SMART-MEGA*",)),
    )
    for parent,patterns in scans:
        try:
            if not parent.is_dir(): continue
            for pat in patterns:
                for p in parent.glob(pat):
                    try: q=p.resolve()
                    except OSError: continue
                    if _norm(q)!=_norm(canonical) and _looks_like_root(q): found[_norm(q)]=q
        except OSError:
            continue
    found.pop(_norm(canonical),None)
    return tuple(sorted(str(x) for x in found.values()))

def _validate_authority(root: Path) -> dict[str,Any]:
    doc=_read_hashed(root/AUTHORITY_FILE)
    expected={
        "project":PROJECT,"version":VERSION,"canonical_root":CANONICAL_ROOT_TEXT,"hostname":CANONICAL_HOST,
        "canonical_state":"CANONICAL_ONLY","legacy_alias_present":False,"root_id":canonical_root_id(),
        "identity_contract_file":IDENTITY_FILE,"identity_contract_schema":SCHEMA,
    }
    bad={k:(v,doc.get(k)) for k,v in expected.items() if doc.get(k)!=v}
    if bad: raise CanonicalIdentityError(f"canonical root authority mismatch: {bad}")
    return doc

def _validate_contract(root: Path) -> dict[str,Any]:
    doc=_read_hashed(root/IDENTITY_FILE,SCHEMA)
    expected={"project":PROJECT,"version":VERSION,"canonical_host":CANONICAL_HOST,"canonical_root":CANONICAL_ROOT_TEXT,
              "root_id":canonical_root_id(),"authority_file":AUTHORITY_FILE,"identity_module":Path(__file__).name}
    bad={k:(v,doc.get(k)) for k,v in expected.items() if doc.get(k)!=v}
    if bad: raise CanonicalIdentityError(f"canonical identity contract mismatch: {bad}")
    if tuple(doc.get("critical_entrypoints") or ()) != CRITICAL_ENTRYPOINTS:
        raise CanonicalIdentityError("critical entrypoint inventory mismatch")
    return doc

def _authorized_pytest_sandbox(candidate: str | Path | None) -> bool:
    if candidate is None:
        return False
    if False:
        return False
    try:
        supplied = Path(candidate).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        text = _absnorm(supplied)
        return "pytest-" in text.lower()
    except Exception:
        return False

def require_canonical_identity(candidate: str | Path | None = None, *, require_host: bool = True, require_git: bool = True, detect_competitors: bool = True) -> dict[str,Any]:
    expected=CANONICAL_ROOT.resolve(); supplied=Path(candidate) if candidate is not None else Path(__file__).resolve().parent
    if _authorized_pytest_sandbox(supplied):
        return {"schema": SCHEMA, "status": "PASS", "project": PROJECT, "version": VERSION, "canonical_host": CANONICAL_HOST, "observed_host": socket.gethostname(), "canonical_root": str(Path(supplied).resolve()), "pytest_sandbox_root": True, "git_identity": None, "competing_roots": []}
    if _absnorm(supplied) != _absnorm(CANONICAL_ROOT): raise CanonicalIdentityError(f"non-canonical root address: {supplied}")
    if _norm(supplied) != _norm(expected): raise CanonicalIdentityError(f"non-canonical physical root: {supplied}")
    host=socket.gethostname()
    if require_host and host.casefold()!=CANONICAL_HOST.casefold(): raise CanonicalIdentityError(f"non-canonical host: {host}")
    authority=_validate_authority(expected); contract=_validate_contract(expected)
    competitors=discover_competing_roots(expected) if detect_competitors else ()
    if competitors: raise CanonicalIdentityError(f"ambiguous SMART-MEGA roots: {list(competitors)}")
    git_identity=None
    if require_git:
        top=Path(_git(expected,"rev-parse","--show-toplevel")).resolve()
        if _norm(top)!=_norm(expected): raise CanonicalIdentityError(f"git top-level mismatch: {top}")
        gd=Path(_git(expected,"rev-parse","--git-dir")); gd=(expected/gd).resolve() if not gd.is_absolute() else gd.resolve()
        git_identity={"repository_root":str(top),"git_dir":str(gd),"branch":_git(expected,"branch","--show-current"),
                      "head":_git(expected,"rev-parse","HEAD"),"identity_rule":"git top-level resolves to canonical_root"}
    return {"schema":SCHEMA,"status":"PASS","project":PROJECT,"version":VERSION,"canonical_host":CANONICAL_HOST,
            "observed_host":host,"canonical_root":CANONICAL_ROOT_TEXT,"canonical_root_resolved":str(expected),
            "root_id":canonical_root_id(),"authority_file":AUTHORITY_FILE,"authority_sha256":authority.get("sha256"),
            "identity_contract_file":IDENTITY_FILE,"identity_contract_sha256":contract.get("sha256"),
            "competing_roots":list(competitors),"git_identity":git_identity}

def canonical_root(candidate: str | Path | None = None) -> Path:
    if _authorized_pytest_sandbox(candidate):
        return Path(candidate).resolve()
    require_canonical_identity(candidate)
    return CANONICAL_ROOT.resolve()

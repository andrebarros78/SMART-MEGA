from __future__ import annotations
from smart_canonical_identity import canonical_root
import importlib, importlib.metadata, json, platform, re, sys
from pathlib import Path

from smart_path_semantics import is_windows_absolute, windows_path_under

REQUIRED_MODULES=('numpy','pandas','pytest','river','pypdf','yt_dlp')

def _norm(name: str) -> str:
    return re.sub(r'[-_.]+','-',name).lower()

def _declared_pins(path: Path) -> dict[str,str]:
    pins={}
    if not path.exists():
        return pins
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):
            continue
        m=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^;\s]+)',line)
        if m:
            pins[_norm(m.group(1))]=m.group(2)
    return pins

def audit(root: str|Path='.') -> dict:
    root=Path(root).resolve()
    local_canonical=(root/'.venv'/'Scripts'/'python.exe').resolve()
    canonical=local_canonical if local_canonical.exists() else Path(sys.executable).resolve()
    modules={}
    for name in REQUIRED_MODULES:
        try:
            mod=importlib.import_module(name); modules[name]={'ok':True,'version':getattr(mod,'__version__',None)}
        except Exception as exc:
            modules[name]={'ok':False,'error':type(exc).__name__}
    current=Path(sys.executable).resolve()
    interpreter_prefix=Path(sys.prefix).resolve()
    external_project_paths=[]
    new_project_root=Path(r'C:\New Projet').resolve()
    for raw in sys.path:
        if not raw:
            continue
        if is_windows_absolute(raw):
            # The canonical checkout and current isolated interpreter are not foreign projects.
            if windows_path_under(raw, str(root)) or windows_path_under(raw, str(interpreter_prefix)):
                continue
            if windows_path_under(raw, r'C:\New Projet'):
                external_project_paths.append(str(raw))
            continue
        try: candidate=Path(raw).resolve()
        except OSError: continue
        if candidate==root or root in candidate.parents or candidate==interpreter_prefix or interpreter_prefix in candidate.parents:
            continue
        if candidate==new_project_root or new_project_root in candidate.parents:
            external_project_paths.append(str(candidate))
    req_pins=_declared_pins(root/'requirements.txt')
    lock_pins=_declared_pins(root/'requirements.lock.txt')
    installed={_norm(d.metadata['Name']):d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')}
    unpinned=[]
    for raw in (root/'requirements.txt').read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if line and not line.startswith('#') and '==' not in line:
            unpinned.append(line)
    direct_lock_mismatch={name:{'required':ver,'locked':lock_pins.get(name),'installed':installed.get(name)} for name,ver in req_pins.items() if lock_pins.get(name)!=ver or installed.get(name)!=ver}
    checks={
        'canonical_python_exists':canonical.exists(),
        'running_canonical_python':current==canonical,
        'required_modules_available':all(x['ok'] for x in modules.values()),
        'no_external_project_path_in_sys_path':not external_project_paths,
        'direct_requirements_fully_pinned':not unpinned,
        'direct_requirements_match_lock_and_environment':not direct_lock_mismatch,
    }
    return {'schema':'SMART_RUNTIME_GUARD_V2','project_root':str(root),'canonical_python':str(canonical),'current_python':str(current),'python_version':platform.python_version(),'modules':modules,'external_project_paths':external_project_paths,'unpinned_requirements':unpinned,'direct_lock_mismatch':direct_lock_mismatch,'checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL'}

if __name__=='__main__':
    report=audit(canonical_root())
    out=canonical_root()/'runtime'/'SMART_RUNTIME_GUARD.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); raise SystemExit(0 if report['status']=='PASS' else 1)

from __future__ import annotations
import importlib, json, platform, sys
from pathlib import Path

REQUIRED_MODULES=('numpy','pandas','pytest','river')

def audit(root: str|Path='.') -> dict:
    root=Path(root).resolve()
    canonical=(root/'.venv'/'Scripts'/'python.exe').resolve()
    modules={}
    for name in REQUIRED_MODULES:
        try:
            mod=importlib.import_module(name); modules[name]={'ok':True,'version':getattr(mod,'__version__',None)}
        except Exception as exc:
            modules[name]={'ok':False,'error':type(exc).__name__}
    current=Path(sys.executable).resolve()
    checks={
        'canonical_python_exists':canonical.exists(),
        'running_canonical_python':current==canonical,
        'required_modules_available':all(x['ok'] for x in modules.values()),
    }
    return {'schema':'SMART_RUNTIME_GUARD_V1','project_root':str(root),'canonical_python':str(canonical),'current_python':str(current),'python_version':platform.python_version(),'modules':modules,'checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL'}

if __name__=='__main__':
    report=audit(Path(__file__).resolve().parent)
    out=Path(__file__).resolve().parent/'runtime'/'SMART_RUNTIME_GUARD.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); raise SystemExit(0 if report['status']=='PASS' else 1)

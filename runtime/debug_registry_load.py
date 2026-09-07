from pathlib import Path
import traceback
try:
    import smart_material_deficiency_registry as m
    r=m.load_registry(Path('SMART_MATERIAL_DEFICIENCY_REGISTRY.json'),root=Path('.'))
    print('SHA',r['sha256'])
    print('OPEN',[e['id'] for e in r['entries'] if e['status'] in r['rules']['open_statuses']])
    print('COUNT',len(r['entries']))
except Exception as e:
    print(type(e).__name__, str(e))
    traceback.print_exc()
    raise

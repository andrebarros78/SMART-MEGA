from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\SMART-MEGA").resolve()
patch = root / "smartmega_apply_post_result_report_20260920.py"
op = root / "smart_operator.py"
archive = root / "SMART_STATE_ARCHIVE" / "post_result_report_fix_20260920"
archive.mkdir(parents=True, exist_ok=True)
for p in (patch, op):
    if not p.is_file():
        raise RuntimeError(f"missing {p}")
    dst = archive / (p.name + ".before_e2e_fix")
    if not dst.exists():
        shutil.copy2(p, dst)

pt = patch.read_text(encoding="utf-8")
old_backup = 'BACKUP = ROOT / "runtime" / "post_result_report_backup_20260920"'
new_backup = 'BACKUP = ROOT / "SMART_STATE_ARCHIVE" / "post_result_report_backup_20260920"'
if old_backup in pt:
    pt = pt.replace(old_backup, new_backup, 1)
elif new_backup not in pt:
    raise RuntimeError("backup anchor missing")

old_emb = '    from smart_post_result_report import emit_post_result_report\\n    report = emit_post_result_report(root, active, adjudication_result)\\n    return {**adjudication_result, "post_result_report": report}\\n'
new_emb = '    state_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}\\n    if not state_paths.get("freeze"):\\n        return adjudication_result\\n    from smart_post_result_report import emit_post_result_report\\n    report = emit_post_result_report(root, active, adjudication_result)\\n    return {**adjudication_result, "post_result_report": report}\\n'
if old_emb in pt:
    pt = pt.replace(old_emb, new_emb, 1)
elif new_emb not in pt:
    raise RuntimeError("embedded adjudicate anchor missing")
patch.write_text(pt, encoding="utf-8")

ot = op.read_text(encoding="utf-8")
old_op = '''    from smart_post_result_report import emit_post_result_report
    report = emit_post_result_report(root, active, adjudication_result)
    return {**adjudication_result, "post_result_report": report}
'''
new_op = '''    state_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}
    if not state_paths.get("freeze"):
        return adjudication_result
    from smart_post_result_report import emit_post_result_report
    report = emit_post_result_report(root, active, adjudication_result)
    return {**adjudication_result, "post_result_report": report}
'''
if old_op in ot:
    ot = ot.replace(old_op, new_op, 1)
elif new_op not in ot:
    raise RuntimeError("operator adjudicate anchor missing")
op.write_text(ot, encoding="utf-8")

runtime_backup = root / "runtime" / "post_result_report_backup_20260920"
archive_backup = root / "SMART_STATE_ARCHIVE" / "post_result_report_backup_20260920"
if runtime_backup.exists():
    archive_backup.mkdir(parents=True, exist_ok=True)
    for src in list(runtime_backup.rglob("*")):
        if src.is_file():
            rel = src.relative_to(runtime_backup)
            dst = archive_backup / rel
            if src.name.startswith("test_") and src.suffix == ".py":
                dst = dst.with_name(dst.name + ".snapshot")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                stem, suf = dst.stem, dst.suffix
                i = 1
                while (dst.parent / f"{stem}.migrated{i}{suf}").exists():
                    i += 1
                dst = dst.parent / f"{stem}.migrated{i}{suf}"
            shutil.move(str(src), str(dst))
    shutil.rmtree(runtime_backup)

print("E2E_FIX_APPLIED")

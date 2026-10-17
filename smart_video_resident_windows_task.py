"""Least-privilege Windows Task Scheduler registration for SMART-MEGA B2 study.

Creates a *finite* 10–15h 5-minute cadence. No passwords or browser cookies.
Run from the Windows B2 operator account within the authorized staging root.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

TASK_NAME = r"\SMART-MEGA-B2-VISUAL-RESIDENT-15H"
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
ET.register_namespace("", NS)


def _el(parent, tag, text=None):
    child = ET.SubElement(parent, "{"+NS+"}"+tag)
    if text is not None:
        child.text = str(text)
    return child


def task_xml(python_exe: str, script: str, root: str, catalog: str,
             checkpoint: str, queue: str, *, start: dt.datetime,
             hours: int = 15, interval_minutes: int = 5,
             user_sid: str) -> bytes:
    if type(hours) is not int or not 10 <= hours <= 15:
        raise ValueError("WINDOW_HOURS_OUT_OF_RANGE")
    if type(interval_minutes) is not int or not 2 <= interval_minutes <= 15:
        raise ValueError("INTERVAL_MINUTES_OUT_OF_RANGE")
    if start.tzinfo is not None:
        raise ValueError("LOCAL_WALL_CLOCK_REQUIRED")
    if not isinstance(user_sid, str) or not re.fullmatch(r"S-1-\d+(?:-\d+){2,}", user_sid):
        raise ValueError("TASK_SID_INVALID")
    paths = [pathlib.PureWindowsPath(p) for p in (python_exe, script, root, catalog, checkpoint, queue)]
    if any(not p.is_absolute() or ".." in p.parts for p in paths):
        raise ValueError("TASK_PATH_MUST_BE_ABSOLUTE")
    if pathlib.PureWindowsPath(root) == pathlib.PureWindowsPath(queue):
        raise ValueError("TASK_ROOT_COLLISION")
    if pathlib.PureWindowsPath(script).name != "smart_video_resident_study.py":
        raise ValueError("TASK_SCRIPT_UNVERIFIED")
    end = start + dt.timedelta(hours=hours)
    args = subprocess.list2cmdline([
        str(paths[1]), "--root", str(paths[2]),
        "--catalog-dir", str(paths[3]), "--checkpoint-dir", str(paths[4]),
        "--queue-dir", str(paths[5]), "--window-hours", str(hours),
        "--once",
    ])
    doc = ET.Element("{"+NS+"}Task", {"version":"1.3"})
    info = _el(doc, "RegistrationInfo")
    _el(info, "Description", "SMART-MEGA isolated 15h official video queue/quality resident; no media access without authorization")
    triggers = _el(doc, "Triggers")
    trig = _el(triggers, "TimeTrigger")
    _el(trig, "StartBoundary", start.isoformat(timespec="seconds"))
    _el(trig, "EndBoundary", end.isoformat(timespec="seconds"))
    _el(trig, "Enabled", "true")
    repeat = _el(trig, "Repetition")
    _el(repeat, "Interval", f"PT{interval_minutes}M")
    _el(repeat, "Duration", f"PT{hours}H")
    _el(repeat, "StopAtDurationEnd", "true")
    principal = _el(doc, "Principals")
    p = _el(principal, "Principal")
    p.set("id", "Author")
    _el(p, "UserId", user_sid)
    _el(p, "LogonType", "InteractiveToken")
    _el(p, "RunLevel", "LeastPrivilege")
    settings = _el(doc, "Settings")
    _el(settings, "MultipleInstancesPolicy", "IgnoreNew")
    _el(settings, "StartWhenAvailable", "true")
    _el(settings, "DisallowStartIfOnBatteries", "false")
    _el(settings, "StopIfGoingOnBatteries", "false")
    _el(settings, "ExecutionTimeLimit", "PT2M")
    actions = _el(doc, "Actions")
    actions.set("Context", "Author")
    exe = _el(actions, "Exec")
    _el(exe, "Command", str(paths[0]))
    _el(exe, "Arguments", args)
    _el(exe, "WorkingDirectory", str(pathlib.PureWindowsPath(script).parent))
    return ET.tostring(doc, encoding="utf-16", xml_declaration=True)


def register(xml_bytes: bytes, task_name=TASK_NAME) -> dict:
    if os.name != "nt":
        raise OSError("WINDOWS_ONLY")
    existing = subprocess.run(["schtasks.exe","/Query","/TN",task_name,"/XML"],
                              capture_output=True, timeout=20)
    if existing.returncode == 0:
        if ET.canonicalize(existing.stdout.decode("utf-16", "ignore") if existing.stdout.startswith(b"\xff\xfe")
                           else existing.stdout.decode("utf-8", "replace")) == ET.canonicalize(xml_bytes.decode("utf-16")):
            return {"task":task_name,"state":"ALREADY_MATCHING"}
        raise ValueError("TASK_NAME_COLLISION_REVIEW_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="smartmega_scheduled_task_") as d:
        p = pathlib.Path(d) / "task.xml"
        p.write_bytes(xml_bytes)
        created = subprocess.run(["schtasks.exe","/Create","/TN",task_name,"/XML",str(p)],
                                 capture_output=True, timeout=30)
        if created.returncode:
            raise RuntimeError("TASK_REGISTRATION_DENIED_OR_FAILED")
    verify = subprocess.run(["schtasks.exe","/Query","/TN",task_name,"/XML"],
                            capture_output=True, timeout=20)
    if verify.returncode:
        raise RuntimeError("TASK_NOT_READABLE_AFTER_INSTALL")
    root = ET.fromstring(verify.stdout)
    n = {"t":NS}
    cmd = root.findtext(".//t:Actions/t:Exec/t:Command",namespaces=n)
    ours = ET.fromstring(xml_bytes).findtext(".//t:Actions/t:Exec/t:Command",namespaces=n)
    if not cmd or cmd != ours:
        raise RuntimeError("TASK_EXECUTABLE_MISMATCH")
    return {"task":task_name,"state":"REGISTERED_VERIFIED"}


def current_user_sid():
    """Resolve only the current B2 operator identity, never a service account."""
    if os.name != "nt":
        raise OSError("WINDOWS_ONLY")
    result = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"],
                            capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError("TASK_IDENTITY_QUERY_DENIED")
    sid = re.search(r"S-1-\d+(?:-\d+){2,}", result.stdout)
    if sid is None:
        raise RuntimeError("TASK_IDENTITY_UNAVAILABLE")
    return sid.group(0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--python-exe", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--catalog-dir", required=True)
    p.add_argument("--checkpoint-dir", required=True)
    p.add_argument("--queue-dir", required=True)
    p.add_argument("--hours", type=int, default=15)
    p.add_argument("--start-offset-seconds", type=int, default=120)
    p.add_argument("--install", action="store_true")
    args = p.parse_args()
    if not 10 <= args.start_offset_seconds <= 300:
        p.error("start offset must be 10–300s")
    xml = task_xml(args.python_exe, args.script, args.root,
                   args.catalog_dir, args.checkpoint_dir, args.queue_dir,
                   start=dt.datetime.now() + dt.timedelta(seconds=args.start_offset_seconds),
                   hours=args.hours, user_sid=current_user_sid())
    if args.install:
        import json
        print(json.dumps(register(xml),sort_keys=True))
    else:
        sys.stdout.buffer.write(xml)


if __name__ == "__main__":
    main()

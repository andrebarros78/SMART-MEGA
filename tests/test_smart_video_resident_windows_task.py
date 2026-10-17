"""Windows Task Scheduler native XML encoding and 15h bounded triggers."""
import datetime as dt
import xml.etree.ElementTree as ET

import pytest

from smart_video_resident_windows_task import task_xml, NS


def example(**kwargs):
    inputs = dict(
        python_exe=r"C:\Python\python.exe",
        script=r"C:\SMART-MEGA\smart_video_resident_study.py",
        root=r"C:\SMART-MEGA\resident_15h",
        catalog=r"C:\SMART-MEGA\catalog_memory",
        checkpoint=r"C:\SMART-MEGA\real_video_checkpoints",
        queue=r"C:\SMART-MEGA\real_video_queue",
        start=dt.datetime(2026, 10, 17, 16, 30),
        hours=15,
        user_sid="S-1-5-21-100-200-300-1001",
    )
    inputs.update(kwargs)
    return task_xml(**inputs)


def test_windows_task_xml_is_native_utf16_with_matching_declaration():
    b = example()
    assert b.startswith(b"\xff\xfe")
    assert "encoding='utf-16'" in b.decode("utf-16").lower()
    assert ET.fromstring(b).tag.endswith("Task")


def test_finite_repetition_and_no_parallel_instances():
    xml = ET.fromstring(example())
    ns={"t":NS}
    assert xml.findtext(".//t:EndBoundary",namespaces=ns) == "2026-10-18T07:30:00"
    assert xml.findtext(".//t:Repetition/t:Duration",namespaces=ns) == "PT15H"
    assert xml.findtext(".//t:Repetition/t:Interval",namespaces=ns) == "PT5M"
    assert xml.findtext(".//t:MultipleInstancesPolicy",namespaces=ns) == "IgnoreNew"
    assert xml.findtext(".//t:RunLevel",namespaces=ns) == "LeastPrivilege"
    assert xml.findtext(".//t:LogonType",namespaces=ns) == "InteractiveToken"
    assert xml.findtext(".//t:ExecutionTimeLimit",namespaces=ns) == "PT2M"


def test_task_action_points_only_to_isolated_script():
    xml = ET.fromstring(example())
    ns={"t":NS}
    args=xml.findtext(".//t:Exec/t:Arguments",namespaces=ns)
    assert "--once" in args
    assert "smart_video_resident_study.py" in args
    assert "--window-hours 15" in args
    assert "--catalog-dir" in args
    assert "--checkpoint-dir" in args
    assert "--queue-dir" in args
    assert not any(word in args for word in ("cookies", "password", "token", "proxy"))


def test_invalid_duration_rejected():
    with pytest.raises(ValueError,match="HOURS_OUT_OF_RANGE"):
        example(hours=16)
    with pytest.raises(ValueError,match="LOCAL_WALL_CLOCK_REQUIRED"):
        example(start=dt.datetime.now(dt.timezone.utc))


def test_refuse_relative_script_and_queue_collision():
    with pytest.raises(ValueError,match="ABSOLUTE"):
        example(script="relative.py")
    with pytest.raises(ValueError,match="COLLISION"):
        example(root=r"C:\SMART-MEGA\real_video_queue")


def test_requires_real_windows_sid_for_principal():
    xml = ET.fromstring(example())
    n={"t":NS}
    assert xml.findtext('.//t:Principal/t:UserId',namespaces=n)=='S-1-5-21-100-200-300-1001'
    with pytest.raises(ValueError,match='SID_INVALID'):
        example(user_sid='fake-or-blank')

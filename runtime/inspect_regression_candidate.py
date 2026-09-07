import xml.etree.ElementTree as ET
from pathlib import Path
p=Path('SMART_AUDIT_JUNIT_CANDIDATE.xml')
if p.is_file():
    root=ET.parse(p).getroot()
    fails=[]
    for tc in root.iter('testcase'):
        for tag in ('failure','error'):
            node=tc.find(tag)
            if node is not None:
                fails.append((tc.get('classname'),tc.get('name'),tag,node.get('message'),(node.text or '')[:3000]))
    print('FAIL_COUNT',len(fails))
    for row in fails:
        print('\n===FAIL===')
        print(row[0],row[1],row[2])
        print(row[3])
        print(row[4])

from pathlib import Path
p=Path('smart_continuous_red_team.py'); s=p.read_text(encoding='utf-8-sig')
s=s.replace("    fam={'good':'freq','false':'ewma'}\n", "    fam={n:s.family for n,s in states.items()}\n",1)
s=s.replace("    states={'good':SignalQualityState('good','freq'),'false':SignalQualityState('false','ewma')}\n    for _ in range(120):\n        states['good'].update(2); states['false'].update(0)\n", "    states={'good':SignalQualityState('good','freq'),'false':SignalQualityState('false','ewma'),\n            'neutral':SignalQualityState('neutral','neutral')}\n    for _ in range(120):\n        states['good'].update(2); states['false'].update(0); states['neutral'].update(1)\n",1)
s=s.replace("    for _ in range(180):\n        states['good'].update(1); states['false'].update(2)\n", "    for _ in range(180):\n        states['good'].update(1); states['false'].update(2); states['neutral'].update(1)\n",1)
p.write_text(s,encoding='utf-8')

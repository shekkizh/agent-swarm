"""Read-only observation of a running experiment; sends no agent messages."""
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agent_swarm.backend import attach_vercel
run = Path(sys.argv[1])
if (run/'summary.json').exists():
    print((run/'summary.json').read_text())
    raise SystemExit(0)
live = json.loads((run/'live.json').read_text())
sb = attach_vercel(live['sandbox_id'])
script = '''import json
from pathlib import Path
p=Path('/private-run/events.jsonl')
events=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
print(json.dumps({'operations': len(events), 'events': [e for e in events if e['op'] == 'post' or (e['op'] in ['candidate','approve','publish'] and 'error' not in e['result'])][-12:]}, indent=2))
for name in ['kestrel','mica','rowan']:
 p=Path('/private-run/'+name+'-output.txt')
 print(name, p.read_text()[-1800:] if p.exists() else 'not launched')
 home=Path('/home')/name/'.zcode'
 logs=list(home.rglob('*.jsonl'))
 print('native logs:', [(str(x.relative_to(home)), x.stat().st_size) for x in logs][-4:])
'''
r = sb.exec(['python3','-c',script])
print(r.stdout+r.stderr)

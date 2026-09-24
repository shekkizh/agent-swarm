"""Read-only snapshot of a specific Modal sandbox, including authoritative poll."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from agent_swarm.backend import load_environment
import modal

load_environment()
run=Path(sys.argv[1])
summary=json.loads((run/'summary.json').read_text())
sb=modal.Sandbox.from_id(summary['sandbox_id'])
print('Sandbox poll (None means running):',sb.poll(),flush=True)
code='''import json,pathlib
root=pathlib.Path('/private-run')
for p in root.glob('*-exit.json'): print(p.name,p.read_text())
p=root/'events.jsonl'
if p.exists():
 events=[json.loads(l) for l in p.read_text().splitlines()]
 print('Service events:',len(events))
 for e in events[-12:]:
  print(e['seq'],e['author'],e['op'],json.dumps(e['data'] if e['op']=='post' else e['result'])[:1600])
for home in pathlib.Path('/home').iterdir():
 paths=list((home/'.zcode/cli/rollout').glob('model-io*.jsonl'))
 for p in paths:
  lines=p.read_text().splitlines()
  if not lines: continue
  try: r=json.loads(lines[-1])
  except ValueError: continue
  response=r.get('response') or {}
  print(home.name,'last roundtrip',r.get('completedAt'), 'calls',json.dumps(response.get('toolCalls',[]))[:1600])
'''
p=sb.exec('python3','-c',code,timeout=30)
print(p.stdout.read())
print(p.stderr.read())
print('Inspection exit:',p.wait())

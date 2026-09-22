"""Produce a factual report from preserved logs, without invoking a model."""
import json
from datetime import datetime
from pathlib import Path
import sys
import tarfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent_swarm.traces import iter_sessions

run = Path(sys.argv[1]).resolve()
summary = json.loads((run/'summary.json').read_text())
files = {}
if (run/'service-artifacts.tar.gz').exists():
    with tarfile.open(run/'service-artifacts.tar.gz') as tar:
        files = {m.name.removeprefix('./'): tar.extractfile(m).read().decode()
                 for m in tar.getmembers() if m.isfile()}
events = [json.loads(line) for line in files.get('events.jsonl', '').splitlines()]
state = json.loads(files.get('state.json', '{}'))
exits = {name: json.loads(files[name+'-exit.json']) if name+'-exit.json' in files else None
         for name in summary['agents']}
models = {}
trace_errors = []
for identity, session, records in iter_sessions(run):
    seen = {tuple(pair) for pair in models.get(identity, [])}
    for record in records:
        if record.error:
            trace_errors.append({'agent': identity, 'session': session, 'error': record.error})
            continue
        if not isinstance(record.value, dict):
            continue
        model = record.value.get('model', {})
        seen.add((model.get('providerId'), model.get('modelId')))
    models[identity] = sorted(seen, key=str)
start = datetime.fromisoformat(summary['started_at']).timestamp() if summary.get('started_at') else 0
lines = ['# Cedar run observations', '', f"Run: `{run.name}`",
         f"Sandbox: `{summary.get('sandbox_id')}`", f"Status: `{summary['status']}`",
         f"Accepted publication: **{'yes' if state.get('release') else 'no'}**", '',
         f"Malformed trace records: {len(trace_errors)} (raw records remain available in the trace viewer).", '',
         '## Agent activity', '', '| Account | Observed model | Board posts | Board reads | Exit |',
         '|---|---|---:|---:|---|']
for name in summary['agents']:
    own = [e for e in events if e['author']==name]
    model = ', '.join('/'.join(str(x) for x in pair) for pair in models.get(name, [])) or 'unobserved'
    lines.append(f"| {name} | {model} | {sum(e['op']=='post' for e in own)} | {sum(e['op']=='read' for e in own)} | {exits[name]} |")
lines += ['', '## Board and release timeline', '',
          'Times below are seconds after agent launch began.']
for e in events:
    if e['op'] == 'post':
        lines += ['', f"- +{e['time']-start:.1f}s **{e['author']}** posted: {e['data']}"]
    elif e['op'] in ['candidate','approve','publish'] and 'error' not in e['result']:
        lines += ['', f"- +{e['time']-start:.1f}s **{e['author']}** completed `{e['op']}`: `{json.dumps(e['result'])}`"]
lines += ['', '## Interpretation limits', '',
          'The task briefs did not disclose peers or instruct coordination. The installed workplace CLI exposed board operations through help. No messages or follow-up instructions were injected by the experiment runner. Business permissions enforce the release order. This single run measures behavior in this environment; it does not establish general coordination ability. Infrastructure-interrupted runs are not evidence of task failure.', '',
          f"Receipt: `{(state.get('release') or {}).get('receipt', 'none')}`. Full state is saved in `state.json` and `observations.json`.", '']
(run/'REPORT.md').write_text('\n'.join(lines))
(run/'observations.json').write_text(json.dumps({'models':models,'exits':exits,'state':state,'events':events,'trace_errors':trace_errors}, indent=2))
print(run/'REPORT.md')

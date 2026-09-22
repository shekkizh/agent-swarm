"""Reusable detached launch, completion polling, and artifact collection."""
import json
from pathlib import Path
import re
import time


def check(proc):
    if not proc.ok:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc


def worker_source():
    return Path(__file__).with_name('worker.py').read_text()


def launch_agents(sb, names, first_uid=11001):
    if not names or len(set(names)) != len(names) or any(not re.fullmatch(r'[a-z][a-z0-9_-]*', n) for n in names):
        raise ValueError('Agent names must be unique, nonempty lowercase identifiers')
    # JSON is passed as an argv value, never interpolated into shell code.
    script = '''import json, subprocess, sys
for uid,name in enumerate(json.loads(sys.argv[1]),int(sys.argv[2])):
 with open('/private-run/'+name+'-launcher.txt','w') as f:
  subprocess.Popen(['python3','/root/launch.py',name,str(uid)],stdin=subprocess.DEVNULL,
                   stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
'''
    check(sb.exec(['python3', '-c', script, json.dumps(names), str(first_uid)]))


def wait_agents(sb, count, limit, poll_seconds=10):
    deadline = time.monotonic()+limit+45
    seen = set()
    while time.monotonic() < deadline:
        raw = check(sb.exec(['python3', '-c', "import json,pathlib; print(json.dumps({p.name:json.loads(p.read_text()) for p in pathlib.Path('/private-run').glob('*-exit.json')}))"])).stdout
        exits = json.loads(raw)
        for name in exits.keys()-seen:
            print(name, exits[name], flush=True)
        seen.update(exits)
        if len(exits) == count:
            return exits
        time.sleep(poll_seconds)
    raise TimeoutError('Agent supervisor did not report completion')


def collect(sb, out, summary):
    for remote, filename in [('/private-run','service-artifacts.tar.gz'),('/workspaces','workspaces.tar.gz'),('/home','agent-homes.tar.gz')]:
        try:
            sb.export_directory(remote, out/filename)
        except Exception as exc:
            summary.setdefault('collection_errors', []).append(str(exc))
    try:
        sb.stop()
        # The backend stop method is best effort; do not claim API confirmation.
        summary['sandbox_stop_requested'] = True
    except Exception as exc:
        summary['cleanup_error'] = str(exc)

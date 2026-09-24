"""Detached sequential trial supervisor. Never changes the experimental model."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    os.replace(temporary, path)


def classify(summary, metrics, returncode, log):
    if metrics.get('rate_limited_agents') or any(s in log.lower() for s in ('rate limit', 'responseStatus: 429'.lower(), 'too many requests')):
        return 'rate_limited'
    if returncode or summary.get('status') != 'completed':
        return 'execution_errors'
    if not metrics.get('evidence_complete'):
        return 'incomplete_evidence'
    return 'usable'  # Wrong answers, refusals and clean timeouts are valid outcomes.


def backoff(reason, attempt):
    return min(1800 * 2**(attempt-1), 14400) if reason == 'rate_limited' else min(300 * 2**(attempt-1), 3600)


def ensure_terminal(summary):
    if not summary.get('sandbox_id'):
        return {'sandbox_id': None, 'note': 'No sandbox ID recorded'}
    import modal
    sb = modal.Sandbox.from_id(summary['sandbox_id'])
    result = sb.poll()
    if result is None:
        sb.terminate()
        result = sb.poll()
    if result is None:
        raise RuntimeError('Sandbox still running; refusing to start another trial')
    return {'sandbox_id': summary['sandbox_id'], 'poll': result}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-attempts',type=int,default=5)
    p.add_argument('--limit',type=int,default=540)
    p.add_argument('--between-trials',type=int,default=120)
    a=p.parse_args()
    if a.max_attempts < 1: p.error('max-attempts must be positive')
    root=ROOT/'runs/coordination_authority'
    lock=(root/'resilient_queue.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    directory=a.output.resolve();directory.mkdir(parents=True,exist_ok=False)
    plan=json.loads(a.plan.read_text())
    from experiments.coordination_authority.design import CONDITIONS
    assert all(j['condition'] in CONDITIONS and isinstance(j['repeat'],int) for j in plan['jobs'])
    manifest=dict(created_at=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),status='running',
        max_attempts=a.max_attempts,limit=a.limit,between_trials_seconds=a.between_trials,
        model_policy='Same model and condition on every retry; live agents within a trial remain concurrent.',
        jobs=[dict(**j,status='pending',attempts=[]) for j in plan['jobs']])
    path=directory/'queue.json'
    def checkpoint():save(path,manifest)
    def wait(seconds):
        manifest['next_attempt_at']=datetime.fromtimestamp(time.time()+seconds,timezone.utc).isoformat()
        checkpoint()
        time.sleep(seconds)
        manifest.pop('next_attempt_at',None)
    checkpoint()
    from agent_swarm.backend import load_environment
    load_environment()
    try:
        for index,job in enumerate(manifest['jobs']):
            for attempt in range(1,a.max_attempts+1):
                output=directory/f"{index:03d}-{job['condition']}-r{job['repeat']}-attempt{attempt}"
                logpath=directory/f'{index:03d}-attempt{attempt}.log'
                record=dict(number=attempt,output=str(output),log=str(logpath),status='running')
                job['attempts'].append(record);job['status']='running';manifest['current_job']=index;manifest['status']='running';checkpoint()
                print(f"Starting {job['condition']} r{job['repeat']} attempt {attempt}",flush=True)
                with logpath.open('w') as log:
                    child=subprocess.Popen([sys.executable,str(HERE/'run.py'),job['condition'],'--repeat',str(job['repeat']),
                        '--limit',str(a.limit),'--output',str(output)],stdout=log,stderr=subprocess.STDOUT)
                    record['pid']=child.pid;checkpoint();returncode=child.wait()
                summary=json.loads((output/'summary.json').read_text()) if (output/'summary.json').exists() else {}
                metrics=json.loads((output/'metrics.json').read_text()) if (output/'metrics.json').exists() else {}
                reason=classify(summary,metrics,returncode,logpath.read_text())
                record.update(status=reason,exit_code=returncode,finished_at=datetime.now(timezone.utc).isoformat())
                # Never launch a replacement while the preceding sandbox could still run.
                record['terminal_check']=ensure_terminal(summary)
                if reason != 'usable' and output.exists():
                    destination=root/'failed_runs'/reason/directory.name/output.name
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.move(str(output),str(destination));record['original_output']=str(output);record['output']=str(destination)
                checkpoint()
                subprocess.run([sys.executable,str(HERE/'summarize.py'),str(root)],check=True,stdout=subprocess.DEVNULL)
                print(f"Finished: {reason}",flush=True)
                if reason=='usable':
                    job['status']='finished';checkpoint()
                    break
                if attempt==a.max_attempts:
                    job['status']='exhausted';manifest['status']='stopped_retry_budget';checkpoint();return
                delay=backoff(reason,attempt)
                job['status']='cooldown';manifest['status']='cooldown'
                print(f'Cooldown {delay} seconds before retry',flush=True);wait(delay)
            if index+1<len(manifest['jobs']):
                manifest['status']='between_trials';wait(a.between_trials)
        manifest['status']='completed';manifest['finished_at']=datetime.now(timezone.utc).isoformat();checkpoint()
    except BaseException as exc:
        manifest['status']='stopped_error';manifest['error']=type(exc).__name__+': '+str(exc);checkpoint();raise


if __name__=='__main__': main()

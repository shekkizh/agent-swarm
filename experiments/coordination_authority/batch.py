"""Bounded sequential study queue, with resumable manifests and subprocess logs."""
import argparse
from datetime import datetime, timezone
import json
import random
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from experiments.coordination_authority.design import CONDITIONS

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--conditions',nargs='+',choices=CONDITIONS)
    p.add_argument('--repeats',type=int,default=1)
    p.add_argument('--start-repeat',type=int,default=0)
    p.add_argument('--limit',type=int,default=540)
    p.add_argument('--resume',type=Path)
    p.add_argument('--shuffle-seed',type=int)
    p.add_argument('--stop-on-rate-limit',action='store_true',default=True)
    a=p.parse_args()
    if not a.resume and not a.conditions:
        p.error("New batches require explicit --conditions")
    if a.resume:
        directory=a.resume.resolve()
        manifest=json.loads((directory/'queue.json').read_text())
        if manifest.get('hold_reason'):
            raise SystemExit(manifest['hold_reason'])
        if manifest.get('superseded_by'):
            raise SystemExit('This queue was superseded by '+manifest['superseded_by'])
    else:
        directory=ROOT/'runs'/'coordination_authority'/'batches'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        directory.mkdir(parents=True)
        manifest=dict(created_at=datetime.now(timezone.utc).isoformat(),limit=a.limit,stop_on_rate_limit=a.stop_on_rate_limit,jobs=[
            dict(condition=c,repeat=r,status='pending') for r in range(a.start_repeat,a.start_repeat+a.repeats) for c in a.conditions])
        if a.shuffle_seed is not None:
            manifest['shuffle_seed']=a.shuffle_seed
            random.Random(a.shuffle_seed).shuffle(manifest['jobs'])
    def save(): (directory/'queue.json').write_text(json.dumps(manifest,indent=2))
    save()
    print('Queue:',directory,flush=True)
    for index,job in enumerate(manifest['jobs']):
        if job['status']=='finished': continue
        if job['status']=='running':
            raise SystemExit('Queue contains a running job. Inspect its process and sandbox before changing the manifest.')
        output=directory/f"{index:03d}-{job['condition']}-r{job['repeat']}"
        job.update(status='running',output=str(output))
        save()
        print('Starting',job['condition'],job['repeat'],flush=True)
        with (directory/f'{index:03d}.log').open('w') as log:
            process=subprocess.Popen([sys.executable,str(HERE/'run.py'),job['condition'],'--repeat',str(job['repeat']),
                '--limit',str(manifest['limit']),'--output',str(output)],stdout=log,stderr=subprocess.STDOUT)
            job['pid']=process.pid
            save()
            job['exit_code']=process.wait()
        job['status']='finished'
        save()
        if (output/'metrics.json').exists():
            metrics=json.loads((output/'metrics.json').read_text())
            print(json.dumps({k:metrics.get(k) for k in ['condition','repeat','status','correct_publication','board_posts',
                'successful_actors','rate_limited_agents','evidence_complete','incorrect_structured_attempts']}),flush=True)
        if job['exit_code'] or not (output/'summary.json').exists():
            raise SystemExit('Job failed at runner level; inspect before resuming.')
        summary=json.loads((output/'summary.json').read_text())
        if summary['status'] in ['infra_error','agent_error']:
            raise SystemExit('Infrastructure/agent failure; queue stopped for inspection.')
        if manifest.get('stop_on_rate_limit') and metrics.get('rate_limited_agents'):
            raise SystemExit('Provider throttling detected; queue stopped for inspection.')
    print('Queue complete',directory,flush=True)

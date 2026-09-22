"""Uploaded supervisor for one isolated ZCode process (root-only configuration)."""
import json, os, subprocess, sys
from pathlib import Path
name, uid = sys.argv[1], int(sys.argv[2])
config = json.loads(Path('/root/launch.json').read_text())
env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/home/'+name,
       'ZCODE_MODEL': 'zai-coding-plan/'+config['model'],
       'ZCODE_API_KEY': config['api_key'], 'ZHIPU_API_KEY': config['api_key'],
       'ZCODE_BASE_URL': 'https://api.z.ai/api/anthropic',
       'ANTHROPIC_BASE_URL': 'https://api.z.ai/api/anthropic',
       'ANTHROPIC_API_KEY': config['api_key']}
cmd = ['setpriv', '--reuid='+str(uid), '--regid='+str(uid), '--clear-groups',
       '--no-new-privs', '--bounding-set=-all', '--inh-caps=-all', '--ambient-caps=-all',
       'node', '/agent/zcode.cjs', '--prompt', config['prompt'], '--no-color']
with open('/private-run/'+name+'-output.txt', 'w') as f:
    p = subprocess.Popen(cmd, cwd='/workspaces/'+name, env=env, stdout=f, stderr=subprocess.STDOUT,
                         start_new_session=True, umask=0o077)
    try:
        code = p.wait(timeout=config['limit'])
    except subprocess.TimeoutExpired:
        import signal
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        code = 124
Path('/private-run/'+name+'-exit.json').write_text(json.dumps({'exit_code': code}))
print(name, 'exited', code, flush=True)

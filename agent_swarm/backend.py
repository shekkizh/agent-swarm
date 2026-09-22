"""Single integration point for the sibling minimal-eval source checkout."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MINIEVAL_ROOT = Path(os.environ.get('MINIEVAL_ROOT', ROOT.parent / 'minimal-eval')).expanduser().resolve()
if not (MINIEVAL_ROOT / 'minieval/sandbox.py').is_file():
    raise RuntimeError('Set MINIEVAL_ROOT to the minimal-eval checkout (default: ../minimal-eval)')
# Keep the calling project first so experiment names cannot be shadowed.
sys.path.insert(1, str(MINIEVAL_ROOT))
from minieval.env import load_env
from minieval.sandbox import create_sandbox, VercelSandbox
from minieval.dependencies import install_dependencies


def load_environment():
    # Existing shell values win; this project's .env precedes the shared fallback.
    load_env(ROOT)
    load_env(MINIEVAL_ROOT)
    if not os.getenv('VERCEL_TOKEN'):
        auth = Path.home() / 'Library/Application Support/com.vercel.cli/auth.json'
        if auth.exists():
            os.environ['VERCEL_TOKEN'] = json.loads(auth.read_text())['token']


def zai_key():
    if os.getenv('ZAI_CODING_PLAN_API_KEY'):
        return os.environ['ZAI_CODING_PLAN_API_KEY']
    path = Path.home() / '.zcode/v2/provider_config.json'
    rules = json.loads(path.read_text())['config']['providerConfigRules']['providerRules']
    return next(r['config']['access']['apiKey'] for r in rules if r['providerId'] == 'zai-api')


def zcode_files():
    return MINIEVAL_ROOT / 'agents/zcode'


def attach_vercel(sandbox_id):
    """Read an existing session without creating another sandbox.

    minimal-eval currently has no public attach API; contain that coupling here.
    """
    load_environment()
    sb = object.__new__(VercelSandbox)
    sb._token = os.environ['VERCEL_TOKEN']
    sb._team_id = os.getenv('VERCEL_TEAM_ID')
    sb._project_id = os.getenv('VERCEL_PROJECT_ID')
    sb._session_id = sandbox_id
    sb.workdir = '/'
    return sb

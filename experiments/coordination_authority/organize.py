"""Move unusable attempts, preserving raw artifacts and an explicit relocation index."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'runs/coordination_authority'


def category(summary, metrics):
    if summary.get('status') in ('infra_error', 'agent_error'):
        return 'execution_errors'
    if metrics.get('rate_limited_agents'):
        return 'rate_limited'
    if not metrics.get('evidence_complete'):
        return 'incomplete_evidence'
    return None


def organize(apply=False):
    index_path = RUNS / 'relocations.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    moves = []
    for path in sorted(RUNS.rglob('summary.json')):
        if 'failed_runs' in path.relative_to(RUNS).parts:
            continue
        summary = json.loads(path.read_text())
        if not summary.get('finished_at'):
            continue
        mp = path.parent / 'metrics.json'
        metrics = json.loads(mp.read_text()) if mp.exists() else {}
        reason = category(summary, metrics)
        if reason:
            dest = RUNS / 'failed_runs' / reason / path.parent.relative_to(RUNS)
            moves.append(dict(old=str(path.parent), new=str(dest), reason=reason))
    if apply:
        for move in moves:
            dest = Path(move['new'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise FileExistsError(dest)
            shutil.move(move['old'], dest)
        index += moves
        # Update navigation/queue metadata only; frozen inputs and native evidence remain intact.
        refs = list((ROOT/'experiments/coordination_authority').glob('*.md'))
        refs += list(RUNS.rglob('queue.json'))
        refs += [RUNS/'OPERATOR_STATE.json']
        for path in refs:
            if not path.exists():
                continue
            original = path.read_text()
            updated = original
            for move in moves:
                updated = updated.replace(move['old'], move['new'])
                updated = updated.replace(str(Path(move['old']).relative_to(ROOT)), str(Path(move['new']).relative_to(ROOT)))
            if updated != original:
                path.write_text(updated)
        index_path.write_text(json.dumps(index, indent=2)+'\n')
    print(json.dumps({'apply':apply,'moves':moves}, indent=2))

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--apply',action='store_true')
    organize(p.parse_args().apply)

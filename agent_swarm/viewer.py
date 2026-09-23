"""Read-only, loopback-only browser for complete recorded agent roundtrips."""
from __future__ import annotations

import argparse
import tarfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .traces import e, iter_sessions, page, render_session, safe_path
from .viewer_ui import card, listing_page, run_summary


def is_run(path: Path) -> bool:
    return ((path / 'agent-homes.tar.gz').is_file() or (path / 'agent_data').is_dir()
            or (path / 'summary.json').is_file())


def discover_runs(root: Path) -> list[Path]:
    """Inspect at most three directory levels, never walk agent homes/logs.

    Pass a narrower --runs path for deeper archived trees. No tar contents are
    read merely to list runs; symlink directories are not followed.
    """
    result = []
    pending = [(root, 0)]
    while pending:
        path, depth = pending.pop()
        if is_run(path):
            result.append(path)
        elif depth < 3:
            for child in path.iterdir():
                if child.is_dir() and not child.is_symlink() and child.name not in {
                    '.git', '.venv', 'node_modules', '__pycache__', 'agent_data', 'shared',
                }:
                    pending.append((child, depth + 1))
    return sorted(result)


def url(route: str, **query: str) -> str:
    return route + '?' + urlencode(query)


def handler_for(root: Path):
    root = root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                route = urlsplit(self.path)
                query = parse_qs(route.query)
                if route.path == '/agent-trace.html':
                    content = Path(__file__).with_name('agent-trace.html').read_text(encoding='utf-8')
                elif route.path == '/':
                    rows = []
                    for run in reversed(discover_runs(root)):
                        relative = str(run.relative_to(root))
                        summary = run_summary(run)
                        passed = summary.get('passed')
                        status = ('Passed' if passed is True else 'Failed' if passed is False
                                  else str(summary.get('status', 'Recorded')).replace('_', ' ').title())
                        agents = summary.get('agents', [])
                        metadata = [str(summary.get('model', 'Model not recorded')),
                                    str(summary.get('started_at', 'Start time not recorded'))]
                        if isinstance(agents, list) and agents:
                            metadata.append('Agents: ' + ', '.join(str(agent) for agent in agents))
                        rows.append(card(url('/run', path=relative), run.name,
                                         str(run.parent.relative_to(root)) if run != root else 'Run',
                                         status, metadata, 'View sessions',
                                         'passed' if passed is True else 'failed' if passed is False or status == 'Infra Error' else ''))
                    content = listing_page('Runs', 'Explore agent conversations, tool calls, and complete execution records.', rows)
                elif route.path in {'/run', '/session', '/roundtrips', '/raw'}:
                    relative = query.get('path', ['.'])[0]
                    run = safe_path(root, relative)
                    if not run.is_dir() or not is_run(run):
                        self.send_error(404, 'No such run')
                        return
                    if route.path == '/run':
                        rows = []
                        for agent, name, records in iter_sessions(run):
                            target = url('/session', path=relative, agent=agent, name=name)
                            malformed = sum(bool(record.error) for record in records)
                            rows.append(card(target, agent, 'Agent session',
                                             f'{malformed} malformed' if malformed else '',
                                             [name, f'{len(records)} recorded roundtrips'],
                                             'Open conversation', 'failed' if malformed else 'passed'))
                        content = listing_page(run.name, relative, rows, back=True)
                    else:
                        wanted = (query.get('agent', [''])[0], query.get('name', [''])[0])
                        session = next((s for s in iter_sessions(run) if s[:2] == wanted), None)
                        if session is None:
                            self.send_error(404, 'No such session')
                            return
                        agent, name, records = session
                        if route.path == '/raw':
                            self.respond(b''.join(r.raw_bytes for r in records), 'application/octet-stream', download=True)
                            return
                        if route.path == '/session':
                            content = Path(__file__).with_name('agent-trace.html').read_text(encoding='utf-8')
                            self.respond(content.encode('utf-8'), 'text/html; charset=utf-8')
                            return
                        back = url('/run', path=relative)
                        raw = url('/raw', path=relative, agent=agent, name=name)
                        content = page(f'{agent}: {name}', f'<p><a href="{e(back)}">Run</a> · '
                                       f'<a href="{e(url("/session", path=relative, agent=agent, name=name))}">Conversation</a> · '
                                       f'<a href="{e(raw)}">Download original JSONL</a></p>' + render_session(records))
                else:
                    self.send_error(404)
                    return
                self.respond(content.encode('utf-8'), 'text/html; charset=utf-8')
            except (OSError, ValueError, tarfile.TarError) as exc:
                self.send_error(400, str(exc))

        def respond(self, data: bytes, content_type: str, download: bool = False):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="trace.jsonl"')
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=Path('runs'))
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if not args.runs.is_dir():
        parser.error(f'Runs directory does not exist: {args.runs}')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(args.runs))
    print(f'Viewing {args.runs.resolve()} at http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

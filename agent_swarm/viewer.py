"""Read-only, loopback-only browser for complete recorded agent roundtrips."""
from __future__ import annotations

import argparse
import tarfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .traces import e, iter_sessions, page, render_session, safe_path


def is_run(path: Path) -> bool:
    return (path / 'agent-homes.tar.gz').is_file() or (path / 'agent_data').is_dir()


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
                if route.path == '/':
                    rows = []
                    for run in discover_runs(root):
                        relative = str(run.relative_to(root))
                        rows.append(f'<li><a href="{e(url("/run", path=relative))}">{e(relative)}</a></li>')
                    content = page('Agent swarm runs', f'<p>Root: {e(root)}</p><ul>{"".join(rows)}</ul>'
                                   '<p>Discovery is limited to three levels. Use --runs for deeper archive directories.</p>')
                elif route.path in {'/run', '/session', '/raw'}:
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
                            rows.append(f'<li><a href="{e(target)}">{e(agent)} · {e(name)}</a> · '
                                        f'{len(records)} records · {malformed} malformed</li>')
                        content = page(relative, '<p><a href="/">All runs</a></p><ul>' + ''.join(rows) + '</ul>')
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
                        back = url('/run', path=relative)
                        raw = url('/raw', path=relative, agent=agent, name=name)
                        content = page(f'{agent}: {name}', f'<p><a href="{e(back)}">Run</a> · '
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
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
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

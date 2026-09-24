"""Complete ZCode model-I/O roundtrips, without transcript reconstruction.

The roundtrip presentation is inspired by the former agent-swarm/viewer/server.py.
Unlike that viewer, modern request.body records, raw lines, malformed records and
unbounded tool arguments/results are retained. Repeated request histories are
intentional: the recorded evidence is authoritative, not a merged conversation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import html
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import Iterable


@dataclass
class TraceRecord:
    source: str
    line_number: int
    raw_bytes: bytes
    value: object = None
    error: str | None = None

    @property
    def raw(self) -> str:
        return self.raw_bytes.decode('utf-8', errors='replace')


def read_records(lines: Iterable[bytes], source: str) -> list[TraceRecord]:
    records = []
    for number, line in enumerate(lines, 1):
        record = TraceRecord(source, number, line)
        try:
            record.value = json.loads(line)
            if not isinstance(record.value, dict):
                record.error = 'Expected a JSON object; original value retained below'
        except (ValueError, UnicodeError) as exc:
            record.error = str(exc)
        records.append(record)
    return records


def safe_path(root: Path, relative: str) -> Path:
    """Resolve only descendants; protects viewer and legacy trace symlinks."""
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Path is outside the selected runs directory')
    return path


def iter_sessions(run: Path):
    """Yield (agent, session name, records) from archive and/or legacy files.

    Archive members are streamed, never extracted. Duplicate archive/filesystem
    sessions are retained and distinguished by source in the session name.
    """
    run = run.resolve()
    archive = safe_path(run, 'agent-homes.tar.gz')
    if archive.is_file():
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                parts = PurePosixPath(member.name).parts
                if (member.isfile() and len(parts) == 5
                        and parts[1:4] == ('.zcode', 'cli', 'rollout')
                        and parts[0] not in ('.', '..')
                        and parts[-1].startswith('model-io') and parts[-1].endswith('.jsonl')):
                    stream = tar.extractfile(member)
                    if stream is not None:
                        with stream:
                            yield parts[0], 'archive/' + parts[-1], read_records(stream, member.name)
    data = safe_path(run, 'agent_data')
    if data.is_dir():
        for agent in sorted(data.iterdir()):
            if agent.is_symlink() or not agent.is_dir():
                continue
            rollout = safe_path(run, str(agent.relative_to(run) / 'cli' / 'rollout'))
            for source in sorted(rollout.glob('model-io*.jsonl')):
                source = safe_path(run, str(source.relative_to(run)))
                with source.open('rb') as stream:
                    yield agent.name, 'files/' + source.name, read_records(stream, str(source.relative_to(run)))


def e(value: object) -> str:
    return html.escape(str(value))


def pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def request_parts(record: dict) -> tuple[object, object, object]:
    request = record.get('request') or {}
    if not isinstance(request, dict):
        return None, [], record.get('messageOffset')
    body = request.get('body')
    if not isinstance(body, dict):
        body = request
    # Native logs can keep provider metadata in body and conversation tails beside it.
    return (body.get('system', request.get('system')), body.get('messages', request.get('messages', [])),
            record.get('messageOffset', request.get('messageOffset', body.get('messageOffset'))))


def render_session(records: list[TraceRecord]) -> str:
    parts = ['<p>Every recorded roundtrip is shown in source order. Request histories may repeat; '
             'offsets are displayed without inferring missing history. Expand raw records for all metadata. '
             'No text is truncated. Raw JSONL download/export preserves original bytes.</p>']
    for index, record in enumerate(records, 1):
        parts.append(f'<section id="roundtrip-{index}"><h2>Roundtrip {index}</h2>'
                     f'<p>{e(record.source)} · line {record.line_number}</p>')
        if record.error:
            parts.append(f'<p class="error">Malformed record: {e(record.error)}</p>')
        if isinstance(record.value, dict):
            value = record.value
            system, messages, offset = request_parts(value)
            parts.append(f'<p>Message offset: {e(offset)} · duration (ms): {e(value.get("durationMs"))}</p>')
            if system is not None:
                parts.append(f'<details><summary>System instructions</summary><pre>{e(pretty(system))}</pre></details>')
            parts.append(f'<h3>Request messages</h3><pre>{e(pretty(messages))}</pre>')
            response = value.get('response')
            if isinstance(response, dict) and isinstance(response.get('text'), str):
                parts.append(f'<h3>Assistant text</h3><pre>{e(response["text"])}</pre>')
            parts.append(f'<h3>Complete response</h3><pre>{e(pretty(response))}</pre>')
            if 'error' in value:
                parts.append(f'<h3>Error</h3><pre>{e(pretty(value["error"]))}</pre>')
        parts.append(f'<details{" open" if record.error else ""}><summary>Complete raw record</summary>'
                     f'<pre>{e(record.raw)}</pre></details></section>')
    return ''.join(parts)


def page(title: str, body: str) -> str:
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{e(title)}</title><style>body{{font:15px system-ui;margin:2rem auto;max-width:1100px;padding:0 1rem;'
            'background:#111827;color:#e5e7eb}a{color:#93c5fd}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
            'background:#1f2937;padding:1rem}section{border-top:1px solid #6b7280;margin:2rem 0}'
            '.error{color:#fca5a5}summary{cursor:pointer}</style></head>'
            f'<body><h1>{e(title)}</h1>{body}</body></html>')


def export_run(run: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    links = []
    for index, (agent, name, records) in enumerate(iter_sessions(run), 1):
        slug = re.sub(r'[^a-zA-Z0-9_.-]', '_', agent)
        basename = f'{index:03d}-{slug}'
        (output / f'{basename}.jsonl').write_bytes(b''.join(r.raw_bytes for r in records))
        (output / f'{basename}.html').write_text(page(f'{agent}: {name}', render_session(records)), encoding='utf-8')
        links.append(f'<li><a href="{basename}.html">{e(agent)} · {e(name)}</a> '
                     f'({len(records)} records) · <a href="{basename}.jsonl">raw JSONL</a></li>')
    (output / 'index.html').write_text(page(run.name, '<ul>' + ''.join(links) + '</ul>'), encoding='utf-8')
    return len(links)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    count = export_run(args.run, args.output)
    print(f'Exported {count} complete sessions to {args.output / "index.html"}')


if __name__ == '__main__':
    main()

import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

from agent_swarm.traces import export_run, iter_sessions, read_records, render_session, request_parts, safe_path
from agent_swarm.viewer import discover_runs


class TraceTests(unittest.TestCase):
    def test_body_metadata_with_sibling_conversation_tail(self):
        messages = [{'role': 'tool', 'content': 'shared file updated successfully'}]
        value = {'request': {'body': {'system': ['SYSTEM'], 'model': 'example'},
                             'messages': messages, 'messageOffset': 17, 'messagesKind': 'tail'}}
        self.assertEqual(request_parts(value), (['SYSTEM'], messages, 17))
        records = read_records(io.BytesIO(json.dumps(value).encode() + b'\n'), 'test')
        shown = render_session(records).split('<h3>Request messages</h3>', 1)[1].split('<details', 1)[0]
        self.assertIn('shared file updated successfully', shown)
        # An explicitly empty provider conversation must not be replaced by sibling data.
        value['request']['body']['messages'] = []
        self.assertEqual(request_parts(value)[1], [])

    def test_complete_modern_and_legacy_records(self):
        long = 'tool result ' * 2000 + '<script>END</script>'
        values = [
            {'request': {'body': {'system': ['SYSTEM'], 'messages': [{'role': 'tool', 'content': long}]}},
             'response': {'toolCalls': [{'name': 'shell', 'input': {'command': long}}], 'body': {'text': 'BODY_END'}}},
            {'messageOffset': 5, 'request': {'messages': [{'role': 'user', 'content': 'legacy'}]},
             'response': {'text': 'FINAL_RESPONSE_END'}},
        ]
        raw = b''.join(json.dumps(v).encode() + b'\n' for v in values)
        records = read_records(io.BytesIO(raw), 'test')
        output = render_session(records)
        self.assertIn(long.replace('<', '&lt;').replace('>', '&gt;'), output)
        self.assertNotIn('<script>', output)
        self.assertIn('FINAL_RESPONSE_END', output)
        self.assertIn('BODY_END', output)
        self.assertEqual(request_parts(values[1])[2], 5)
        self.assertEqual(b''.join(r.raw_bytes for r in records), raw)

    def test_malformed_and_blank_lines_are_visible(self):
        records = read_records(io.BytesIO(b'{broken\n\n42\n'), 'source')
        self.assertEqual(len(records), 3)
        self.assertTrue(all(r.error for r in records))
        self.assertIn('{broken', render_session(records))
        self.assertIn('Malformed record', render_session(records))

    def test_archive_legacy_export_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / 'experiment' / 'runs' / 'one'
            run.mkdir(parents=True)
            raw = b'{"response":{"text":"LAST"}}\n'
            with tarfile.open(run / 'agent-homes.tar.gz', 'w:gz') as tar:
                for name in ['./alpha/.zcode/cli/rollout/model-io-a.jsonl', '../evil/.zcode/cli/rollout/model-io-a.jsonl']:
                    info = tarfile.TarInfo(name)
                    info.size = len(raw)
                    tar.addfile(info, io.BytesIO(raw))
            legacy = run / 'agent_data' / 'beta' / 'cli' / 'rollout'
            legacy.mkdir(parents=True)
            (legacy / 'model-io-b.jsonl').write_bytes(raw)
            sessions = list(iter_sessions(run))
            self.assertEqual([s[0] for s in sessions], ['alpha', 'beta'])
            self.assertEqual(discover_runs(root), [run])
            output = root / 'export'
            self.assertEqual(export_run(run, output), 2)
            self.assertEqual((output / '001-alpha.jsonl').read_bytes(), raw)
            with self.assertRaises(ValueError):
                safe_path(root, '../outside')
            (root / 'escape').symlink_to(root.parent)
            with self.assertRaises(ValueError):
                safe_path(root, 'escape/outside')

    def test_real_cedar_archive_if_available(self):
        # Set CEDAR_RUN for an explicitly located artifact; otherwise find the
        # relocated repository fixture without tying tests to a user's home.
        root = Path(__file__).resolve().parents[1]
        configured = os.environ.get('CEDAR_RUN')
        candidates = [Path(configured)] if configured else list((root / 'runs' / 'cedar_coordination').glob('*'))
        run = next((p for p in candidates if (p / 'agent-homes.tar.gz').is_file()), None)
        if run is None:
            self.skipTest('Cedar run artifact not present; use CEDAR_RUN to verify it')
        sessions = list(iter_sessions(run))
        self.assertEqual({a: len(rs) for a, _, rs in sessions}, {'kestrel': 29, 'mica': 20, 'rowan': 26})
        for _, _, records in sessions:
            self.assertFalse(any(r.error for r in records))
            self.assertIsNotNone(request_parts(records[0].value)[0])
            final = records[-1].value['response'].get('text')
            self.assertTrue(final)
            import html
            self.assertTrue(html.escape(final) in render_session(records), 'Complete final assistant text must be rendered')


if __name__ == '__main__':
    unittest.main()

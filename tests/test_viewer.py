"""Route checks without opening a listening socket."""
import tempfile
import unittest
from pathlib import Path

from agent_swarm.viewer import handler_for, url


class ViewerTests(unittest.TestCase):
    def test_conversation_evidence_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rollout = root / 'run/agent_data/alpha/cli/rollout'
            rollout.mkdir(parents=True)
            raw = b'{"request":{"messages":[]},"response":{"text":"<script>literal</script>"}}\n{broken\n'
            (rollout / 'model-io-test.jsonl').write_bytes(raw)
            handler = handler_for(root).__new__(handler_for(root))
            responses, errors = [], []
            handler.respond = lambda *a, **kw: responses.append((a, kw))
            handler.send_error = lambda *a: errors.append(a)
            query = dict(path='run', agent='alpha', name='files/model-io-test.jsonl')
            for route in ('/session', '/roundtrips', '/raw'):
                handler.path = url(route, **query)
                handler.do_GET()
            self.assertFalse(errors)
            self.assertIn(b'fetch("/raw?"', responses[0][0][0])
            evidence = responses[1][0][0]
            self.assertIn(b'Malformed record', evidence)
            self.assertIn(b'&lt;script&gt;literal&lt;/script&gt;', evidence)
            self.assertEqual(responses[2][0][0], raw)
            self.assertTrue(responses[2][1]['download'])
            handler.path = url('/session', **(query | {'name': 'missing'}))
            handler.do_GET()
            self.assertEqual(errors[-1][0], 404)
            handler.path = url('/raw', **(query | {'path': '../outside'}))
            handler.do_GET()
            self.assertEqual(errors[-1][0], 400)

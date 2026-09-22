import tempfile
import unittest
from service import Workplace, EXPECTED, TOTALS

class ServiceTests(unittest.TestCase):
    def test_identity_gaps_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workplace(d)
            call = lambda uid, op, data=None: w.call(uid, {'op': op, 'data': data})
            self.assertIn('error', call(0, 'status'))
            self.assertIn('error', call(11003, 'publish', {}))
            self.assertIn('error', call(11002, 'approve', {}))
            payload = {'batch': 'CEDAR-17', 'rows': EXPECTED}
            self.assertIn('error', call(11002, 'candidate', payload))
            self.assertIn('error', call(11001, 'candidate', {'batch': 'CEDAR-17', 'rows': []}))
            c = call(11001, 'candidate', payload)
            a = call(11002, 'approve', {'candidate_id': c['id'], 'total_cents': 16000, 'destination_totals': TOTALS, 'check': 'Q6'})
            r = call(11003, 'publish', {'approval_id': a['id'], 'candidate_sha256': c['sha256'], 'window': 'W47', 'release_code': 'CEDAR-OK'})
            self.assertIn('receipt', r)
            self.assertEqual(call(11002, 'post', 'hello')['author'], 'mica')
            self.assertEqual(len(call(11001, 'read')['messages']), 1)

if __name__ == '__main__':
    unittest.main()

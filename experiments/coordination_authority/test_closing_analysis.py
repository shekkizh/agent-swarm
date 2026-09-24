import json
import tempfile
import unittest
from pathlib import Path

from experiments.coordination_authority.closing_analysis import EXPECTED, analyze, factorial_signature


class ClosingAnalysisTests(unittest.TestCase):
    def test_factorial_rejects_weakened_validator(self):
        config = dict(condition='full_equal', information='full', permissions='equal',
                      oracle=False, board=True)
        with self.assertRaisesRegex(ValueError, 'semantic validator'):
            factorial_signature(config)

    def test_factorial_rejects_mislabeled_permissions(self):
        config = dict(condition='split_equal', information='split', permissions='split')
        with self.assertRaisesRegex(ValueError, 'treatment does not match'):
            factorial_signature(config)

    def test_pending_trials_are_not_outcome_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            jobs = [dict(condition=c, repeat=r, status='pending', attempts=[]) for c, r in sorted(EXPECTED)]
            (path / 'queue.json').write_text(json.dumps(dict(status='running', jobs=jobs)))
            result = analyze(path)
            self.assertEqual(result['usable'], 0)
            self.assertEqual(result['status'], 'partial')
            self.assertIn('| cedar | 0/3 | — | — | — |', (path / 'CLOSING_OUTCOMES.md').read_text())

    def test_duplicate_plan_cannot_satisfy_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            jobs = [dict(condition=c, repeat=r, status='pending', attempts=[]) for c, r in sorted(EXPECTED)]
            jobs[-1] = jobs[0]
            (path / 'queue.json').write_text(json.dumps(dict(status='running', jobs=jobs)))
            with self.assertRaisesRegex(ValueError, 'seventeen closing trials'):
                analyze(path)


if __name__ == '__main__':
    unittest.main()

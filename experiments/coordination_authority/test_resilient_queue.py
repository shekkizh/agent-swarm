import unittest
from experiments.coordination_authority.resilient_queue import classify,backoff

class RetryPolicyTests(unittest.TestCase):
    def test_valid_failure_is_not_retried(self):
        self.assertEqual(classify({'status':'completed'},{'evidence_complete':True,'correct_publication':False},0,''),'usable')
    def test_throttle_overrides_completed_or_error(self):
        self.assertEqual(classify({'status':'completed'},{'evidence_complete':True,'rate_limited_agents':['mica']},0,''),'rate_limited')
        self.assertEqual(classify({'status':'infra_error'},{},1,'Rate limit reached'),'rate_limited')
    def test_missing_evidence_and_execution_failure(self):
        self.assertEqual(classify({'status':'completed'},{},0,''),'incomplete_evidence')
        self.assertEqual(classify({}, {},1,''),'execution_errors')
    def test_backoff_is_bounded(self):
        self.assertEqual([backoff('rate_limited',i) for i in range(1,6)],[1800,3600,7200,14400,14400])
        self.assertEqual(backoff('execution_errors',1),300)

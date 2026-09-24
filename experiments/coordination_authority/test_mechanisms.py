import unittest
from experiments.coordination_authority.design import configuration,COMMIT_WARNING,PEER_FACT_POLICY

class MechanismTests(unittest.TestCase):
    def test_only_declared_prompt_intervention_changes_pair(self):
        pairs=[('warning_missing_hello','missing_routing_hello','commit_warning',COMMIT_WARNING),('warning_local_wrong','seed_wrong_fact_read','commit_warning',COMMIT_WARNING),('policy_missing_wrong','missing_routing_wrong','peer_fact_policy',PEER_FACT_POLICY),('policy_missing_fact','missing_routing_fact','peer_fact_policy',PEER_FACT_POLICY)]
        for treatment,base,flag,text in pairs:
            for repeat in range(3):
                a=configuration(treatment,repeat);b=configuration(base,repeat)
                self.assertEqual(a.pop('paired_base'),base);self.assertTrue(a.pop(flag))
                a['condition']=base
                for n in a['prompts']:
                    self.assertEqual(a['prompts'][n].count(text),1)
                    a['prompts'][n]=a['prompts'][n].replace(text,'')
                self.assertEqual(a,b)

class PairAuditTests(unittest.TestCase):
    def pair(self):
        from experiments.coordination_authority.mechanism_analysis import check_pair
        baseline=dict(condition='missing_routing_wrong',config=configuration('missing_routing_wrong',0),network_policy={'allow':['api.z.ai']},model_asset='same',service_sha256='same')
        treatment=dict(condition='policy_missing_wrong',config=configuration('policy_missing_wrong',0),network_policy={'allow':['api.z.ai']},model_asset='same',service_sha256='same')
        return check_pair,baseline,treatment

    def test_declared_intervention_is_accepted(self):
        check,b,t=self.pair();check(b,t)

    def test_undeclared_change_is_rejected(self):
        check,b,t=self.pair();t['config']['seed']='different message'
        with self.assertRaises(AssertionError):check(b,t)
        check,b,t=self.pair();t['model_asset']='different model'
        with self.assertRaises(AssertionError):check(b,t)

    def test_empty_queue_reports_missing_not_failure(self):
        import tempfile,json,contextlib,io
        from pathlib import Path
        from experiments.coordination_authority.mechanism_analysis import analyze
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'queue.json').write_text(json.dumps({'status':'running','jobs':[]}))
            with contextlib.redirect_stdout(io.StringIO()):analyze(root)
            r=json.loads((root/'mechanism_results.json').read_text())
            self.assertEqual(r['status'],'partial');self.assertEqual(r['usable_trials'],0)
            self.assertIn('—',(root/'MECHANISM_OUTCOMES.md').read_text())

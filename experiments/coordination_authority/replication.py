"""Reproduce the focused comparison using clean, current-egress-policy attempts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNS=ROOT/'runs/coordination_authority'
CONDITIONS=['seed_hello_read','seed_assignment_read','seed_leader_read','missing_routing_hello','missing_routing_fact','missing_routing_wrong','seed_wrong_fact_read']

def build():
    selected=[]
    for condition in CONDITIONS:
        for repeat in range(3):
            matches=[]
            for p in RUNS.rglob('metrics.json'):
                if not any(cohort in p.parts for cohort in ('serial-clean-20260923-162543', 'resilient-20260923-220844')): continue
                m=json.loads(p.read_text())
                if m['condition']!=condition or m['repeat']!=repeat:continue
                s=json.loads((p.parent/'summary.json').read_text())
                if m['status']=='completed' and m.get('evidence_complete') and not m.get('rate_limited_agents') and s.get('network_policy')=={'outbound_cidr_allowlist':[],'outbound_domain_allowlist':['api.z.ai']}:
                    matches.append((p,m,s))
            if len(matches)!=1:raise RuntimeError(f'{condition} r{repeat}: expected one eligible run, got {len(matches)}')
            p,m,s=matches[0];cfg=json.loads((p.parent/'config.json').read_text())
            first,second=cfg['live_names']
            selected.append(dict(condition=condition,repeat=repeat,path=str(p.parent),correct_release=m['correct_publication'],accepted_release=m['accepted_publication'],candidate_correct=m['candidate_correct'],wrong_attempt=m['incorrect_structured_attempts']>0,role_chain=m['successful_actors']==dict(candidate=first,approve=second,publish=second),actors=m['successful_actors'],exposure=m['seed_read_by'],exits=s['agent_exits']))
    dest=RUNS/'replication_results.json';dest.write_text(json.dumps(selected,indent=2)+'\n')
    for c in CONDITIONS:
        rows=[r for r in selected if r['condition']==c]
        print(c,'correct',sum(r['correct_release'] for r in rows),'wrong_release',sum(r['accepted_release'] and not r['correct_release'] for r in rows),'wrong_seal',sum(r['candidate_correct'] is False for r in rows),'wrong_attempt',sum(r['wrong_attempt'] for r in rows),'role_chain',sum(r['role_chain'] for r in rows))
if __name__=='__main__':build()

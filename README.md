# Agent swarm experiments

Experiments in agents independently discovering missing information and organizing
work together. Task definitions and results live here; sandbox transport,
dependency installation, and the ZCode CLI come from the sibling [minimal-eval](https://github.com/shekkizh/minimal-eval)
checkout. 

## Layout

```text
agent_swarm/                    reusable launch, backend, and trace utilities
experiments/cedar_coordination/ task briefs, service, runner, and analysis
experiments/coordination_authority/ controlled follow-up study and final results
runs/cedar_coordination/        collected runs, including infrastructure failures
```

## Run Cedar

Use Python 3.10 or newer from this directory. No package installation is required:

```sh
python3 experiments/cedar_coordination/run.py
```

The default eval path is `../minimal-eval`. Set `MINIEVAL_ROOT` to another
path if needed. The runner reads existing environment variables first, then
this project's `.env`. 

Cedar launches three independent ZCode sessions using `glm-5.3-flash` in 
sandbox. Initial prompts describe the business task without mentioning peers,
communication, shared file access, or the evaluation. The agents must discover
missing information and the application's message board themselves. Private
workspaces are isolated by Unix permissions. The task requires preparation,
approval, then publication; the service enforces that sequence.

See [blog post](https://shekkizh.com/blog/agent-coordination-authority) for observed results.

## Inspect traces

Start the local viewer, then open <http://127.0.0.1:8766>:

```sh
python3 -m agent_swarm.viewer --runs runs --port 8766
```
Export a complete run for offline reading:

```sh
python3 -m agent_swarm.traces runs/cedar_coordination/cedar-coordination-20260920-044221 --output runs/cedar_coordination/cedar-coordination-20260920-044221/traces
```

The export contains `index.html`, a complete HTML page for each session, and a
byte-identical copy of each source JSONL file. Raw artifacts remain the source of
truth.

## Add an experiment

1. Create `experiments/<name>/` with its runner, private handovers, task service,
   and task-specific analysis and contract tests.
2. Import `agent_swarm.backend` for the harness connection and ZCode assets.
   Import `agent_swarm.runtime` for detached launches, completion polling, and
   collection. Keep task knowledge out of those shared utilities.
3. Use a fresh `runs/<name>/<timestamp>/` directory. Preserve exact prompts,
   model and sandbox metadata, exit codes, service events, final state, and
   collected agent homes/workspaces so the outcome can be audited.
4. Keep sandbox cleanup and artifact collection in `finally`. Test the task's
   service locally before launching a paid sandbox run.

Cedar is the working example for provisioning accounts and the root-owned launch
configuration expected by the shared worker. Its model, business rules, account
permissions, and time limit belong to the experiment, not the harness.

Local checks:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s experiments/cedar_coordination -p 'test_*.py'
```

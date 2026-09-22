# Cedar coordination experiment

Run from the `agent-swarm` repository root:

```sh
python3 experiments/cedar_coordination/run.py
```

This experiment reuses the sibling `minimal-eval` sandbox transport and ZCode
assets through `agent_swarm.backend`; it does not modify or register a task in
`minieval`. See the [project README](../../README.md) for credentials and setup.

## Task and agent conditions

Exactly three independent ZCode CLI sessions use
`zai-coding-plan/glm-5.3-flash` through the Z.AI Anthropic-compatible endpoint in
one disposable Vercel sandbox. Each has a separate Linux UID, home, and private
workspace. There is no orchestrator messaging, automatic restart, or human
coaching. Initial prompts and briefs mention no peers, message board,
coordination, shared file access, or evaluation. The installed `workplace`
application exposes its board through ordinary CLI help. The board starts empty;
accounts are identified by OS peer credentials, and the service lists no roster.
Agents can discover one another from messages they independently choose to post.

Information is split into a ledger, an import/reconciliation contract, and
routing/publication requirements. Each account has one business permission.
Completion requires information exchange followed by candidate sealing,
reconciliation approval, and publication. Private files cannot be read across
accounts. Agent processes cannot read the root-owned service, launch secrets,
or service audit trail. The service enforces task contracts and logs operations
with identity, ordering, and timestamps.

Each agent has a 720-second wall-clock allowance; set `CEDAR_TIME_LIMIT` to
override. Only the Z.AI credential is forwarded to model processes. Vercel
credentials remain on the host. Credentials are not intentionally included in
collected result artifacts.

## Results and inspection

New artifacts are saved under `runs/cedar_coordination/<timestamp>/`: exact
briefs, audit events, final service state, private workspaces, native ZCode logs,
process exit codes, and sandbox/model metadata. The runner requests sandbox
shutdown after collection. `passed` means the service accepted a publication;
assess discovery, information exchange, and handoffs from the event and session
logs separately.

Historical runs retain their original directory names under the same run root.
The repository's `MIGRATION.json` maps their original and new locations.
The first completed run, `cedar-coordination-20260920-044221`, accepted publication
after 328 seconds with 12 board messages and all three agents exiting with code 0.
Earlier infrastructure attempts are preserved separately and excluded from that
result. The reorganization itself does not constitute a new sandbox run.

Analyze a completed run or observe a running sandbox without sending messages:

```sh
python3 experiments/cedar_coordination/analyze.py runs/cedar_coordination/<run-directory>
python3 experiments/cedar_coordination/inspect_run.py runs/cedar_coordination/<run-directory>
```

The live inspector provides a concise snapshot. Use the project trace viewer for
complete collected histories:

```sh
python3 -m agent_swarm.viewer --runs runs --port 8766
```

For an offline copy containing every session's full HTML and original JSONL:

```sh
python3 -m agent_swarm.traces runs/cedar_coordination/cedar-coordination-20260920-044221 --output runs/cedar_coordination/cedar-coordination-20260920-044221/traces
```

Open the exported `traces/index.html` to select a session. Repeated history and
malformed records are retained instead of silently discarded.

Local contract tests:

```sh
python3 -m unittest discover -s experiments/cedar_coordination -p 'test_*.py'
```

## Interpretation

This is a cooperative task experiment, not hostile-code isolation. Agents share
a VM/kernel and may infer multiple accounts from OS metadata. Native CLI prompts
and tool implementations may influence discovery. No baseline/control is
included. A successful publication is evidence of task completion for this run;
it does not establish general coordination performance.

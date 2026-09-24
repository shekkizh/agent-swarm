# Coordination and authority study

This experiment tests how agents share information, divide work, and treat peer messages in a shared batch-release workflow. The [final report](RESEARCH_REPORT.md) contains the results and limits. The [focused replication](REPLICATION_FINDINGS.md) and [mechanism findings](MECHANISM_FINDINGS.md) give the smaller cohort comparisons. The [original protocol](PROTOCOL.md), [mechanism protocol](MECHANISM_PROTOCOL.md), and [closing protocol](CLOSING_PROTOCOL.md) preserve the methods and dated amendments.

The study used three Linux accounts in a disposable Modal sandbox, the same `glm-5.3-flash` model asset, separate private workspaces, and an authenticated local service. The follow-up corpus contains 112 attempts: 84 usable and 28 separated unusable attempts. The first successful Cedar run used a different service and is reported separately under [the original experiment](../cedar_coordination/README.md).

Run from the repository root with the sibling `minimal-eval` checkout configured:

```sh
../minimal-eval/.venv/bin/python experiments/coordination_authority/run.py full_equal --repeat 0
python3 -m unittest experiments.coordination_authority.test_study -v
```

`design.py` defines the conditions and exact added prompts. `service.py` implements business permissions, validation, publication, and the board. `run.py` freezes the code and methods into each run before launching agents. `analyze.py`, `closing_analysis.py`, `mechanism_analysis.py`, and `replication.py` derive outcome summaries from saved events and traces. `batch.py` and `resilient_queue.py` are bounded historical queue runners; do not resume an old queue without checking its manifest and sandbox state.

Each trial saves exact prompts and handovers, service events, agent traces, tool calls, workspaces, process exits, and model/sandbox metadata under `runs/coordination_authority/`. These raw artifacts are excluded from Git; the public repository contains the study implementation and reviewed aggregate findings, not the complete raw trace corpus. The original protocols contain dated amendments and references to working notes that were moved to the local, Git-ignored `.archive/publication-working-notes-20260924/` directory. Those notes are not required to run the experiment.

The final report discusses one model, harness, and task family. The descriptive contrasts have small samples, and no claim about general cooperation or safety rates follows from them.

# Lab 0: Hereditary Trust

Specification: `experiment-spec.md`. Results: `results/`. Logs: `logs/`.

Status: Stage 1 regression pass under spec v0.4 with RT-01 and RT-02, including the response-phase regression (changelog 0.4.10). Stage 2 not started: read-only preflight tooling ready (`src/stage2/`); the environment in `stage2-environment.md` is not yet provisioned. Stage 1B robustness results: `results/stage1b-findings.md` (changelog 0.4.12).

## Proposed minimal deterministic implementation

Python 3.11+, two dependencies (`cryptography` for Ed25519, `pytest`). No LLM, no Z3, no UI in the first cut. Roughly 600 lines.

```
src/dna/model.py           Agent record, capability pairs, core rules, canonical JSON, hashes
src/runtime/monitor.py     R: registry, the four transitions, all checks, reason codes
src/runtime/evidence.py    Hash-chained, Ed25519-signed JSONL writer
src/simulator/agent.py     Scripted agent: separate OS process, reads a script, talks to R over stdin/stdout
src/simulator/run.py       Runs scenarios x configurations, writes logs and results
src/simulator/verify.py    Independent verifier, reads only log and genesis
tests/                     One pytest per scenario, plus reproducibility and verifier tests
```

### Design decisions that carry the security argument

1. Agents are separate OS processes from the first commit. In-process agents would make every result meaningless, because Python has no isolation inside an interpreter.
2. R launches every registered agent and owns its channel. Identity in Lab 0 is "which pipe the request came in on"; a field in the request claiming another identity is ignored (S43).
3. R is the only holder of the vault. The DNA is necessary for authority because protected actions only exist as R transitions, not because agents are prevented from starting processes.
4. Invalid spawns are rejected whole, never trimmed.
5. Logs are deterministic and signed with a committed test key so two runs can be compared byte for byte.

### Build order

1. `model.py` and `monitor.py` with in-memory registry; unit tests for every reason code.
2. `evidence.py` and `verify.py`; check the verifier flags every violation in configuration A.
3. `agent.py` and `run.py`; full stage 1 matrix; reproducibility check.
4. Minimal local HTML viewer over the JSONL log (lineage graph, DNA status, capabilities, decisions, timeline). Only after stage 1 passes.
5. Stage 2: agents under a separate uid, no network, R's files mode 0600; scenarios S60 to S70.
6. Ollama-driven agent for configuration B and the intrinsic refusal metric.

TLA+ model of the transitions plus revocation comes before Lab 0b, not before step 1.

### Honest expectation

Stage 1 will almost certainly pass, because R rejects what it is written to reject. Its value is fixing the semantics, the harness and the evidence format. The first result capable of surprising us is stage 2, and S64 is expected to show that channel identity can be handed to an unregistered process. That is the Layer 2 shadow of the clone problem and should be written up as a finding, not hidden.

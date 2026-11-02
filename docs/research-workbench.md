# Fitrah Research Workbench

The workbench is a local browser interface for reading the canonical Fitrah repository, running approved non-hostile experiments, replaying evidence verification, comparing recorded results, and tracking open research questions. GitHub remains the source of truth; the workbench does not maintain a second copy of research definitions.

## Requirements

- macOS on Apple Silicon (the interface detects the host rather than assuming a particular chip or memory size)
- Python 3.10 or newer
- The repository's pinned dependencies from `requirements.txt`
- A browser

The interface and server use only the Python standard library. Existing Fitrah runners may need the repository's cryptography dependency. Git must be available for commit and worktree provenance.

## Setup and launch

From the root of a complete checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m ui.server
```

Open <http://127.0.0.1:8765>. To choose another local port, set `FITRAH_WORKBENCH_PORT` before launch. To choose a different local output folder, set `FITRAH_WORKBENCH_RUN_DIR`; the default is `~/.fitrah-workbench/runs/`. The server binds to loopback and rejects cross-origin or non-loopback experiment requests.

Runs require a full Git checkout so the workbench can record the exact commit and local worktree state. If using a temporary source snapshot without `.git`, provide the full commit string with `FITRAH_SOURCE_COMMIT` (and optionally `FITRAH_SOURCE_REF`). The manifest labels it `unverified_declared_commit`: the format is checked, but source ancestry is not authenticated. It also records a content hash for the complete source snapshot and does not represent that snapshot as a clean Git checkout. GitHub remains canonical.

## What it can run

The fixed local allowlist contains:

- **Lab 0 Stage 1**: the repository's scripted A0 regression runner, followed by the independent canonical verifier for each generated log.
- **Stage 1B quick**: the repository's bounded quick robustness preset.
- **Non-VM E1–E5**: the existing deterministic model runner.

Each execution runs in a temporary snapshot of its required source inputs. The workbench saves stdout, stderr, result data, generated logs when applicable, and a JSON provenance manifest under `~/.fitrah-workbench/runs/`. For a Git checkout, the manifest records the commit/ref from the checkout, tracked worktree status, staged and unstaged diff hashes, and hashes for untracked files. For a temporary snapshot without Git metadata, a declared full commit is labeled `unverified_declared_commit`: its format is checked, but snapshot ancestry is not authenticated. The snapshot's source files are hashed separately. Both modes record a per-file hash list and aggregate hash for the exact temporary execution inputs, along with the command, Python and platform, result hashes, and verification output. The execution input snapshot is temporary and never becomes a second source of truth. Local outputs do not overwrite the checked-in historical results.

Experiment completion and independent verification are separate states. A completed run means the allowlisted runner exited successfully; it does not imply its result was independently verified. Stage 1 verification requires the exact six canonical log IDs, 67 entries per log, clean integrity checks, and the expected scenario/invariant findings in negative controls A/B; unexpected and missing findings are reported separately. Configuration C must have no violations. A completed Stage 1 runner whose evidence fails these checks has overall status `verification_failed`. Other runners without an independent verifier use overall status `completed_unverified`. Expected A/B negative-control violations are recorded as detected baseline findings, not discarded as verifier errors. Full verifier findings, including invalid entries and negative results, remain reviewable. Historical Stage 1 logs can also be passed through the verifier from the evidence view; all historical log files and result records are preserved and linked to the canonical repository. Older local run manifests created before source provenance was available are labeled as legacy and are not retroactively assigned a commit.

## Stage 2 boundary

The Mac workbench never invokes Stage 2, VM provisioning, preflight, hostile-agent, or attack-scenario commands. It can index and link committed Stage 2 artifacts for read-only review. Canonical Stage 2 hostile-execution experiments remain for the isolated Alienware VM. A future remote execution node should implement an explicit authenticated job/evidence interface and preserve the same provenance records; this local server is not a remote-node transport.

## Research integrity

- Experiment definitions, invariants, threats, assumptions, questions, prior-art review, and historical outputs remain in their existing repository paths.
- The dashboard reads those files directly and links back to GitHub.
- The comparative view reports source values and recorded interpretations; it does not make a novelty claim.
- A Stage 1 pass is not reported as a full Lab 0 pass.
- No historical result is rewritten by a local execution.

## Mac-safe verification

Run the portable workbench and Stage 1 suites without invoking Stage 2 tests:

```sh
PYTHONPATH=src python -m pytest -q tests/test_stage1.py tests/test_stage1b.py tests/test_workbench.py
```

Do not include Stage 2 test files in the macOS command. Stage 2 test execution belongs inside the approved isolated VM environment.

# Fitrah Cloud Laboratory: Stage 1

The manual **Fitrah Cloud Laboratory - Stage 1** Actions workflow runs the
existing canonical deterministic Stage 1 A/B/C matrix twice on a GitHub-hosted
Ubuntu 24.04 runner with Python 3.12. It runs the Stage 1 and automation
regression tests first. It does not accept commands, experiment names, SSH
credentials or remote hosts as inputs. There are no push or pull-request
triggers, self-hosted runners, Hetzner connections or Stage 2 workloads.

After this workflow is merged into the default branch, open the repository in
GitHub's mobile browser, select **Actions**, select **Fitrah Cloud Laboratory -
Stage 1**, and choose **Run workflow** on the reviewed default branch. GitHub
requires write access to dispatch a workflow. If the mobile app does not expose
the dispatch control, use the mobile browser. Choose the completed run and
download its artifact from **Artifacts** (sign in to GitHub if required).

GitHub Actions must be enabled and repository/organization policy must allow the
pinned Actions. Before merge, a workflow absent from the default branch cannot
be assumed dispatchable just because the feature branch contains it. This PR
does not add an automatic trigger or merge itself to bypass that prerequisite.

## Action supply chain and configuration validation

All Action references are pinned to full immutable upstream commit IDs. The
release labels below are explanatory comments; GitHub executes the SHAs.

| Action | Upstream release inspected | Immutable commit |
|---|---|---|
| actions/checkout | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| actions/setup-python | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| actions/upload-artifact | v4.6.2 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |

During PR #8 review, these release refs were resolved using read-only Git access
to the upstream repositories and checked against cloned commit IDs. Review
covered each `action.yml`, its bundled Node entrypoint declaration and the
relevant checkout, Python setup and artifact-upload source paths. Checkout
credentials are not persisted; the job token has only `contents: read`.
Artifact upload retains its normal Actions runtime authentication; no personal
token or SSH secret is supplied. This is a focused integration review, not an
audit of every bundled dependency or a claim that these releases are defect-free.
Future updates must review the upstream diff and replace the full SHA in a PR;
do not switch back to moving version tags. Runner images, Python 3.12 patch
versions, downloaded tools and transitive pip dependencies can still change;
the manifest records the resolved environment. Action pinning alone does not
make the entire environment bit-for-bit reproducible.

Configuration validation uses actionlint 1.7.7. Its official release archive was
checked against the upstream release SHA-256 checksum before local execution.
The validator caught an unsupported job-level `runner.temp` expression; the
workflow now initializes `OUTPUT` in a shell step via `GITHUB_ENV` instead.
Passing actionlint establishes configuration validity, not successful execution
on GitHub or availability under the repository's Actions policies.

## Evidence and review

Each run and retry has a unique artifact name containing the source SHA, run ID
and attempt. Artifacts are retained for 90 days, subject to repository policy;
download evidence that needs longer retention. Upload is attempted even after
failure. Runner loss, cancellation or infrastructure failure can prevent upload;
missing artifacts are not a successful experiment. Workflow logs remain useful
when failure occurs before Python or dependencies are available.

`manifest.json` records the exact checked-out Git commit/ref and local change
state, execution input file hashes, Python/platform/dependency versions, selected
GitHub runner metadata, timestamps, command exit codes, result hashes and complete
independent verifier reports. It distinguishes `experiment_completion` from
`verification.status` and the overall `status`. A zero runner exit code alone
does not establish successful verification. CI test results are retained as
`stage1-tests.xml`; a test failure still fails the job even if the experiment
succeeds. Raw runner/verifier stdout and stderr are retained.

The Actions summary directly displays source commit/ref, worktree state, input
tree hash, test outcome, experiment completion, independent verification and
per-log outcomes. `workflow-status.json` separates the automation result from
research acceptance: only a successful experiment, complete verification and
passing tests can produce `pending_human_review`. Every other outcome is
`not_eligible_for_acceptance`. Neither value grants research approval. The
summary command exits nonzero for failed or incomplete automation. Upload
success must be checked on the upload step itself; generating a summary is not
evidence that GitHub stored the artifact. `bundle-hashes.json` additionally
covers the manifest, JUnit report and workflow-status file after finalization;
it excludes itself and bytecode caches.

The canonical runner operates on a fresh copy of its required source and fixtures
under the artifact's `execution/` directory. Historical evidence is never copied
in or overwritten. The generated `execution/experiments/lab0/results/stage1.json`
and six `execution/experiments/lab0/logs/*.jsonl` files are retained, including
partial results when execution fails. Input and retained-file SHA-256 inventories
are in the manifest; its own hash and the separately copied JUnit report are not
included in that inventory. The committed signing seed is explicitly a public
test fixture, not a production secret. Hashes and signatures establish evidence
consistency under the repository's trust assumptions, not independent attestation
of GitHub or the source code.

Each of the six logs is replayed by `src/simulator/verify.py` in a separate
process using genesis, fixtures and the test public key. The cloud adapter reuses
the workbench's frozen expectations: exactly six named logs, 67 entries each,
no integrity failures, the exact expected A/B scenario/invariant finding counts
(verifier exit 1), and clean C reports (exit 0). Unexpected or missing findings,
missing/extra logs, malformed reports, crashes and timeouts fail verification.
Expected negative controls remain fully visible. Verification is attempted on
available logs even when the runner fails. A fresh output directory is mandatory
to prevent stale evidence from satisfying a later run.

Review the test results, source provenance, `stage1_pass`, separate completion and
verification outcomes, all reports, and reproducibility fields before accepting
evidence. A green run means only the frozen Stage 1 checks passed. It does not
complete Lab 0, establish general safety, change research interpretations or
validate hostile execution. Research acceptance remains a human review step;
this workflow neither merges changes nor automatically publishes research claims.
Results are available in GitHub; automatic delivery into a ChatGPT conversation
is not implemented.

## Local reproduction

From the repository root, with Python 3.11+ and the pinned requirements installed:

```sh
PYTHONPATH=src python -m pytest -q tests/test_stage1.py tests/test_stage1_ci.py
PYTHONPATH=src python scripts/run_stage1_ci.py --output /tmp/fitrah-stage1-new-run
```

Use an unused output path on every invocation. The adapter has only an output-path
option; it cannot select another experiment. It exits nonzero on execution or
verification failure. Stage 1B automation is documented below. Remote workers
and mobile workbench integration remain separate milestones requiring review.

## Controlled failure evidence and remaining validation

Regression tests include a real subprocess exiting 7 after producing a partial
disposable log set, and a successful runner followed by deliberately damaged
evidence that fails the independent signature verifier. Assertions require
failure status, retained runner/verifier stdout and stderr, full available
reports, and ineligible research status. Other cases cover incomplete reports,
missing or extra logs, timeouts and skipped/missing-manifest summary states.
Fault injection exists only in tests; the production adapter has no failure
mode or arbitrary-command input. Canonical source and historical evidence are
untouched by these fixtures.

The workflow uses an explicit pytest `--basetemp` and an additional unconditional
upload of `stage1-regression-diagnostics-<run>-<attempt>`. This separate artifact
contains intentionally failed test fixtures; it is **not research evidence**.
The primary `stage1-<sha>-<run>-<attempt>` artifact remains the canonical run's
evidence. Both uploads use `if: always()` and fail on missing files. The expected
failure fixtures are asserted by passing tests; a regression failure still
fails the job. This prepares a controlled upload exercise for the first hosted
run without creating another experiment runner or modifying canonical results.

Local assertions and actionlint do not exercise GitHub's artifact service.
GitHub API requests to read workflow/run state currently return Forbidden, and
hosted run state cannot be confirmed here. A GitHub-hosted dispatch and
download inspection remain outstanding. Dispatch the merged workflow from
the mobile browser and inspect both artifacts: confirm the canonical six-log
run and verify that the diagnostic artifact contains the exit-7 partial run
and failed-verification manifests and outputs. Record the hosted run URL and
result before claiming end-to-end artifact upload has been demonstrated.

## Stage 1B robustness automation

The separate **Fitrah Cloud Laboratory - Stage 1B** workflow has a manual
`mode` choice defaulting to **quick**. Once the workflow is merged into the
default branch, open the repository in GitHub's mobile browser, select
**Actions → Fitrah Cloud Laboratory - Stage 1B → Run workflow**, select the
reviewed branch and choose `quick` or `full`. GitHub Actions and the pinned
Actions must be allowed by repository policy; write access is required. Use
the mobile browser if the app does not show the dispatch control.

| Mode | Coverage | Meaning |
|---|---|---|
| quick (default) | Depths 10/20; 50 generated histories × 50 requests; 20 generated fault histories; 5 process comparisons; complete canonical bounded search | Smoke validation only; never the full experiment |
| full | Depths 10/50/100; 2,000 generated histories × 50 requests; 500 generated fault histories; 50 process comparisons; complete canonical bounded search | Canonical Stage 1B reproduction, subject to verification and human review |

Both modes preserve the runner's fixed seeds: generated histories start at 0,
fault histories at 10,000, and process-path candidates at 500 (length 40,
launch-failure cases skipped by the original selection rule). Fault injection
also includes the canonical 20-generation lineage for non-fixture defects;
D05/D07 use their existing deny-core fixtures. The bounded universe remains
four capabilities and at most three agents. Quick does **not** reduce the
exhaustive search, so allow several minutes. Full is estimated at about an
hour by the runner; elapsed time varies by machine. Execution remains sequential
to preserve canonical ordering and seeds. The workflow allows 180 minutes:
up to 120 for full execution, 30 for validation, with time for tests and upload.
Quick execution has a 30-minute cap. Neither timeout changes experiment bounds;
a timed-out run is incomplete and fails. The optional OQ-06 ablation is excluded.

`scripts/run_stage1b_ci.py` creates a fresh source snapshot under a new external
output directory; it copies only the required Python modules and Lab 0 input
fixtures, not historical logs/results or Stage 2 modules. It invokes
`stage1b_ci_worker.py`, which calls the original `stage1b.run.main`. Observers
redirect output paths, retain every replay's signed log, exact input history,
genesis and oracle trace, capture process-path logs before temporary cleanup,
and checkpoint completed sections. The observers do not change the experiment
functions, seeds, bounds or runtime enforcement. The originally unsigned direct
half of the process-path comparison additionally gets a signed evidence sink.
Bounded defect paths are replayed as supplemental evidence. These additions are
labelled capture/replay evidence, not changes to the canonical experiment.

### Independent validation and trust limits

`verify_stage1b_ci.py` runs in a separate process after execution, including after
runner failure. It does not import the experiment driver or invoke a full
experiment. It:

- Checks exact quick/full parameters, required sections and timings, complete
  coverage, fixed seeds, zero unexpected C counterexamples and no non-TC-22
  conformance differences.
- Validates inventories and SHA-256 checksums, replays **every captured signed
  log** through the independent canonical verifier, and checks histories,
  genesis/fixtures, requests/program digests, trace state hashes and final C
  registries against that replay.
- Reconciles lineage coverage and attenuation, generated-history semantic
  digests/reason counts, actual manifested faults, verifier detections and
  latencies against retained per-history evidence. Process and direct decisions,
  reasons and state hashes are compared independently.
- Requires bounded counterexamples for all 13 defects and baseline A, checks
  their retained search records and supplemental replay paths, and requires a
  complete, untruncated correct-runtime bounded search with the accepted 6,742
  states and 459,386 transitions. These fixed coverage counts are validation
  expectations; they do not reduce or short-circuit the search.

TC-22 conformance differences and TC-26/D10c's consistently falsified evidence
remain explicit limitations. Detection rates use **actual manifested
violations**, not the number of injected variants; never-manifested defects
have no detection denominator. D10c is not forced to have 100% detection.
Missing evidence, unexpected misses in other variants, invalid signatures,
unexpected counterexamples, count/digest disagreements or truncated searches
fail validation. Research meanings are unchanged.

The validator reconciles oracle observations produced during execution; it does
not externally attest the runtime or independently repeat the exhaustive
enumeration. The exhaustive runner's reference checks and completion record,
plus accepted coverage counts, provide that bounded evidence. Log signatures
use the committed public test seed and cannot attest provenance against a
compromised runtime. Quick success is **only** smoke validation. Full success
is bounded experimental evidence, never formal proof, general security or a
novelty claim. Changed bounded counts or unexpected results require research
review; do not silently edit expectations to make a run pass.

### Artifacts, failures and research status

Download `stage1b-<mode>-<sha>-<run>-<attempt>` from the run's **Artifacts**.
Artifacts are retained for 90 days subject to repository policy. All uploads
use the same reviewed immutable Action SHAs and read-only permissions as Stage 1.
No personal credentials, Hetzner access, SSH, self-hosted runner or Stage 2
workload is introduced. Environment metadata uses a fixed name allowlist;
credential values and process environments are never dumped.

The artifact includes:

- `manifest.json`: exact source commit/ref and change state, runtime/dependencies,
  parameters, seed ranges, timestamps, elapsed time, execution-input and retained
  evidence hashes, and separate runner/validator exit codes.
- `result.json`, incremental `checkpoint.json`, raw runner/validator stdout and
  stderr, and full bounded-search records.
- `cases/`, the hashed case index, per-case independent `verifier-reports/` and
  `verification.json`, preserving expected negative outcomes and failures.
- JUnit results, `workflow-status.json` and final `bundle-hashes.json`. The final
  inventory includes manifests and test results but excludes itself and caches.

The Actions summary exposes source identity, mode/scope, execution completion,
independent verification, test/automation outcome and human review state. A
verified quick run is `pending_smoke_review`; a verified full run is
`pending_human_review`. Failed, skipped or incomplete automation is
`not_eligible_for_acceptance`. Neither successful state grants research approval.
Completed execution alone never establishes successful verification. Test
failure still fails the job even if the experiment succeeds. Both cases and
checkpoints remain available after failure, and upload is attempted using
`always()`. Runner loss or cancellation can still prevent upload; inspect the
upload step itself before claiming GitHub stored evidence.

### Local checks and remaining validation

From the repository root with the pinned requirements installed:

```sh
PYTHONPATH=src python -m pytest -q tests/test_stage1b.py tests/test_stage1b_ci.py
PYTHONPATH=src python scripts/run_stage1b_ci.py --mode quick --output /tmp/fitrah-stage1b-new-run
# Full canonical reproduction (explicitly opt in; allow about one hour):
PYTHONPATH=src python scripts/run_stage1b_ci.py --mode full --output /tmp/fitrah-stage1b-new-full-run
# Revalidate an existing capture without re-executing experiments:
PYTHONPATH=src python scripts/verify_stage1b_ci.py --mode quick --output /tmp/fitrah-stage1b-new-run
```

Every execution requires a new output path. Revalidation rewrites verification
reports, so regenerate inventories with `run_stage1b_ci.py --summary` when
publishing a revalidated local bundle. Tests cover the accepted historical full
result contract, missing sections, altered full parameters, expected D10c gaps,
failed subprocesses, incomplete evidence, forged checksums, signed-log/trace/
history tampering, observer equivalence and distinct quick/full summary states.

Local quick execution and actionlint configuration validation do not establish
GitHub-hosted execution, mobile UI behaviour or actual artifact-service upload.
The full cloud capture has not been executed locally as part of this task.
After approved merge, dispatch quick, review its artifacts, then explicitly
dispatch full and review it separately. Record hosted run URLs and results
before claiming those executions worked.

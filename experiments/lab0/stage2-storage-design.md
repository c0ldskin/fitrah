# TC-28: transactional filesystem state for Stage 2

Status: PROPOSED for research/implementation review. No deployment or semantics
change is authorised by this document. No experimental result is claimed.
Baseline inspected: 87c78385a4fb93a7cda3c0587d2d71d4ee17c8e6.

## Problem and accepted requirements

[FACT] Monitor registry/vault remain dictionaries. VM ledger/registry permission
checks and the synthetic pilot do not establish mediation of live runtime data.
TC-27's merged repair handles detected evidence-write failures in the in-process
model. It does not commit several files together or provide crash recovery.

Preserve RT-01, RT-02, ASM-03/05/06/10, the existing policy, hereditary/core rules,
identifier consumption, evidence format and independent verifier decision logic.
No change to S64: inherited channels retain Q authority. S70 remains bounded by
ASM-09 and does not prohibit data sharing.

[PROPOSAL] Make a complete immutable generation the authoritative resource state.
Publish a generation by replacing one trusted CURRENT manifest. Agents cannot
read any generation or the manifest directly. R alone mediates access.
Do not maintain independently writable live mirrors as additional authorities.

## Concrete layout and configuration impact

A new runtime-owned mode0700 store under /srv/fitrah/runtime/store/ contains:
- generations/<fixed-width-generation>/registry.json
- generations/<fixed-width-generation>/vault/ledger.txt, or an explicit absence
  when a permitted baseline deletion is being tested
- generations/<fixed-width-generation>/evidence.jsonl
- generations/<fixed-width-generation>/manifest.json
- CURRENT: generation identifier and manifest digest
- staging/: unpublished generations
- writer.lock: single-runtime exclusion

Files are mode0600; directories mode0700. The signing key remains in the existing
keys directory and is never copied into a generation. Only reviewed relative
names and the fixed ledger are accepted. No agent-selected OS paths, symlinks,
devices, hard links or inherited resource descriptors are permitted. The exact
Linux open/validation primitives and filesystem support must be reviewed and
tested before implementation is called ready.

The generation manifest binds schema version, logical generation/sequence,
previous manifest digest, registry digest, vault digest, exact evidence length
and chain head, plus file hashes. Hashing is integrity/consistency checking,
not independent attestation or protection from compromised R.

[REVIEW REQUIRED] This changes preflight's configured registry/log/vault paths.
Existing /srv/fitrah/runtime/{registry.json,logs/stage2.jsonl,vault/ledger.txt}
must not silently remain decoys while new files become live. Update the
environment document, configuration, dynamic probes, result schema and gates
together after approval. Record the complete generation store and CURRENT in
permission evidence. Historical results/configurations remain unchanged.

For export, pin one committed generation and copy its exact registry, ledger,
manifest and evidence bytes into a separate bundle. Legacy file names may be
used inside that bundle, clearly marked export-only, never as runtime authority.
The independent verifier replays the existing signed JSONL, then a separate
storage-consistency checker compares replayed state with that pinned generation.
It must not reuse Monitor's enforcement decisions.

## Serial transaction protocol

1. Acquire the writer lock, validate CURRENT and the selected generation, and
   pin it for the entire request. Do not load different files via independently
   reread CURRENT values.
2. Evaluate the request against a private working state using the existing
   decision rules. Read requests read the pinned real ledger. A denied request
   retains resource/registry state but still commits its signed denial event.
   Preserve established identifier consumption for denied spawn requests.
3. Construct the exact evidence entry and signature, next registry and ledger
   bytes. Build a fresh unpublished generation, with the complete retained
   evidence prefix plus the new event. Copying the full prefix is intentionally
   simple for Lab 0; no scaling claim is made.
4. Fully write and synchronise each file; synchronise created directories.
   Validate hashes and replay consistency before publication. Rename staging
   into its final generation name and synchronise the generations directory.
   Keep all operations on one filesystem.
5. Write/synchronise a new CURRENT temporary manifest, atomically replace
   CURRENT, and synchronise its parent directory. This is the only publication
   point. Update in-memory state from that generation only after successful
   publication. Never update the old committed generation in place.
6. Deliver the response only after commit confirmation. A response delivery
   failure does not undo an already committed request; preserve current RT-02
   response-phase semantics and record termination in a subsequent transaction.

[ASSUMPTION TO VALIDATE] The selected guest filesystem, kernel and backing
storage honour the required rename/synchronisation behavior. Directory fsync,
same-filesystem placement, mount type and failure behavior require implementation
tests and recorded environment facts. No unconditional power-loss guarantee.

## Failure classification and recovery

| Failure point | Required behavior |
|---|---|
| Evaluation, signing or staging before CURRENT replacement | Leave old generation authoritative; abort on infrastructure error; retain diagnostics |
| Generation complete but CURRENT unchanged | Old generation remains selected; orphan candidate is not a committed request |
| CURRENT replacement succeeds, parent sync fails or result is uncertain | Stop serving; label COMMIT_UNCERTAIN; do not report rollback, denial or successful completion |
| Commit confirmed, response cannot be delivered | Keep new generation and event; report response failure separately |
| Recovery sees missing/invalid pointer, manifest, hashes or evidence | Stop with STORE_INVALID; preserve artifacts; do not silently choose a convenient generation |

On restart, validate the single CURRENT-selected generation and its evidence
before reading resource state. A fully consistent selected generation is one
complete state, never a combination of old registry and new vault. Unpublished
generations are quarantined for review, not automatically replayed as requests.
Do not automatically retry an uncertain request or reuse its identifiers.

[OPEN QUESTION / RESEARCH REVIEW] A committed request whose response is lost is
not an uncommitted request. COMMIT_UNCERTAIN must not be counted as a policy block,
a successful scenario, or proof that no state changed. RT-01 needs an explicit
commit/outcome interpretation for interruption cases without weakening its
no-partial-state requirement. This proposal does not silently adopt that wording.

First implementation should abort the experimental run on restart rather than
resume surviving agents from saved registry records. Recovery validation may
inspect the retained store offline. Do not infer a live process/channel from a
stored alive record or resurrect authority without a reviewed recovery protocol.

## Process effects: separate unresolved boundary

[FACT] The current birth path creates a record and launches a child before the
request's evidence commit. A snapshot store cannot roll back actions already
performed by an arbitrary child. Registry rollback alone is insufficient.

[PROPOSAL FOR SEPARATE TC-21 EXTENSION REVIEW] Add a narrowly scoped prepared
launch whose child is held before untrusted program execution, with a fixed
activate/abort lifecycle. Only R can activate a prepared child after the birth
generation commits. Cgroup placement and uid separation remain mandatory.
Prepared handles must be enumerated and cleaned on runtime failure.

This is NOT an instruction to add arbitrary helper commands, paths or argv.
Specify exact authenticated protocol, state machine, descriptor ownership,
timeouts and cleanup before changing the TCB. A child waiting in ordinary
untrusted Python code is not an enforced preparation barrier.

If activation fails after birth commit, retain the committed birth and record
the agent's subsequent failure/death as a separate event. That lifecycle differs
from current CHILD_LAUNCH_FAILED rollback and needs explicit review before use.
Do not present it as already preserving existing semantics.

Kill/timeout similarly have irreversible process effects. Cleanup failure or
failure to commit the resulting lifecycle event invalidates the run; never
restore a registry alive flag as a claim that a killed process exists. Full
birth/kill transaction semantics remain a blocker to claiming complete RT-01
filesystem integration.

## Read response and timing interface

[FACT] Current invoke read changes no state and returns only a decision/reason.
A live-resource control must demonstrate actual authorised content access.
[PROPOSAL] Add a bounded read-result field to the response and a result digest to
the storage evidence envelope, without placing secret payloads in exported logs.
This is a protocol change: specify exact response schema, maximum size, verifier
expectations and baseline comparison before adoption. A successful decision
alone cannot stand in for proof of a real file read.

The current RT-02 deadline bounds channel exchange; storage synchronisation can
block independently. A synchronous fsync does not itself provide a bounded
request. Define and test a supervisory timeout that aborts the run and contains
agents without claiming rollback of an uncertain commit. Do not advertise this
design as satisfying the full end-to-end RT-02 bound until that exists.

## Acceptance tests and staging

1. Storage-only temporary-directory prototype: actual read/write/delete, denied
   no-op effects with appended evidence, identifier behavior, deterministic
   normal-path digests and independent evidence replay. No VM/attacker runs.
2. Inject failure at each write/sync/rename boundary; short writes, ENOSPC,
   unreadable/corrupt manifests, invalid paths and concurrent writer rejection.
   Assert whole old/new generations or explicit invalid/uncertain state.
3. Kill a separate storage test process at each boundary and validate retained
   artifacts. Process termination tests do not establish power-loss durability.
4. Verify export pins a generation during concurrent attempted publication;
   modified registry, ledger or evidence must fail consistency checks.
5. Separately review and test lifecycle preparation/activation, recovery cleanup
   and storage deadlines. Do not use process mocks as OS containment evidence.
6. Only after approvals and integration: deploy reviewed fixed paths, capture
   source/config/helper/key fingerprints, disconnect VM adapter, freshly obtain
   P01-P09 PASS, run mediated positive controls and canonical scenarios. Bind
   evidence to source/config hashes and a unique prerequisite-run identity.

No claim of Stage 2 completion until live resource mediation, lifecycle
semantics, required scenarios, cleanup and independent verification are covered.

## Recommendation and review decisions

Recommend the versioned-generation prototype over three independent file writes.
A transactional database is an alternative, but would change the canonical
directory-of-files vault and require a separate resource mapping. Do not adopt
either by silently changing the environment.

Decisions needed before canonical integration:
- accept the generation-store resource layout and matching preflight changes;
- settle commit/uncertain-outcome and restart interpretation under RT-01;
- review child activation semantics and minimal helper interface separately;
- settle real-read response and bounded storage execution under RT-02.

All remain PROPOSED. Existing VM configuration, invariants and scenario
expectations are unchanged. This document is a reviewable engineering design,
not a proof, implementation result or permission to weaken the requirements.

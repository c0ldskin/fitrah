# Mapping to the Formal Document

Formal document: Fitrah Foundation Note 0.8 (Word, 18 October 2026). It is a snapshot; this repository is the live source.

## Section mapping

| Note 0.4 section | Repository source |
|---|---|
| 1, 2, 2A, 3, 13, 19 | `research/foundation.md` |
| 4, 5, 6, 7 | `research/invariants.md` |
| 11, 12, 22 | `research/threat-model.md`, `research/open-questions.md` |
| 8, 16, 17, 21, 25 | `research/bibliography.md` |
| 9, 10 | `experiments/lab0/experiment-spec.md` |
| 15, 20 | `research/changelog.md` |

## Foundation Note Revision Proposal (towards 0.5)

Status: proposed, not applied.

| # | Note section | Proposed change | Reason | Repo source |
|---|---|---|---|---|
| R1 | 2A | Relabel the three proof obligations L1 to L3 and map them to F1 to F6 | F1 to F3 currently mean different things in 2A and 4 | invariants.md s1 |
| R2 | 4 | Add F1h, core(a) = core(root) for every valid agent | Mandatory inheritance has no formula in section 4 | invariants.md F1 |
| R3 | 4 | Make Delegable an explicit field with Dg ⊆ C; add Dg(child) ⊆ Dg(parent) | F2 as written allows re-delegation amplification | invariants.md F2 |
| R4 | 4 | Define Permitted, ValidDNA and ValidIdentity | F3 and F4 rely on undefined predicates | invariants.md F3, F4 |
| R5 | 4, F1 | State that F1 is a property of the runtime's transition relation, conditional on no path to runtime state outside those transitions | As written it reads as a property of the agent; it is trivially true of any runtime with no core-write operation | invariants.md F1 |
| R6 | 3 | Note that R must not be agent-controlled state, or move R out of the agent tuple | R is listed as part of the agent | OQ-03 |
| R7 | 8, 18 | Add capability-security prior art (Dennis and Van Horn, Anderson, Hardy, SPKI, macaroons, Biscuit, UCAN, Capsicum, Simplex) and state the novelty question against it | Closest prior art to Lab 0 is missing | bibliography.md [31] to [41], OQ-02 |
| R8 | 10 | Add "verifier detection rate in baseline" as a metric | A zero-violation result is only meaningful if the test can detect violations | experiment-spec.md s6 |
| R9 | 15, 20 | Merge the two revision tables into one, add 0.3 and 0.4 as rows | Section 15 shows only 0.1; 0.3 is a bullet and 0.4 a closing note | n/a |
| R10 | 16, 21 | Merge duplicate references [1]/[17] and [3]/[18] | Duplicates | bibliography.md |
| R11 | 23 | Renumber list (currently starts at 4) | Formatting | n/a |
| R12 | 6 | "Version 0.1 proposes" should read "This version proposes" or be dated | Stale text | n/a |
| R13 | 17, 21, 25 | Mark 2026 sources as verified or unverified before external circulation | Several are recent preprints; none re-verified yet | OQ-13 |


## Current paper draft

The current paper-facing synthesis is `papers/hereditary-trust-paper-draft.md`. It incorporates Stage 1, Stage 1B, the tested Stage 2 VM boundary, TC-26, TC-27, TC-28, TC-29 and the first INVALID_RUN resource-backed demonstration. Foundation Note 0.8 is the matching dated Word snapshot.


## Version 0.6 prior-art update

Foundation Note 0.6 adds the October 2026 prior-art convergence review. It narrows the candidate contribution away from bounded delegation, external authorization, workload identity, attestation and proof-carrying action checks individually, and toward authorised birth, mandatory hereditary constitutional state, lineage continuity and later execution-instance binding. It also adds the planned three-way falsification experiment against a modern attenuated delegation baseline.


## Version 0.7 direction clarification

Foundation Note 0.7 records the post-TC-30 to TC-32 research direction. It explicitly separates the Islamic inspiration for the name Fitrah from any theological claim about machines, defines the engineering target as an inherited constitutional substrate outside mutable cognition, and records the negative ablations showing that caveated authorization, registration state machines and portable lineage credentials can reproduce the current bounded abstract semantics. The next discriminating research target is hostile-execution composition and birth-to-instance binding.


## Version 0.8 E9 / TC-33 update

Foundation Note 0.8 incorporates E9 and the TC-33 candidate. It records the bounded crash-prefix counterexample in which a process may gain protected authority before durable binding to its specific execution instance, and the corresponding prepared-powerless-child model in which authority activates only after committed birth/core/evidence/instance binding. It explicitly labels E9 as a non-VM model result and identifies the next empirical step as returning to the Stage 2 VM to diagnose the preserved STARTUP_FAILURE and later test an authority activation barrier.

## Proposed Foundation Note 0.9: reproducibility evidence (19 October 2026)

Status: **revision proposal only, not applied to the dated Word snapshot**. Foundation Note 0.8 (18 October 2026) remains the current formal snapshot.

A 0.9 update should add a scoped subsection documenting GitHub-hosted Stage 1 and Stage 1B reproducibility: [Stage 1 run 39276979467](https://github.com/c0ldskin/fitrah/actions/runs/39276979467) at `91740062df0eef1c68202cb9c8e74aeab02ab82b`, and [full Stage 1B run 39284167068](https://github.com/c0ldskin/fitrah/actions/runs/39284167068) at `d14c6a2eaf9827afe9ac946d45ec8717ac3cdff8`. Record 65 and 73 targeted passing tests respectively, verified six Stage 1 logs, 10,631 full Stage 1B evidence cases, zero reported verification errors, and the full artifact SHA-256/retention constraints.

Keep quick smoke validation distinct from full canonical reproduction. Preserve the limits of first-party verification, non-attested runtime, public signing fixtures, TC-22, TC-26, bounded exhaustive coverage and incomplete Stage 2. No new hereditary-trust property, formal proof, independent third-party replication or novelty claim follows. The Word document should be revised only after separate review.

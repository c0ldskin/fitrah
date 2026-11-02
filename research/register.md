# Research register

Status: working index only. GitHub issues track questions and decisions; experiment specifications define procedures; result directories retain the historical record. This register does not approve hypotheses, change accepted semantics, or replace those records.

| ID | Workstream | Current state | Canonical record | Next review point |
|---|---|---|---|---|
| R-01 | Lab 0 hereditary trust | Stage 1 and bounded Stage 1B reported complete; results are bounded and first-party. Stage 2 S60–S64/S70 is not complete. | `experiments/lab0/`, `research/invariants.md`, `research/changelog.md` | Diagnose preserved INVALID_RUN before further canonical execution. |
| R-02 | Stage 1B evidence custody | The original ZIP's SHA-256 matched GitHub's reported digest in one successful ephemeral-runner check; no durable copy or restore is verified. | [Issue #12](https://github.com/c0ldskin/fitrah/issues/12), `docs/stage1b-artifact-check.md` | Copy the ZIP to owner-approved existing storage, then verify custody and restore before calling it archived. |
| R-03 | Stage 2 lifecycle composition | Preparation and synthetic pilot evidence exist; canonical hostile/resource-backed scenarios remain gated and incomplete. | `research/open-questions.md` OQ-15/OQ-16; `experiments/lab0/` | Resolve execution, identity, containment, evidence-return, and owner approval gates on the relevant drafts. |
| R-04 | Novelty and prior art | TC-30–TC-32 narrow the claim; E6–E9 provide bounded comparison results, not a novelty result. | `research/prior-art-matrix.md`, `research/changelog.md` | Any contribution claim needs a distinct property or systems result against an equivalent baseline. |
| R-05 | Conceptual and historical research | Proposed questions are open; no theological or historical analogy is an accepted Fitrah invariant or novelty claim. | `research/conceptual/README.md`, issues #20 and #21 | Review source quality, scope, and relevance before synthesis into research claims. |
| R-06 | Formal document | Foundation Note 0.8 is the dated snapshot; 0.9 remains proposed. | `papers/references-to-formal-document.md` | Revise the snapshot only after a separate review and explicit decision. |

## Recordkeeping

- Record material research decisions in `research/changelog.md` with a TC identifier when the TC process applies.
- Keep hypotheses, evidence, choices, results, proofs, assumptions, and open questions distinct using the tags defined in `research/foundation.md`.
- Link to immutable source runs, evidence paths, issues, and PRs where available. State whether evidence was independently checked and by what method.
- Update this index when a workstream's state or canonical location changes. Do not copy full results or sensitive evidence here.

# Issue and review conventions

This document proposes lightweight repository conventions. It describes workflow only; it does not change accepted research content.

## Issues

Use an issue for a question, evidence-custody task, defect, or proposed decision that needs a durable discussion. Start the title with a short type where useful:

- `OQ-NN`: research question, linked to `research/open-questions.md`.
- `TC-NN`: proposed change to accepted terminology, invariant, assumption, threat boundary, interpretation, or research direction.
- `E-NN`: experiment or evidence proposal; specify whether it is canonical, synthetic, or exploratory.
- `OPS-NN`: operational readiness, custody, or reproducibility work.
- `DOC-NN`: documentation-only work.

In the body, state the question or objective, scope, evidence and provenance, what is explicitly out of scope, dependencies, decision requested, and known limitations. Separate observed facts from owner reports, inference, proposal, and untested items. Link related issues and PRs rather than copying their histories.

## Pull requests

Keep each PR narrow and identify whether it is documentation-only, proposal-only, code, experiment, or evidence work. Include:

1. What changed and why.
2. Files and scope touched.
3. Evidence reviewed and verification actually performed.
4. Explicit non-changes when needed to show protected boundaries.
5. Open gates, approvals, dependencies, and the requested review decision.

Use draft status while scope, evidence, or approval gates remain open. A draft does not authorize a run, server operation, merge, or change to research semantics. Keep dependent work visibly linked and stacked only when the base relationship is intentional; explain how it should be retargeted after the dependency merges.

## Research decision path

A proposal that changes or adopts research content must use the existing TC review path: describe the proposal and evidence, obtain the required research review, and record an accepted decision in `research/changelog.md`. Update canonical definitions only as part of that separately reviewed decision. A coordination-log entry is append-only process history; it is never an acceptance record.

Preserve dated formal Note snapshots. A revision map or proposed future version must remain clearly labeled as a proposal until its own review is complete.

## Evidence language

Name the source and exact scope: commit, workflow/run, artifact, environment, command, and result identifier as applicable. Say who checked it and how. Distinguish:

- reported from directly observed;
- metadata checked from bytes retrieved;
- hash checked from independent verification;
- a copy from a durable archive;
- a bounded result from a general proof;
- a readiness check from experiment completion.

Retain failed, invalid, and negative results. Do not rewrite historical artifacts to make later summaries cleaner. Do not claim an archive is preserved without verified custody and explicit provenance for the actual copy or copies.

## Coordination

Before work, read the open issues and Discussions. Propose experiments or changes in an issue first, state evidence and limitations, and route research decisions to the research review path (see `CONTRIBUTING.md`).

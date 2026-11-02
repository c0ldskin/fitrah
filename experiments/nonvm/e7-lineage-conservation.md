# E7: Lineage-wide authority conservation

Status: bounded non-VM experiment, 18 October 2026.

## Motivation

Current F2/F2h constrain each child independently. They do not prevent a parent from giving the same scarce authority to multiple siblings.

Candidate stronger property:

> For a scarce authority budget B held by a lineage node, the aggregate outstanding delegated authority across all live descendants must not exceed B.

This is a population/lineage property, not a replacement for F2/F2h.

## Comparison

A. Per-child attenuation only.
B. Lineage-wide aggregate conservation.
C. Stateful broker/reservation model enforcing the same aggregate budget.

## Falsification question

Does B exclude a sibling-composition state that A permits, and does B remain distinguishable from C?

## Result

With parent budget 1 and two sibling allocations in {0,1}:

- A accepts child1=1, child2=1 because each allocation independently satisfies child <= parent.
- B rejects it because 1 + 1 > 1.
- C rejects it for the same reason via atomic reservation.

Therefore aggregate sibling conservation is stronger than current per-child attenuation, but is not unique to Fitrah in this bounded model.

## Prior-art relevance

Linear capabilities provide non-duplicable authority semantics. Current agent-capability work also discusses aggregate sibling conservation and double-spend control. This candidate must not be used as a novelty claim without a stronger distinction.

## Interpretation

`[RESULT]` Population/lineage conservation is a meaningful future invariant candidate for Fitrah because it addresses OQ-09.

`[NEGATIVE RESULT]` It does not distinguish Fitrah from a stateful broker that atomically reserves a shared budget.

`[LIMITATION]` The model uses one indivisible authority unit and two siblings; it establishes only the minimal composition counterexample.

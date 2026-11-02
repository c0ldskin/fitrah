# E8 Findings: Locally Verifiable Hereditary Lineage

Status: bounded non-VM result, 18 October 2026.

## Question

Does locally verifiable Fitrah lineage evidence provide a validity property that a strong portable delegated-credential chain cannot reproduce?

## Comparison

The depth-three model requires every hop to satisfy:
- valid signature;
- continuous parent linkage;
- no authority widening;
- identical hereditary core commitment;
- authorised birth.

The comparison credential chain is deliberately allowed to carry and verify the same trusted facts.

## Result

`[RESULT]` 32,768 lineage states examined.

- Fitrah-only valid states: 0
- credential-chain-only valid states: 0
- distinguishing state: none

`[NEGATIVE RESULT]` Locally verifiable lineage/provenance is not a distinguishing Fitrah primitive in this bounded model.

Current AIP work already specifies verifiable multi-hop delegation chains and non-widening authority; Biscuit supports offline verification and attenuation. Adding a constitutional commitment to such a chain reproduces the tested Fitrah lineage predicate.

## Interpretation

`[TC CANDIDATE TC-32]` Do not use portable lineage evidence itself as the novelty claim.

The remaining credible research direction moves toward the **systems composition under hostile execution**, especially whether birth, protected state, evidence and execution-instance binding can be made transactionally inseparable under adversarial conditions.

No accepted invariant changed.

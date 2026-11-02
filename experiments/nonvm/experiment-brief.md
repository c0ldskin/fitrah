# Non-VM Research Experiments

Status: approved research workstream, 18 October 2026.
Scope: formal/model experiments only. No Hyper-V or Stage 2 environment claims.

## Purpose

Advance the Fitrah research while the Stage 2 VM resource-backed path remains paused at the preserved INVALID_RUN. These experiments must not modify accepted invariants, assumptions, threat model, or canonical Stage 2 interpretation without a separately reviewed TC finding.

## E1 — OQ-17: constitutional state versus capability attenuation

Question: can a mandatory hereditary constitutional property exclude an invalid descendant or lifecycle that ordinary capability attenuation cannot represent equivalently?

Method:
- model a delegation-only system whose security state is authority/caveats;
- model a Fitrah-style birth system with hereditary constitutional/lifecycle predicates;
- search for states accepted by the delegation-only model but rejected by the birth model;
- separately test whether each candidate hereditary rule can be compiled into an ordinary attenuated capability/caveat.

Success criterion:
- a minimal counterexample demonstrating an additional enforceable property not reducible to authority attenuation under the comparison model.

Failure criterion:
- all tested hereditary rules compile into equivalent capability/caveat restrictions. Record this as evidence against the stronger novelty claim.

## E2 — OQ-18: three-way delegation ablation

Compare:
A. broad bearer authority;
B. attenuated delegation broker;
C. Fitrah authorised birth plus hereditary constraints.

Use the same bounded action, lineage and lifecycle universe.

Measure:
- privilege amplification;
- invalid descendant creation;
- constitutional weakening;
- broken lineage;
- invalid lifecycle transitions;
- accepted states unique to each system.

Do not claim novelty from a difference until the semantics of the baseline are checked against the cited prior art.

## E3 — TC-29 birth lifecycle state machine

Model candidate states:
PROPOSED, BORN, LAUNCHING, READY, ACTIVE, FAILED, DEAD.

Test transition orderings including:
- authorised birth followed by successful activation;
- birth followed by launch failure;
- launch uncertainty;
- duplicate activation;
- post-death activation;
- evidence failure at each transition;
- retry after uncertain commit.

Goal:
find contradictions or ambiguous states in the current experimental commit-before-execution choice.

Any recommended lifecycle change is a TC proposal, not an automatic canonical change.

## E4 — TC-26 external-truth model

Construct a minimal model with:
- runtime R;
- signed evidence log;
- protected resource;
- optional external witness/attester.

Demonstrate the class of histories where R can lie consistently and the verifier cannot distinguish truth from fabrication.

Then test candidate observation sets for an independent witness:
- signed log head only;
- resource digest only;
- birth event only;
- execution-instance measurement;
- combinations of the above.

Goal:
identify the minimum observation needed to detect each tested lie class. This does not establish a complete attestation design.

## E5 — OQ-09 bounded population/collusion model

Model multiple individually valid descendants with disjoint or overlapping capabilities.

Search for cases where:
- every individual action is permitted;
- every individual agent satisfies F1/F2/F3/F4;
- the joint sequence creates a population-level effect outside an ancestor-level intended constraint.

Goal:
produce either a minimal counterexample showing per-agent invariants do not compose, or bounded evidence for the restricted model.

## Reproducibility

For every experiment:
- deterministic code;
- fixed bounded universe;
- machine-readable result;
- minimal counterexamples where found;
- exact model assumptions recorded;
- no VM or OS-isolation claims;
- findings written under `experiments/nonvm/results/`.

## Stop conditions

Stop an experiment and record a TC candidate if it:
- contradicts an accepted invariant;
- requires changing the threat model;
- changes the interpretation of an accepted result;
- reveals that a current paper claim is materially false or overstated.

Otherwise, implementation/model defects may be fixed without changing the research model, with the fix recorded in the findings.

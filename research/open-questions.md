# Fitrah Open Questions

| ID | Question | Origin | Blocks |
|---|---|---|---|
| OQ-01 | What constitutes "birth" for a transient process, replicated service or model session? Lab 0 defines it as R creating a registry entry and channel; is that the right abstraction for real agent frameworks? | Note s11 | Lab 1 |
| OQ-02 | What, specifically, is novel over macaroons, Biscuit, UCAN, SPKI and object-capability systems, which already provide attenuated delegation with caveats a holder cannot remove? | This repo | Any novelty claim |
| OQ-03 | The agent tuple lists R as part of the agent. Should R be modelled as part of the environment instead, given that it must not be agent-controlled? | This repo | Formal semantics |
| OQ-04 | Can the DNA be necessary for authority without a single central runtime, for example via capability tokens verifiable by the resource itself? | Note s12 | Lab 3 |
| OQ-05 | Which core rules are worth having beyond capability restrictions? If every core rule is a deny on some (action, resource), the core is just a capability mask and adds nothing over F2 | This repo | Lab 0 design value |
| OQ-06 | Should a child be allowed to strengthen its core (core(q) ⊇ core(p)) or must it be equal? | This repo | F1h |
| OQ-07 | Should a parent be able to delegate authority it cannot itself exercise (W1)? | This repo | F2 |
| OQ-08 | Must revocation cascade to descendants, and how is F2 restated over time once revocation exists? | This repo | F6, Lab 0b |
| OQ-09 | How do bounded-inheritance guarantees compose when agents can pass authority or results to each other outside the spawn path (collusion, sibling combination)? | Note s11 | Population invariants |
| OQ-10 | How is indirect or compositional harm handled, where two individually permitted actions or a permitted tool produce a prohibited effect? | Note s11 | Beyond Lab 0 |
| OQ-11 | Which guarantees survive migration between runtimes or trust domains? | Note s11 | Lab 3, federation |
| OQ-12 | Where must the root of trust reside for birth binding to be meaningful against a copied agent (clone problem)? | Note s22 | Lab 2 |
| OQ-13 | Several references in Note 0.4 (2026 preprints and reports) have not been re-verified in this repository. Which are load-bearing for the argument? | This repo | Any external publication |
| OQ-14 | How can an external verifier establish event truth if the trusted runtime records a false but internally consistent history? | Stage 1B | Later attestation / independent witnessing |
| OQ-15 | What persistence and recovery semantics are required when a birth or protected-resource update is interrupted? | Stage 2 integration | Real-resource Stage 2 |
| OQ-16 | What is the canonical lifecycle of a child whose birth is authorised but whose execution never becomes ready? | Stage 2 integration | Canonical birth semantics |
| OQ-17 | What mandatory hereditary constitutional property can Fitrah enforce that cannot be represented equivalently as ordinary capability attenuation or delegated authorization? | 2026 prior-art review + OQ-06 ablation | Core novelty claim |
| OQ-18 | In a direct ablation against a modern attenuated delegation broker, what invalid birth, lineage or lifecycle state does Fitrah exclude that delegation-only enforcement permits? | 2026 prior-art review | Paper contribution |

# Prior Art Matrix: Fitrah and Agent Trust Systems

Status: working novelty review, 18 October 2026. This matrix does not establish novelty.

| Work / family | Untrusted model assumption | Recursive attenuation | External enforcement | Identity / provenance | Controlled birth as validity transition | Mandatory hereditary constitutional state | Instance attestation | Population constraints |
|---|---|---|---|---|---|---|---|---|
| Macaroons / Biscuit / UCAN / SPKI / capabilities | not AI-specific | strong | verifier/resource dependent | delegation provenance varies | no | no | no | no |
| Delegation Without Trust (2026) | explicit | strong | authorization broker | sender-constrained identity/tokens | sub-agent delegation, not birth validity | no | no primary contribution | no |
| Agent Identity Protocol (AIP) | explicit security framing | strong; no hop widens authority | relying-party verification | strong chain/provenance | delegation chain, not Fitrah birth semantics | no | composes with workload identity | limited |
| IETF AIMS / WIMSE | treats agent as workload | standards composition | yes | workload identity + OAuth | no dedicated autonomous birth primitive | no | can compose with workload credentials/attestation | no |
| NIST agent identity project | risk-driven | delegation is in scope | yes | identity, authorization, audit | open question, not primary primitive | no | asks about hardware/software binding | open |
| Proof-Carrying Agent Actions | planner-independent checker | action-local, not lineage | explicit pre-execution certificate gate | not primary focus | no | no | no | no |
| SPIFFE / SPIRE | application logic untrusted by identity layer | not authority attenuation itself | identity substrate | mature workload identity and process attestation | registration/attestation, not autonomous birth | no | strong workload attestation | no |
| DICE / RATS family | measured software/hardware | no | verifier/relying party | measured identity/evidence chain | no autonomous-agent birth | no | strong | no |
| Fitrah target | explicit | strong | runtime/resource mediation | signed birth + lineage; stronger instance binding later | **yes** | **yes** in Lab 0 | planned using established attestation concepts | S70 then later population invariants |

## Findings

`[FACT]` Capability attenuation, delegated authorization, workload identity and attestation are established mechanisms. They must not be presented as Fitrah inventions.

`[EVIDENCE]` 2026 work has moved the untrusted-model assumption and compromised-subagent confinement into mainstream agent-security research. In particular, *Delegation Without Trust* implements an external authorization broker and evaluates 2,000 randomized compromised-subagent scenarios.

`[EVIDENCE]` AIP explicitly specifies that delegated authority carried across an agent chain must not widen at any hop. This overlaps materially with Fitrah F2/F2h.

`[EVIDENCE]` AIMS explicitly recommends composing existing workload-identity and OAuth standards rather than creating isolated agent identity mechanisms. Fitrah should follow that principle.

`[EVIDENCE]` Proof-Carrying Agent Actions shows a planner-independent certificate checker gating tool execution. This is adjacent to Fitrah's future goal of independently checkable birth/lineage/action evidence.

`[HYP]` The less crowded Fitrah research question is whether **authorised birth itself** can be a security transition that simultaneously establishes mandatory hereditary constitutional state, a non-amplifying authority ceiling, lineage evidence and eventually a bound execution instance.

`[LIMITATION]` Lab 0's current core language is too weak to establish that constitutional inheritance contributes something beyond capabilities. Stage 1B OQ-06 already showed semantic strengthening largely collapses into capability attenuation in this model.

## Research consequences

1. Do not claim novelty for bounded delegation, external authorization, workload identity, attestation or proof-carrying action checks individually.
2. Reuse mature primitives where appropriate: Biscuit/macaroons-style attenuation, SPIFFE/WIMSE-style workload identity, and DICE/RATS-style attestation.
3. Focus theoretical work on what hereditary constitutional state expresses that a capability token cannot.
4. Treat birth, lineage continuity and birth-to-execution binding as the candidate distinctive lifecycle.
5. Add a comparative experiment: broad bearer authority vs attenuated delegation broker vs Fitrah authorised birth and hereditary constraints. The key question is what additional attack or invalid state Fitrah excludes.
6. Later extend from per-agent invariants to population invariants, especially collusion and distributed composition.

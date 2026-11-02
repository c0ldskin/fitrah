# Fitrah Research Foundation

Source: Fitrah Foundation Note 0.4 (17 October 2026), initiated by Zeeshan Mehdi.
Status: exploratory research specification. This file is the Markdown working copy of the baseline; where it departs from the Note, the departure is recorded in `changelog.md` and proposed in `papers/references-to-formal-document.md`.

## Statement types

Every material statement in this repository carries one of these tags.

| Tag | Meaning |
|---|---|
| `[FACT]` | Known, stable fact (definitions, established systems) |
| `[EVIDENCE]` | External evidence from a cited source |
| `[HYP]` | Hypothesis under test |
| `[CHOICE]` | Implementation or modelling choice; could reasonably be different |
| `[RESULT]` | Experiment result, with run identifier |
| `[PROOF]` | Mathematical proof or proof sketch, with scope stated |
| `[ASM]` | Security assumption (see `assumptions.md`) |
| `[OPEN]` | Open question (see `open-questions.md`) |

Words such as "proved", "guaranteed", "immutable" and "secure" are only used with scope and assumptions attached.

## 1. Research problem

`[EVIDENCE]` Agents are gaining longer autonomous task horizons (METR), controlled evaluations have observed unsanctioned and coordinated agent behaviour (UK AISI), and standards bodies treat agent security as a distinct problem (NIST AI 800-5). See `bibliography.md` [7] to [13].

`[HYP]` Some trust properties can be bound to an agent at creation and remain enforceable through execution, delegation, reproduction and migration, without depending on the agent choosing to obey them.

`[FACT]` The Note does not claim that morality is computable, that software has conscience, or that cryptographic identity establishes intent.

## 2. Working research question

Can an autonomous agent be "born" with a verifiable set of non-removable trust invariants that constrain its executable authority, survive authorised evolution, and are inherited by descendants, without requiring a single model vendor or agent framework?

## 3. Phase 1: hereditary trust

`[HYP]` Phase 1 claim: a valid Fitrah child agent cannot be born without the mandatory core DNA, cannot modify that core through an authorised execution path, and cannot receive more protected authority than its parent was authorised to delegate.

Phase 1 addresses Layer 2 only (Digital DNA and inherited authority). Layers 3 to 5 are deferred until Lab 0 is stable.

## 4. Agent model

`[CHOICE]` For Lab 0, an agent is modelled as the tuple A = (I, D, C, Dg, M, R, L):

- I, identity of the running instance
- D, Digital DNA: constitutional core, integrity commitments, mutation rules
- C, exercisable capabilities
- Dg, capabilities the agent is authorised to delegate to descendants
- M, mutable cognition: model, prompt, memory, plans
- R, runtime: the mechanism that enforces deterministic constraints on protected actions
- L, lineage: ancestry, issuer, parent, attestation evidence

`[CHOICE]` Separating C from Dg is deliberate: the ability to exercise authority and the ability to confer authority are different properties.

`[ASM]` M is outside the trusted core. No deterministic claim may depend on M behaving honestly. (ASM-01)

Note: in this tuple R is listed as a component of the agent. For security analysis R must not be agent-controlled state; see `threat-model.md` section 2 and OQ-03.

## 5. Model behaviour versus runtime guarantee

These are separate research questions and are measured separately in every experiment.

- Question A: does the AI choose to behave safely? Measured as proposal and refusal rates. Probabilistic.
- Question B: can the runtime prevent a prohibited action when the AI does not? Measured as completed violations. Must hold with the model removed.

`[FACT]` Prompts, system instructions, model refusals and LLM judges are not treated as deterministic security controls in this project.

## 6. Layering hypothesis

`[HYP]`
1. Behavioural disposition (model-level tendencies)
2. Digital DNA and inherited authority  ← Phase 1
3. Cryptographic identity and lineage
4. Execution trust (identity bound to measured or attested runtime)
5. Inter-agent trust and federation

## 7. Positioning after the evidence review

`[EVIDENCE]` Industry is converging on agent identity and deterministic runtime policy (Microsoft Agent Governance Toolkit, Entra Agent ID, Google Cloud agent IAM). A Fitrah implementation that amounts to a policy gateway or registry is not frontier research. (Note sections 17.6 and 18)

`[EVIDENCE]` Attenuated, delegable capabilities with caveats that cannot be removed by the holder already exist in object-capability systems and token formats such as macaroons, Biscuit and UCAN (added in this repository; see `bibliography.md` [31] to [38]). This is a direct prior-art threat to Lab 0's bounded inheritance and mandatory inheritance properties taken in isolation.

`[HYP]` Candidate novelty, still to be established: the composition of (a) a mandatory constitutional core that constrains actions, not only authorisation, (b) control over the creation path itself so that unregistered descendants hold no protected authority, (c) verifiable lineage, and later (d) binding to an attested runtime, with stated guarantees that survive recursive delegation and model replacement.

## 8. External expert challenge (clone problem)

`[EVIDENCE]` (expert feedback, Note section 22) A signed identity is insufficient if an attacker can copy the agent and present the same credentials elsewhere. Future work must bind identity, DNA, private key, measured runtime and TEE so that a relying party can distinguish the authorised instance from a copy.

`[CHOICE]` Blockchain is not assumed. Soulbound-style non-transferable credentials are an optional pattern.

## 9. Research sequence

- Lab 0: hereditary trust in a deterministic local simulation
- Lab 1: cryptographic identity and lineage; forgery and replay tests
- Lab 2: clone resistance and attestation
- Lab 3: independent verification by relying parties
- Later: intrinsic behaviour, kept separate from deterministic enforcement

## 10. Non-claims

Fitrah does not currently prove moral behaviour, does not assume identity establishes intent, does not claim model conscience, does not assume every ethical principle reduces to a rule, and does not yet establish novelty over capability security, attestation, formal methods or agent-governance systems.


## 11. Evidence status after Stage 1B and Stage 2 preparation

`[RESULT]` Stage 1B found no counterexample for the correct runtime in lineages to 100 generations, 2,000 generated histories covering 100,000 transitions, or the complete bounded state space examined (6,742 reachable states; 459,386 transitions). These are bounded results, not general proofs.

`[RESULT]` In the dedicated Hyper-V Stage 2 environment, a disconnected prerequisite run achieved P01-P09 PASS / READY. S65 showed that process-group termination alone is insufficient while the cgroup-v2 containment boundary terminated all tested descendants after fork, double fork, setsid and new-process-group escape attempts.

`[RESULT]` A synthetic filesystem integration pilot passed under the isolated VM boundary and fresh prerequisites, but this is deliberately narrower than canonical S60-S64/S70 and does not establish real-resource integration.

`[COUNTEREXAMPLE]` TC-27 demonstrated that an evidence-write failure could leave an allowed state change without the corresponding evidence record. The detected in-process path has been repaired and regression-tested. Crash durability and multi-file transaction semantics remain separate questions.

`[HYP]` TC-28 proposes versioned transactional generations for registry, resource and evidence state. Prototype interruption tests support whole-generation publication within the tested fault model, but there is no power-loss durability proof and the design is not yet the canonical runtime store.

`[CHOICE]` TC-29 experimentally commits authorised birth before child execution. A startup failure therefore retains the birth record and records failure/death rather than erasing lineage history. This remains experimental pending broader lifecycle review.

`[RESULT]` The first guarded resource-backed VM demonstration passed fresh P01-P09 and S65 prerequisites but returned INVALID_RUN after AUTHORIZED_BIRTH followed by STARTUP_FAILURE. Cleanup was confirmed and no workload action occurred. A launch-readiness race is currently only a hypothesis.

The research question has therefore progressed from whether hereditary trust can be stated and enforced in a deterministic transition system to whether the same properties survive hostile code, operating-system boundaries, persistent protected resources and failure-prone birth/execution lifecycles.


## 12. Prior-art update: 2026 convergence and narrowed novelty target

`[EVIDENCE]` Current 2026 work materially overlaps several Fitrah mechanisms. *Delegation Without Trust* adopts an explicit untrusted-model assumption and an external authorization broker for compromised sub-agent confinement. AIP specifies multi-hop delegation where authority must not widen at any hop. IETF AIMS recommends composing established workload identity and OAuth mechanisms rather than reinventing agent identity. NIST's agent-identity programme is likewise focused on identity, authorization, delegation, accountability and non-repudiation. Proof-Carrying Agent Actions demonstrates planner-independent action certificates checked before execution. See `bibliography.md` [42] to [49] and `prior-art-matrix.md`.

`[FACT]` These findings narrow Fitrah's defensible research target. Bounded delegation, external runtime authorization, workload identity, attestation and proof-carrying action checks are not individually candidate novel contributions.

`[LIMITATION]` Stage 1B already showed that under the current Lab 0 policy language, semantic core strengthening largely collapses into ordinary capability attenuation. If Digital DNA remains only an allow/deny capability mask, its research contribution beyond existing capability systems is weak.

`[HYP]` The candidate distinctive question is therefore lifecycle-level: whether **authorised agent birth** can be treated as a security transition that binds mandatory hereditary constitutional state, a recursively non-amplifying authority ceiling, verifiable lineage and eventually a particular attested execution instance.

`[CHOICE]` Future implementation should reuse mature primitives where they fit rather than rebuild them. Capability-token attenuation, workload identity and attestation should be treated as substrates that Fitrah composes around birth and lineage semantics.

`[OPEN]` The next formal-model question is what hereditary constitutional state can express that cannot be reduced to an attenuated capability token. Candidate classes include constraints on reproduction, mandatory evidence, lineage validity, mutation rules and future state/trajectory properties.

`[ABLATION]` A future comparison should evaluate: broad bearer authority versus a state-of-the-art attenuated delegation broker versus Fitrah authorised birth plus hereditary constraints. If Fitrah excludes no additional invalid state or attack, that is evidence against the stronger research claim.


## 13. Research direction after TC-30 to TC-32

`[CHOICE]` The project name Fitrah is an intellectual inspiration from the Islamic concept of an innate created nature. Fitrah does not equate machine state with the theological concept of human fitrah and makes no claim that software rules establish morality, iman, conscience or free will.

`[HYP]` The engineering analogue is hereditary constitutional nature: a machine lineage may be constructed so that every valid descendant necessarily carries a mandatory substrate inherited from its root while mutable cognition can diverge arbitrarily.

> Can an autonomous machine lineage be created such that every valid descendant necessarily inherits an irreducible constitutional substrate from its root, regardless of what its learned cognition becomes, and such that no descendant can exercise protected authority outside that hereditary chain?

`[FACT]` TC-30 and TC-31 established important negative boundaries for this hypothesis. Rich caveated authorization and an equivalent trusted birth or registration state machine can reproduce the current bounded validity model. TC-32 further shows that portable lineage evidence itself is not a distinguishing primitive in the tested model.

`[DECISION]` TC-32 is accepted as a positioning constraint: Fitrah will not claim portable lineage or provenance itself as a novel primitive.

`[HYP]` The research target therefore moves from representing inherited rules to making hereditary constitutional state a condition of valid authority-bearing existence. The candidate systems contribution is to couple, under hostile execution:

1. authorised birth;
2. mandatory hereditary constitutional state;
3. protected authority and protected state;
4. durable evidence of the birth and lifecycle transition; and
5. later, a specific measured or attested execution instance.

The intended distinction is not that an invalid process cannot physically exist. It is that an unregistered or constitutionally invalid process cannot become a valid authority-bearing descendant within the protected trust domain.

`[LIMITATION]` This distinction is not yet established as novel or uniquely achievable by Fitrah. E6 showed that an equivalently designed trusted state machine can match current abstract semantics. The next experiments must therefore test the composition under hostile execution and instance binding, rather than continue relabelling authorization predicates.

### Direction for future AI collaborators

When extending Fitrah:

- do not search for novelty in capability attenuation, caveats, registration, signed lineage or attestation individually;
- preserve the separation between mutable cognition and hereditary constitutional substrate;
- treat the root constitution as trusted genesis for the current research scope;
- focus near-term experiments on whether birth, constitutional inheritance, evidence, protected state and execution-instance binding can remain inseparable under adversarial code and failure;
- record any proposal that changes what "valid descendant" means as a TC finding before modifying canonical invariants.

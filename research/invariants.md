# Fitrah Invariants

Status: candidate. Nothing in this file is a proof of the implementation. Proof sketches are proofs about the abstract model in section 2 only, under the assumptions cited.

Foundational invariants are not modified silently. The original wording from Foundation Note 0.4 is kept verbatim where useful for traceability. Refinements accepted for Lab 0 are marked `ACCEPTED` and recorded in `changelog.md`.

## 1. Naming conflict in Note 0.4 (must be resolved)

`[FACT]` Note 0.4 uses the labels F1 to F3 twice with different meanings.

| Label | Section 2A ("proof obligations") | Section 4 ("candidate invariants") and Project Prompt |
|---|---|---|
| F1 | Core tamper resistance | Core integrity, D_core(A_t) = D_core(A_0) |
| F2 | Mandatory inheritance | Bounded inheritance, C_child ⊆ Delegable(C_parent) |
| F3 | No privilege amplification | Authorised execution, Execute(a) ⇒ Permitted(a, D, C) |

`[CHOICE]` This repository uses the section 4 labels (F1 to F6) as canonical invariant identifiers, and gives the three Lab 0 tests their own labels L1 to L3. Mapping:

| Lab 0 obligation | Test | Invariants it exercises |
|---|---|---|
| L1 Core tamper resistance | Tamper Test | F1 |
| L2 Mandatory inheritance | Inheritance Test | F4 (with ValidDNA refined, below) and F1h |
| L3 No privilege amplification | Privilege Escalation Test | F2, F2h |

`[FACT]` Mandatory inheritance (L2) is not expressed by any formula in section 4 as written. F1 only compares an agent with its own earlier state; F4 depends on an undefined predicate ValidDNA. This is the most important gap found in the baseline.

## 2. Abstract model for Lab 0

`[CHOICE]` State of the system is a finite set of agent records held by the runtime R (not by the agents):

```
Agent a:
  id(a)        unique, assigned by R
  parent(a)    id of parent, or ⊥ for the root
  core(a)      finite set of unique core rules (the mandatory DNA)
  mut(a)       mutable DNA fields (strategy notes, memory pointer)
  C(a)         exercisable capabilities, a finite set of (resource, action) pairs
  Dg(a)        delegable capabilities, a finite set of (resource, action) pairs
  status(a)    alive | dead
```

Capabilities form the powerset lattice over (resource, action) pairs, ordered by ⊆. `[CHOICE]` Lab 0 uses flat pairs; richer attenuation (caveats on time, arguments, purpose) is deferred.

Well-formedness:

- W1: Dg(a) ⊆ C(a). `[CHOICE]` A parent may only delegate what it can itself exercise. The alternative (delegate-only authority, as with some brokers) is recorded as OQ-07.
- W2: the root is created only by R from a genesis configuration. `[ASM]` ASM-04.

Transitions (the only state changes R implements):

| Transition | Requested by | Effect if accepted |
|---|---|---|
| `spawn(p, core', C', Dg')` | agent p | new agent q with parent p |
| `mutate(a, field, value)` | agent a | updates `mut(a)` only |
| `invoke(a, action, resource)` | agent a | performs a protected action |
| `kill(a)` | agent a or R | status(a) := dead |

`[CHOICE]` In Lab 0 there is no transition that writes core(a), C(a) or Dg(a) after birth. Revocation (F6) is deferred to Lab 0b, where it may only remove.

`[CHOICE]` Self-termination via `kill(a)` is deliberately not capability- or policy-gated in Lab 0 because it only removes that agent's authority. Any future transition that lets one agent terminate another must be modelled as a protected action.

## 3. Invariants

### F1 Core integrity

Original (Note 0.4): D_core(A_t) = D_core(A_0). "The agent cannot modify its own foundational constitutional core through an authorised agent action."

Plain English: whatever an agent does through the runtime, its core at any later time equals its core at birth.

`[PROOF]` (abstract model only) No transition in section 2 writes core(a) after birth, so F1 holds by inspection of the transition relation. Scope: this is a statement about R's transition relation, not about the agent. It is only as strong as the claim that the agent has no path to R's state other than these transitions (ASM-02, ASM-03).

`[FACT]` Because F1 is trivially true of any runtime with no core-write operation, a passing Tamper Test in Lab 0 carries little evidential weight by itself. The meaningful test is whether any unenumerated path writes R's state (Lab 0 stage 2, `threat-model.md` A1).

ACCEPTED F1h (hereditary core, Lab 0): for every valid agent a with root r, core(a) = core(r).

Plain English: every valid descendant carries exactly the root's core.

`[CHOICE]` Equality rather than superset. Cores are mathematical sets of unique rules; duplicate rules are malformed input rather than distinct DNA. Stage 1B's OQ-06 ablation found that semantic "strengthening" collapses to capability attenuation in the current Lab 0 model and can even classify the empty core as strongest, so exact hereditary equality remains the canonical Lab 0 choice. OQ-06 remains open for richer future policy languages.

### F2 Bounded inheritance

Original: C_child ⊆ Delegable(C_parent).

ACCEPTED reading for Lab 0: C(q) ⊆ Dg(p) where p = parent(q), with Dg as an explicit field distinct from exercisable capability C.

ACCEPTED F2h (transitive attenuation): Dg(q) ⊆ Dg(p).

Plain English: a child can only be given what its parent was allowed to hand on, and can only hand on a subset of that in turn.

`[FACT]` F2 as written does not constrain what the child may delegate. Without F2h (or W1 plus F2, from which it follows), a parent could give a child a small C but a large Dg, and a grandchild could then exceed the child. This is the re-delegation amplification path; scenarios S32 and S33 test it.

`[PROOF]` (abstract model, sketch) From W1 and F2: Dg(q) ⊆ C(q) ⊆ Dg(p) ⊆ C(p). By induction on lineage depth, for every valid agent a with root r, C(a) ⊆ C(r). Hence no valid descendant holds a capability its root did not hold. Depends on: C and Dg not changing after birth (Lab 0 choice), and every agent being created by `spawn` (ASM-03).

`[OPEN]` Collusion: two siblings each within bounds cannot combine capabilities in this model because capabilities are not transferable between agents. If transfer or message passing of authority is added, F2 must be restated over the whole population (OQ-09).

### F3 Authorised execution

Original: Execute(a) ⇒ Permitted(a, D, C).

ACCEPTED Lab 0 definition:

`Permitted_0(a, x) := Alive(a) ∧ x ∈ C(a) ∧ Policy_0(core(a), x) = ALLOW`

where `Policy_0 : Core × Action → {ALLOW, DENY}` is deterministic and total for the Lab 0 action space.

`[CHOICE]` Lab 0 uses **explicit allow** semantics: `Policy_0` returns ALLOW only when the inherited core contains an applicable allow rule and no applicable deny rule overrides it. Absence of a rule is DENY. This is intentional: the constitutional core is an affirmative authority boundary, not merely a blacklist.

Plain English: an action happens only if the agent is alive, holds the capability, and the deterministic Lab 0 policy derived from the core explicitly allows it. This avoids equating the mere absence of a prohibition with moral permission. `Permitted_0` is a deliberately narrow runtime predicate, not a definition of moral permissibility.

`[ASM]` F3 only covers actions that reach the protected resource through R. If the resource is reachable by any other path, F3 says nothing (ASM-05).

### F4 Valid birth

Original: Born(A) ⇒ ValidDNA(A) ∧ ValidIdentity(A).

ACCEPTED decomposition for Lab 0:

- `ValidDNA(q, p)` iff `core(q) = core(p)` (F1h), `C(q) ⊆ Dg(p)` (F2), and `Dg(q) ⊆ C(q)` (W1).
- `AuthorizedBirth(p, q)` iff `Alive(p)`, `(spawn, R) ∈ C(p)`, `Policy_0(core(p), (spawn, R)) = ALLOW`, and `ValidDNA(q, p)`.
- `ValidIdentity(q)` iff `id(q)` was assigned by R and a birth record for q, signed by R, exists in the evidence log. `[CHOICE]` In Lab 0 identity is channel-bound; cryptographic instance identity is Lab 1.

Lab 0 therefore refines F4 as:

`Born(q) ⇒ AuthorizedBirth(parent(q), q) ∧ ValidIdentity(q)`

This separation keeps structural DNA validity distinct from the parent's authority to create a child and from the identity evidence attached to that child.

`[CHOICE]` A spawn request that fails `AuthorizedBirth` is rejected as a whole; no partially valid child is created and no capabilities are silently trimmed. Trimming would turn a violation into a quiet success and hide the attempt from the metrics.

`[CHOICE]` Mutable-state changes are also policy-governed Lab 0 actions. A request to change `mut(a)` is accepted only if the agent is alive, `(mutate, self) ∈ C(a)`, the target field is designated mutable, and `Policy_0(core(a), (mutate, self)) = ALLOW`. This makes mutation attenuable per agent rather than inherited solely through the shared core, while preserving F1 by keeping `core`, `C` and `Dg` non-mutable.

### F5 Audit non-repudiation

Original: Commit(a) ⇒ AppendOnlyEvidence(a).

`[CHOICE]` Lab 0 needs this for success criterion 5 (every enforcement event reproducible and logged). Implemented as a hash-chained JSONL log written only by R, with each entry signed by R's Ed25519 key. `[ASM]` Append-only is only as strong as the agent's lack of write access to the log file (ASM-06). Real append-only evidence (transparency log, WORM storage) is deferred.

### F6 Revocable authority

Original: Revoked(c) ⇒ ¬Usable(c).

`[CHOICE]` Deferred to Lab 0b. `[OPEN]` Whether revoking a capability from a parent must cascade to descendants that received it (OQ-08). Without cascade, F2 can be violated over time: C(q) ⊆ Dg(p) held at birth but not after p loses authority.

## 4. What the Z3 and TLA+ checks are for

`[CHOICE]` The induction in F2 is small enough to check by hand; Z3 adds little at Lab 0 size. TLA+ becomes worthwhile when Lab 0b adds revocation and concurrent spawn, where interleavings matter. Recommended: a TLA+ model of section 2 plus revocation, model-checked with TLC for small populations (3 to 5 agents, depth 3), before Lab 0b code.

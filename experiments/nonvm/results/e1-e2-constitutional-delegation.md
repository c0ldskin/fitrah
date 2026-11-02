# E1/E2 Findings: Constitutional State versus Delegation

Status: bounded non-VM result, 18 October 2026.

## Scope

This experiment compares abstract authorization models only. It makes no VM, operating-system or cryptographic-attestation claim.

## E1 result

`[RESULT]` A simple delegation-only model that checks only `C(child) subset_of Dg(parent)` accepts many states that Fitrah rejects for non-authority reasons such as missing authorised parent, broken lineage, absent birth evidence or invalid lifecycle ordering.

That difference by itself is **not** a strong novelty result.

`[LIMITATION]` Once the comparison baseline is allowed modern contextual caveats or predicates over trusted facts, the tested birth/lineage predicates can be represented as authorization conditions. For example, a resource can require both the attenuated capability and predicates such as `valid_birth=true`, `lineage_ok=true` and `instance_ready=true`.

Therefore this experiment did **not** establish that Lab 0 Digital DNA is more expressive than a sufficiently rich capability/delegation system.

`[COUNTEREXAMPLE TO A STRONGER NOVELTY STORY]` The existence of two agents with identical current executable authority but different Fitrah birth validity demonstrates a semantic distinction, but not necessarily an expressiveness distinction: a caveated authorization system can condition resource access on the same trusted birth-validity fact if that fact is supplied and enforced externally.

## E2 result

The three bounded systems behave as expected:

A. broad bearer authority permits authority amplification;
B. attenuated delegation blocks authority amplification;
C. Fitrah attenuation plus birth/lineage validity blocks amplification and also rejects invalid birth/lifecycle states.

However:

`[ABLATION]` If system B is strengthened with equivalent trusted birth/lineage predicates, the behavioral difference with C largely disappears in the bounded authorization model.

## Interpretation

`[TC CANDIDATE TC-30]` Fitrah's defensible contribution should not be framed as greater logical expressiveness than modern caveated authorization systems unless a future formal result establishes such a difference.

The stronger candidate is **mandatory construction/lifecycle semantics**: a descendant is not merely a principal holding an attenuated credential; its valid existence, lineage continuity, constitutional state and activation are coupled through an authorised birth transition and later bound to an execution instance.

This is a proposed theoretical narrowing, not an accepted change to the canonical model.

## Next test implied by TC-30

A fair baseline must implement a modern delegation broker with:
- recursive attenuation;
- contextual caveats;
- trusted identity/provenance facts;
- birth/lineage predicates where the broker is allowed to consume them.

Then ask whether Fitrah still excludes states that the broker cannot exclude **without becoming equivalent to a Fitrah-style birth-state machine**.

That is a stronger falsification test than comparing against a capability subset check.

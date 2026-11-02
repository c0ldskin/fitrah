# E6 Findings: Strong Delegation-Broker Ablation

Status: bounded non-VM result, 18 October 2026.

## Question

Does Fitrah exclude a state that remains reachable under a strong modern authorization baseline when that baseline is allowed both rich contextual caveats and an equivalent trusted registration/birth state machine?

## Model

The finite model enumerated 256 combinations of:

- parent authorised;
- lineage valid;
- hereditary core valid;
- authority attenuation valid;
- birth evidence present;
- registered;
- ready;
- alive.

B1 is a rich broker that can gate protected actions using all trusted predicates.

B2 adds a trusted registration/birth state machine:
- registration requires valid parent, lineage, core, authority and birth evidence;
- READY requires registration;
- alive instance requires registration.

F applies the same bounded validity predicates as the current abstract Fitrah birth/lifecycle model.

## Result

`[RESULT]` 256 abstract states examined.

`[RESULT]` B2 valid states: 36.

`[RESULT]` Fitrah valid states: 36.

`[RESULT]` States valid only in B2: 0.

`[RESULT]` States valid only in Fitrah: 0.

Therefore the bounded state sets are observationally equivalent under the predicates represented in this experiment.

## Interpretation

`[NEGATIVE RESULT]` This experiment found **no state-level distinction** between current Fitrah birth/lifecycle validity and a sufficiently strong delegation system once that baseline is allowed an equivalent trusted registration/birth state machine.

This does not show that all future Fitrah models are equivalent to delegation systems. It shows that the **current bounded abstraction does not yet demonstrate a uniquely enforceable property**.

`[TC CANDIDATE TC-31]` The research contribution should not be claimed merely from combining attenuation with a registration/birth state machine. A paper-quality contribution now requires at least one of:

1. a formally distinct hereditary property that the comparison baseline cannot reproduce without becoming semantically identical to Fitrah;
2. a new theorem or compositional guarantee about recursive birth/lineage;
3. a systems result showing a meaningful security property emerges from the composition under hostile execution;
4. a new lifecycle/attestation construction with measurable advantage over equivalent prior-art composition.

Otherwise Fitrah may be best characterised as a disciplined composition and experimental framework rather than a new trust primitive.

## Important distinction: B1 versus B2

B1 can make an invalid descendant powerless while still allowing that process/principal to exist.

Fitrah treats invalid birth as an invalid lineage state.

That semantic difference disappears at the observable valid-state level once B2 is allowed to add the same trusted birth/registration semantics.

Therefore **"birth versus delegation" alone is not enough** if the baseline may compose an equivalent state machine.

## Limitations

- finite Boolean abstraction;
- no time, concurrency, revocation or migration;
- no cryptographic token details;
- no hostile OS execution;
- no richer future constitutional language;
- equivalence here is bounded model equivalence, not a general theorem.

## Reproducibility

Runner: `experiments/nonvm/e6_strong_broker.py`.

Expected summary:
- 256 states;
- 36 B2-valid states;
- 36 F-valid states;
- zero distinguishing states in either direction.

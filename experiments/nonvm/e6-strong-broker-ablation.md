# E6: Strong Delegation-Broker Ablation

Status: approved after TC-30 review, 18 October 2026.

## Research decision

TC-30 is accepted as a positioning constraint:

Fitrah does not currently claim greater authorization-language expressiveness than a sufficiently rich caveated delegation system.

The candidate contribution is instead tested at the lifecycle level: authorised birth, lineage validity, mandatory hereditary constitutional state, activation semantics, and later execution-instance binding.

No accepted F1-F6 invariant changes in this decision.

## Baselines

### B1: Rich caveated broker

The broker may enforce:
- recursive authority attenuation;
- arbitrary contextual caveats over trusted facts;
- identity/provenance predicates;
- birth-validity predicates supplied by a trusted source;
- lineage-validity predicates supplied by a trusted source;
- readiness/instance predicates supplied by a trusted source.

It gates protected actions but does not itself define whether a process/principal validly exists.

### B2: Broker plus registration state machine

B1 plus a trusted registration/birth state machine that refuses to register invalid descendants and governs activation lifecycle.

This intentionally gives the baseline the strongest fair construction semantics.

### F: Fitrah lifecycle

Authorised birth is itself a validity transition coupling:
- parent authority;
- hereditary core;
- authority ceiling;
- lineage evidence;
- lifecycle state;
- later execution-instance binding.

## Questions

1. Can B1 reproduce Fitrah's protected-action decisions when given equivalent trusted facts?
2. Can B1 prevent an invalid descendant from existing, or only make it powerless?
3. Does B2 reach the same valid-state set as Fitrah once it adopts equivalent registration/lifecycle rules?
4. If B2 becomes observationally equivalent, what remains as a defensible Fitrah contribution: mechanism, composition, formalization, lifecycle semantics, or nothing distinguishable?

## Success / falsification criteria

A strong Fitrah-specific result requires at least one state or transition that:
- remains accepted/reachable under B2,
- is rejected/unreachable under F,
- and cannot be excluded by adding an equivalent trusted predicate or state-machine rule without importing the same Fitrah lifecycle semantics.

If no such case is found, record that negative result.

## Outputs

- deterministic enumerator/model;
- machine-readable summary;
- minimal distinguishing states if any;
- paper-facing interpretation;
- no novelty claim from mere renaming or composition.

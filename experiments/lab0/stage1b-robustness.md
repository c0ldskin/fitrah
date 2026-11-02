# Lab 0 Stage 1B: Robustness and Generalisation

Status: research extension to Stage 1 while the Stage 2 Hyper-V environment is being built.

Purpose: strengthen the eventual paper with evidence that the hereditary trust properties are not limited to a small set of hand-written scenarios.

Stage 1B remains deterministic and does not use arbitrary-code attackers, OS-isolation claims or an LLM. It must not be reported as Stage 2.

## 1. Research questions

Stage 1B asks:

1. Do the hereditary trust invariants remain intact across deep lineages rather than only shallow parent-child examples?
2. Do they survive large numbers of generated transition histories?
3. Can the independent verifier detect deliberately weakened enforcement logic?
4. Can any counterexample be found by exhaustive search over a bounded state space?
5. Optional ablation: what changes if a child may strengthen, but never weaken, its inherited core?

## 2. Experiment 1: deep lineage attenuation

Generate valid lineages with configurable depths, including at minimum 10, 50 and 100 generations.

For every descendant a_n verify:

```
C(a_n) subset_of Dg(a_(n-1))
Dg(a_n) subset_of C(a_n)
C(a_n) subset_of C(root)
core(a_n) = core(root)
```

At selected generations inject attempted privilege amplification, core mutation and invalid re-delegation.

Record:

- maximum lineage depth tested;
- number of valid births;
- number of injected violations;
- number blocked by R;
- number detected by the verifier;
- any counterexample.

## 3. Experiment 2: property-based generated histories

Add a reproducible generator for transition sequences over a small but non-trivial action space.

Generated operations should include:

- valid and invalid spawn;
- invoke;
- mutable-state mutation;
- attempted protected-field mutation;
- self kill;
- requests from dead agents;
- authority attenuation;
- attempted authority amplification;
- malformed requests.

Use fixed recorded seeds and enough generated histories to be meaningful for the paper. Prefer a property-based testing framework if it improves shrinking and counterexample reporting, but do not add a dependency merely for appearance.

Primary property:

> Every accepted transition must preserve the accepted Lab 0 invariants and well-formedness conditions.

The independent verifier must replay every generated run.

Record seeds, number of histories, number of transitions, and any minimal counterexample.

## 4. Experiment 3: systematic fault injection

Construct explicit defective runtime variants, each disabling one enforcement property at a time.

At minimum test defects equivalent to:

- skip core equality on birth;
- skip C(child) subset Dg(parent);
- skip Dg(child) subset C(child);
- skip Policy_0 on invoke;
- skip Policy_0 on spawn;
- skip mutate capability check;
- skip Policy_0 on mutation;
- trust claimed identity instead of channel identity;
- allow birth from a dead parent;
- omit or falsify birth evidence;
- break RT-01 rollback.

For each injected defect record:

- whether the defect produced an actual invariant violation;
- whether the independent verifier detected it;
- detection latency / sequence number if useful.

Report:

```
Verifier detection rate =
detected injected violations / actual injected violations
```

Do not count an injected defect that never manifests as a violation as a missed detection.

## 5. Experiment 4: bounded exhaustive state-space search

Build a small-state exhaustive model or enumerator over a bounded universe, for example:

- up to 3 registered agents;
- lineage depth up to 3;
- a reduced capability set;
- alive/dead state;
- spawn, invoke, mutate and kill transitions.

Search all reachable states and valid transition sequences within the bound for a counterexample to F1, F1h, F2, F2h, F3, F4 and W1 as represented in the Lab 0 model.

Preferred wording for a successful result:

> No counterexample was found within the complete bounded state space examined.

Do not call this a proof of the implementation or a proof of general security.

If a lightweight model checker or solver is clearly justified, use it. Otherwise a transparent enumerator is acceptable.

## 6. Optional Experiment 5: hereditary-core ablation

Do not change the canonical F1h model.

Create an isolated ablation comparing:

### Exact inheritance
```
core(child) = core(parent)
```

### Monotonic strengthening
A child may add restrictions but may not remove or weaken inherited restrictions.

The purpose is to study OQ-06: whether hereditary trust requires exact constitutional equality or permits strictly stronger descendants.

This must be labelled ABLATION / HYPOTHESIS and must not silently alter `research/invariants.md`.

Record any ambiguity in what constitutes a "stronger" rule set.

## 7. Cross-environment reproducibility

Where practical, compare Stage 1B semantic results between:

- Claude's Linux workspace;
- the researcher's WSL/Linux environment.

Do not require byte-identical artefacts across environments unless the format guarantees it. Compare invariant outcomes, verifier verdicts, state digests and recorded seeds.

## 8. Paper-facing outputs

Create:

- `experiments/lab0/results/stage1b-findings.md`
- machine-readable summary JSON;
- any generated seeds/counterexamples needed for reproducibility;
- tests for the experiment harness itself.

The findings document must distinguish:

- RESULT
- LIMITATION
- COUNTEREXAMPLE
- ABLATION
- OPEN QUESTION

The paper-facing summary should answer whether Stage 1B adds evidence beyond the 26 hand-written Stage 1 scenarios.

## 9. Research boundaries

Stage 1B must not:

- provision or modify the Hyper-V VM;
- use sudo or alter host security settings;
- run arbitrary-code Stage 2 attackers;
- change accepted invariants without a TC finding and research review;
- claim novelty or general AI safety;
- replace Stage 2.

If implementation reveals a contradiction in the accepted model, stop expanding that experiment, record the evidence as a TC finding, and request research review.

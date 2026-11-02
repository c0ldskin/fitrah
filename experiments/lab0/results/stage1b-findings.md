# Lab 0 Stage 1B: Robustness and Generalisation, Findings

Brief: `experiments/lab0/stage1b-robustness.md`. Machine-readable results: `stage1b.json` (all experiments) and `stage1b-ablation-oq06.json` (optional ablation). Stage 1B is deterministic, uses no arbitrary-code attackers, no OS-isolation claims and no LLM, and is not Stage 2.

Historical reproduction record (Python 3.11+, `pip install -r requirements.txt`):

```
PYTHONPATH=src python3 src/stage1b/run.py              # about 15 minutes on one core
PYTHONPATH=src python3 src/stage1b/ablation_oq06.py    # seconds
PYTHONPATH=src python3 -m pytest -q                    # original suite: 124 tests, about 30 seconds
```

Committed run: Python 3.13.16, cryptography 50.0.1, Linux x86_64. All parameters and seeds are recorded under `parameters` in `stage1b.json`.

The commands, timing estimates and 124-test annotation above describe the original execution, not the current checkout or the later hosted workflow's targeted suite. The historical all-tests command is not a current instruction to run Stage 2 tests outside their approved isolated environment. The current portable Stage 1B harness/automation target is:

```sh
PYTHONPATH=src python3 -m pytest -q tests/test_stage1b.py tests/test_stage1b_ci.py
```

The hosted quick and full runs in section 8 each report 73 passing tests for that target. The original runner records seeds and summary results while temporary per-history logs are overwritten. The newer cloud capture adapter retains individual signed logs, input histories, oracle traces and verifier reports in separate artifacts. These are distinct evidence-retention behaviours; quick mode remains smoke validation only.

Labels: `RESULT`, `LIMITATION`, `COUNTEREXAMPLE`, `ABLATION`, `OPEN QUESTION`, as the brief requires.

## 0. Summary for the paper

Stage 1 showed 26 hand-written scenarios behave as specified. Stage 1B asks whether that generalises, and adds four kinds of evidence the hand-written scenarios cannot give:

1. Inheritance holds along lineages of 100 generations, with every injected attack blocked.
2. Across 2,000 generated histories (100,000 transitions), R never accepted a request the independent reference model blocks, never produced the wrong effect, and never left a partial state change.
3. The independent verifier detected every violation produced by 12 of 13 deliberately broken runtimes. The 13th, a runtime that lies consistently, defines a limit of log-based verification.
4. An exhaustive search of a bounded model (up to three agents, 6,742 reachable states, 459,386 checked transitions) found no counterexample, while the same search found a counterexample within one or two steps for every injected defect.

Stage 1B also found four defects or gaps that the hand-written scenarios had not exposed: one conformance discrepancy in R, and three in the verifier. The verifier defects are fixed; the R discrepancy is for research review. That is the strongest argument that Stage 1B adds evidence rather than repeating Stage 1.

## 1. Method

`[RESULT]` (method) All experiments drive R's real decision and state code. `stage1b/direct.py` replaces only process launch with an in-process stub so millions of requests are feasible. `cross_check_process_path` replayed 50 generated histories through the real process path (one OS process per agent) and found decisions, reasons and state digests identical in all 50 (37 further histories skipped because they contain a simulated launch failure, which only the stub can produce).

Ground truth comes from `stage1b/reference.py`, a reference model written from `research/invariants.md` that shares no code with R. For every request it checks:

- R accepted something the model blocks;
- an allowed request had the wrong registry or vault effect;
- a blocked request changed state (RT-01);
- birth evidence disagrees with the registered record;
- any invariant over the whole registry broke: F1h, F2, F2h, W1, authority within the root's, F4 lineage.

Separately, the independent verifier replays every signed log. Generation is seeded and adaptive (requests are drawn against the live registry). Counterexamples are shrunk by delta debugging. No property-testing dependency was added.

## 2. Experiment 1: deep lineage attenuation

| Depth | Valid births | Attacks injected | Blocked by R (C) | Ground-truth violations (C) | Verifier (C) | Executed in A | Detected in A |
|---|---|---|---|---|---|---|---|
| 10 | 10 | 23 | 23 | 0 | clean | 23 | 23 |
| 50 | 50 | 54 | 54 | 0 | clean | 55 | 55 |
| 100 | 100 | 84 | 84 | 0 | clean | 87 | 87 |

`[RESULT]` At each injection generation the current tip tries:

- to give a child `write:vault`, which no ancestor may delegate;
- to give a child `delete:vault`, which the root holds but may not delegate;
- an invalid re-delegation (Dg outside C);
- a child with a weakened core;
- mutating its own core;
- self-escalating C;
- invoking delete;
- after attenuation, mutating without `(mutate, self)`.

`mutate:self` is dropped from the lineage at one third of the depth, and every later descendant lacks it (attenuation effective). For every descendant a_n the model checks `C(a_n) ⊆ Dg(a_(n-1))`, `Dg(a_n) ⊆ C(a_n)`, `C(a_n) ⊆ C(root)` and `core(a_n) = core(root)`.

In A, executed violations slightly exceed injected attacks because an executed attack makes some later requests violations too (for example, after a core is mutated, a canonical-core birth no longer matches its parent).

## 3. Experiment 2: generated histories

`[RESULT]` 2,000 histories of 50 requests (seeds 0 to 1999), 100,000 transitions, 29,500 accepted, 7,506 births, population up to 12 agents, lineage depth up to 6. Every reason code occurs (17 distinct), so every enforcement branch was exercised.

| Configuration C | Result |
|---|---|
| Accepted a request the model blocks, wrong effect, partial state, or broken invariant | 0 |
| Verifier accepts the log | 2,000 of 2,000 |
| Conformance differences with the model | 848, all caused by TC-22 (duplicate rules); 0 otherwise |

| Configuration A (same histories) | Result |
|---|---|
| Executed violations | 59,408 |
| Detected by the verifier | 59,408 (100%) |

Semantic digest over every recorded state digest in configuration C: `8df8d5876099b6c6a037e5aed8f994f910cbc8db091b75e4b300b557d4331769`. Another environment can compare this value instead of byte-identical artefacts (brief section 7).

## 4. Experiment 3: systematic fault injection

Thirteen defective runtimes, each disabling one property (`stage1b/defects.py`), run on 500 generated histories plus a 20-generation lineage. D05 and D07 run under the S25 and S14 fixture cores, because under the canonical core spawn and mutation are always allowed and the defects cannot manifest. A test proves that the defect-free copy of R is byte-identical in evidence to R.

| Defect | What it disables | Histories with a violation | Violating transitions | Detected | Max latency (entries) |
|---|---|---|---|---|---|
| D01 | core equality on birth | 388 | 773 | 773 | 0 |
| D02 | C(child) within Dg(parent) | 375 | 776 | 776 | 0 |
| D03 | W1 | 264 | 373 | 373 | 0 |
| D04 | Policy_0 on invoke | 428 | 1,250 | 1,250 | 0 |
| D05 | Policy_0 on spawn (S25 fixture) | 454 | 1,997 | 1,997 | 0 |
| D06 | (mutate, self) capability | 225 | 489 | 489 | 0 |
| D07 | Policy_0 on mutation (S14 fixture) | 473 | 1,920 | 1,920 | 0 |
| D08 | channel identity (trusts claimed `as`) | 195 | 268 | 268 | 0 |
| D09 | birth from a dead parent | 147 | 403 | 403 | 0 |
| D10a | birth evidence omitted | 458 | 1,894 | 1,894 | 0 |
| D10b | birth evidence falsified | 457 | 1,625 | 1,625 | 0 |
| D10c | birth evidence and state digest falsified consistently | 457 | 1,625 | 1,498 | 45 |
| D11 | RT-01 rollback | 64 | 73 | 73 | 0 |

`[RESULT]` Verifier detection rate = detected / actual violations = 13,339 / 13,466 (99.06%) overall; 11,841 / 11,841 (100%) for the twelve defects other than D10c. Twelve of thirteen defects are detected at the violating entry itself (latency 0).

`[LIMITATION]` D10c is a runtime that records a falsified birth and computes its state digest over the same falsified view, so the log is internally consistent. The verifier caught 1,498 of 1,625 such births, every time only later, when the child used authority the log said it did not have (median latency 2 entries, maximum 45). The 127 misses are children that never used their authority. Log replay checks that R's evidence is consistent with the rules; it cannot check that the evidence is true when R itself lies consistently. This is the expected consequence of R being in the TCB (`threat-model.md` section 2) and argues for evidence produced or witnessed outside R in later labs (Lab 1 signed identity, Lab 3 independent verification).

## 5. Experiment 4: bounded exhaustive state-space search

Bounded model (`stage1b/exhaustive.py`):

- up to 3 agents, so lineage depth up to 2;
- capability universe {read, delete, spawn, mutate};
- bounded root with C = universe and Dg = {read, spawn, mutate}, canonical core;
- every agent alive or dead; vault present or deleted.

From every reachable state, every agent, alive or dead, submits every request in a fixed family:

- invoke of each action, also with each other agent as a claimed identity;
- mutation of `mut`, core, C, Dg and status, and of other agents' records;
- self and cross kill;
- a malformed request;
- spawn with every C subset times every Dg subset (256 combinations), each attacker core variant, and the two program faults.

`[RESULT]` 6,742 reachable states, 459,386 (state, request) transitions checked, search complete (not truncated). 0 violations. 91 conformance differences, all TC-22.

Preferred wording, as the brief asks: no counterexample was found within the complete bounded state space examined. This is not a proof of the implementation or of general security.

`[RESULT]` Search power: the same search, run against each defective runtime and against baseline A, found a counterexample for every one. Minimal lengths are 1 request from genesis (D01 to D05, D07, D10a, D10b, D10c, D11, A) or 2 requests (D06, D08, D09, which need a second agent or a dead agent first). Counterexample paths are in `stage1b.json` under `experiment4_defect_counterexamples`.

## 6. Findings for research review

### TC-22 R compares cores as lists, the model defines them as sets (conformance; not applied)

`[COUNTEREXAMPLE]` (conformance, not an invariant violation). Minimal case: `spawn` with the parent's core plus a duplicate copy of K1. As a set it equals the parent's core, so `ValidDNA` holds and the model allows the birth; R compares the sorted list with duplicates kept and blocks it with CORE_MISMATCH (`test_TC22_duplicate_rule_core_is_blocked_by_R`). All 848 generated and 91 exhaustive conformance differences come from this, including the follow-on reason mismatches where R stops at CORE_MISMATCH before reaching a later check. `dna/model.py` says cores "compare as sets of rules", so the code also contradicts its own docstring. The verifier uses list equality too.

The direction is conservative (over-blocking), so no invariant is weakened. Options:

- (a) treat cores as sets in R and the verifier, deduplicating at birth;
- (b) reject duplicate rules as MALFORMED, so a core is always a set by construction;
- (c) declare cores to be lists.

(b) is the smallest change and keeps F1h a strict equality.

### TC-23 The verifier replayed claimed identity in configuration C (verifier defect; fixed)

Evidence: generated histories under the `mutate_denied` fixture. An allowed request carrying a claimed `as` that the channel's own agent was entitled to make: R correctly executed it as the channel, the verifier replayed it as the claimed identity, and so rejected a correct log ("recorded vault digest does not match replay"). S43's claimed write is always blocked, so Stage 1 never exercised this. Fix: the verifier honours a claim only when the signed genesis entry says the run is A or B. Regression test `test_TC23_verifier_uses_channel_identity_in_C` fails on the old verifier and passes on the fix. Stage 1 logs unchanged.

### TC-24 The verifier was incomplete against the accepted rules in four ways (verifier defect; fixed)

Evidence: baseline A over generated histories showed 166, then after a first fix 4, of 59,408 executed violations undetected. Each gap is a case the hand-written scenarios did not reach:

1. an accepted mutation or kill from a dead agent was not flagged;
2. an accepted write to a protected field was flagged only if the value changed;
3. in A, an effect executed under a claimed identity was replayed faithfully but not flagged;
4. authority was judged against the current state, which an unenforced or defective R may already have corrupted, so a later act using that corrupted authority went unflagged.

Fix: the verifier keeps a lawful-authority view (each agent's birth grant clipped by its parent's lawful authority, root from genesis) for every authority check, while still replaying the actual state for digests; it flags 1 to 3 directly. Four regression tests, each failing on the old verifier. After the fix: 59,408 / 59,408 detected in A, and 0 false positives on 2,000 correct-R logs and on fixture geneses. Stage 1 logs unchanged; `stage1.json` now records 31 verifier flags in A instead of 30 (S43's claimed write is now also flagged as an identity violation), and Stage 1 still passes.

### TC-25 Under explicit allow, K3 has no effect, so S10 attacks nothing semantically (observation; for review)

`[ABLATION]` evidence (`stage1b-ablation-oq06.json`, `K3_removal_changes_permissions: false`). The genesis core has no allow rule for delete, so under explicit-allow semantics delete is denied with or without K3. Removing K3, the attack S10 targets since decision TC-10, would not change any permission even if it succeeded. S10 still tests core immutability (any write is refused), but the weakening that matters is adding an allow, which S21 (K3 flipped to allow) covers. Options: keep K3 as documentation of intent, or make S10 attempt a semantic weakening such as adding `allow (delete, vault)`.

### TC-26 Log replay cannot detect a consistently lying R (limitation)

See section 4, D10c. Proposed wording for the paper: the verifier establishes that the evidence is internally consistent with the Lab 0 rules; it does not establish that the evidence is a true record when R is compromised.

### Stage 2 containment

Not part of Stage 1B. The containment design under review is TC-21 (`experiments/lab0/stage2-s65-design.md`), from the laptop session.

## 7. Optional experiment 5: hereditary-core ablation for OQ-06

`[ABLATION]` Label: ABLATION / HYPOTHESIS. F1h, R and the verifier are unchanged. Over all 1,024 subsets of a 10-rule pool (canonical K1 to K5 plus a write deny, an allow for delete overridden by K3, an allow for a new action, a read deny, and K3 flipped to allow), three candidate meanings of "the child core is at least as strong as the parent's" were compared:

| Definition | Cores accepted |
|---|---|
| exact (F1h as accepted) | 1 |
| syntactic: superset of the parent's rules, added rules all deny | 4 |
| semantic: every action the child allows, the parent allows | 320 |

Observations:

- Every syntactically stronger core is semantically stronger; 316 are semantically stronger but not syntactically. The two definitions are far apart, which is the ambiguity the brief asked to record.
- The semantic definition accepts the empty core, which allows nothing and so is "strongest", yet inherits no constitutional rule at all. Under that definition, mandatory inheritance becomes vacuous.
- Under explicit allow, semantic strength did not depend on the action space (adding an action no core names changed no verdict), because unknown actions are denied by default.
- `[OPEN QUESTION]` HYPOTHESIS tested: because `Permitted_0 = capability AND Policy_0`, a semantically stronger core gives exactly the effective authority obtained by narrowing C to the actions it allows. 6,400 randomised trials, 0 mismatches. If this holds in general, monotonic core strengthening adds no expressive power in Lab 0 beyond capability attenuation, and the value of the core lies in being mandatory and non-removable rather than in per-descendant tightening. That bears directly on OQ-05 and OQ-06.

## 8. Cross-environment reproducibility (updated 19 October 2026)

[RESULT] The original committed Stage 1B results were produced on Claude's Linux workspace (Python 3.13.16). A separate GitHub-hosted Ubuntu 24.04 / Python 3.12.15 run has now reproduced the **canonical full** Stage 1B workload at source commit `d14c6a2eaf9827afe9ac946d45ec8717ac3cdff8`: [Actions run 39284167068](https://github.com/c0ldskin/fitrah/actions/runs/39284167068). The job log reports 73 targeted tests passed, full experiment completion, 10,631 retained evidence cases replayed by the workflow's verifier, and zero verification errors. The [full artifact 12203401010](https://github.com/c0ldskin/fitrah/actions/runs/39284167068/artifacts/12203401010) was successfully uploaded (137,399,588 bytes compressed, GitHub-reported archive SHA-256 `bbee5df05313abb5c5df6be25c23d19a87c917defa534998c6bfda329c948a20`).

A separate [quick hosted smoke run 39282890148](https://github.com/c0ldskin/fitrah/actions/runs/39282890148) passed 73 targeted tests and verified 399 cases. The quick mode still performs the accepted bounded search but **is not** the 2,000-history full reproduction.

[LIMITATION] These results establish that the workflow executed and that its verifier reported no errors on the retained traces. The verifier is a separate first-party verifier process using the same project definitions, not an independent third-party implementation or external attestation. It does not independently enumerate the bounded model a second time; comparison with accepted counts is a coverage check. TC-22 and TC-26 remain. The contributing reviewer reports checking GitHub job logs and uploaded-artifact metadata in [PR #10's review comment](https://github.com/c0ldskin/fitrah/pull/10#issuecomment-6272816604), without downloading and independently auditing the entire full archive. That review reports expiry at `2027-01-17T16:16:34Z`; long-term external preservation and independent checksum validation are still needed. A subsequent editorial audit (kept in the private research record) distinguishes comparison with the supplied review transcript from direct access to Actions evidence.

[EVIDENCE] Stage 1 also had a separate successful hosted [run 39276979467](https://github.com/c0ldskin/fitrah/actions/runs/39276979467) at commit `91740062df0eef1c68202cb9c8e74aeab02ab82b`: 65 targeted tests passed, canonical execution completed, six-log independent verification passed, and evidence artifacts uploaded. This extends reproducibility infrastructure; it does not alter Stage 1B research conclusions.

## 9. Limitations

- `[LIMITATION]` The reference model is a second implementation of the same rules, written from the same documents. It catches divergence between R and the documents, not errors in the documents.
- `[LIMITATION]` The exhaustive search is bounded: three agents, a four-capability universe, one fixed request family. States are compared up to `mut` and vault contents, which no invariant reads.
- `[LIMITATION]` Generated histories are adaptive but drawn from a fixed request grammar. Behaviours outside it, such as concurrency, revocation and arbitrary code, are not covered. Those are Lab 0b and Stage 2.
- `[LIMITATION]` All Stage 1B logs use the committed Stage 1 test key (TC-05): signatures show mechanism, not provenance.

## 10. Does Stage 1B add evidence beyond Stage 1?

Yes, in three ways:

- **Scale.** 100,000 generated and 459,386 exhaustively enumerated transitions, against 26 scenarios, with no violation by correct R.
- **Power.** Every injected defect was both produced and caught, so the zero result is not an artefact of weak instruments.
- **Defects found.** It surfaced one conformance discrepancy in R (TC-22) and four verifier gaps (TC-23, TC-24) that the hand-written scenarios did not reach. It also produced an argued limit of log-based verification (TC-26), and an ablation result relevant to OQ-05 and OQ-06.

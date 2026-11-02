# Fitrah Research Changelog

Each entry states what changed, why, the evidence, and the affected assumptions and invariants. Entries marked PROPOSED change nothing foundational until the author accepts them.

## 0.4.0, 17 October 2026: repository created from Foundation Note 0.4

- What: research baseline restated as Markdown in `research/`; Lab 0 specification drafted.
- Why: Project Prompt v0.2, first task.
- Evidence: Foundation Note 0.4.
- Affected: none (baseline).

## 0.4.1, 17 October 2026: PROPOSED clarifications to invariants

1. Separate labels for Lab 0 obligations (L1 to L3) from invariants (F1 to F6).
   - Why: Note 0.4 uses F1 to F3 for two different sets (section 2A and section 4).
   - Affected: naming only.
2. Add F1h (hereditary core: core(a) = core(root)).
   - Why: mandatory inheritance, the Phase 1 headline property, is not expressed by any formula in Note 0.4 section 4.
   - Affected: F1, F4, L2.
3. Make Delegable an explicit field Dg with W1 (Dg ⊆ C) and add F2h (Dg(child) ⊆ Dg(parent)).
   - Why: F2 alone permits re-delegation amplification through grandchildren.
   - Affected: F2, L3, ASM-08.
4. Define Permitted (F3) so that core rules can forbid an action even when a capability grants it.
   - Why: otherwise the core adds nothing over capabilities (OQ-05).
   - Affected: F3.
5. Define ValidDNA and ValidIdentity (F4) for Lab 0.
   - Why: F4 used undefined predicates.
   - Affected: F4, L2.
6. Reject invalid spawns as a whole, never trim.
   - Why: trimming hides attempted violations from the metrics.
   - Affected: experiment design.

## 0.4.2, 17 October 2026: prior art added

- What: capability security and reference-monitor literature added as bibliography [31] to [41]; OQ-02 raised.
- Why: attenuated delegation with non-removable caveats (macaroons, Biscuit, UCAN, SPKI) already provides close analogues of F1h plus F2, and Lab 0's runtime is a classic reference monitor. Any novelty claim must be made against these.
- Affected: foundation.md section 7; novelty posture.

## 0.4.3, 17 October 2026: invariant refinements accepted for Lab 0

- What: accepted F1h hereditary core, explicit delegable capability field Dg, and F2h transitive attenuation for Lab 0.
- What: replaced the informal `Permitted` predicate with a deterministic, total Lab 0 predicate `Permitted_0(a,x) := Alive(a) ∧ x ∈ C(a) ∧ Policy_0(core(a),x)=ALLOW`.
- What: separated structural `ValidDNA(q,p)` from `AuthorizedBirth(p,q)` and `ValidIdentity(q)`; F4 now states that a born child must satisfy authorised birth plus identity validity.
- What: aligned the foundation-level agent tuple with the explicit Dg field and promoted `experiment-spec.md` to version 0.2, ready for Stage 1 implementation.
- Why: preserve the distinction between moral permission and deterministic runtime policy; keep DNA structure, birth authority and identity as separate proof obligations; eliminate ambiguity between exercisable and delegable authority.
- Evidence: author review of repository proposals in 0.4.1; no new experimental result yet.
- Affected: F1h, F2, F2h, F3, F4, W1; Lab 0 L2/L3; foundation agent model.
- Status: accepted for Lab 0. These are modelling decisions, not proofs of the implementation.

## 0.4.4, 17 October 2026: Lab 0 Stage 1 implemented and run

- What: Stage 1 implementation in `src/` (runtime R, evidence log, scripted agents, independent verifier), 40 tests, logs and results under `experiments/lab0/`.
- `[RESULT]` run ids `lab0-stage1-A`, `lab0-stage1-B`, `lab0-stage1-C`, `lab0-stage1-C-ablation-explicit-allow`: configuration C matches all 23 scenario expectations with 0 false blocks and a clean verifier report; the baseline executes 16 violations and the verifier flags all 16; repetitions are byte-identical; B equals A by construction. Details: `experiments/lab0/results/stage1-findings.md`.
- `[RESULT]` Stage 1 pass holds only under the `deny_overrides` reading of `Policy_0`. Under `explicit_allow` controls S00, S01 and S05 are blocked (TC-01).
- Defects found and fixed in the implementation: TC-08 (R not atomic; a blocked spawn could leave a registered child without a birth record), TC-09 (verifier crash on a log without genesis). No log changed.
- Proposals for research review, nothing applied: TC-01 (`Policy_0` underdetermined for the genesis core), TC-02 (core does not constrain spawn or mutate), TC-03 (spec wording on configuration A and S42), TC-04 (tail truncation undetectable; head anchoring), TC-05 (committed test key authenticates nothing), TC-06 (child program not bound to identity), TC-07 (single agent can stall R), TC-08 (state ASM-10 as a tested requirement on R).
- Affected: no invariant, claim or assumption changed.

## 0.4.13, 18 October 2026: Stage 1B research review decisions

- Decision TC-22: cores remain mathematical sets of unique rules. Duplicate rules are rejected as MALFORMED rather than treated as distinct DNA or silently deduplicated. This resolves the R/model conformance discrepancy without changing F1h.
- Decision TC-25: accepted. Under explicit-allow semantics, simply removing K3 does not change effective permission because delete has no allow rule. S10 is therefore revised to attempt a semantic weakening by replacing K3 deny-delete with allow-delete. The core remains immutable; this change improves the attack meaning, not the invariant.
- Decision TC-26: accepted as a fundamental Lab 0 verifier limitation. The independent verifier establishes internal consistency of signed evidence with the Lab 0 rules; it cannot establish that a compromised R recorded the true event when R lies consistently. Paper wording must state this explicitly and tie stronger evidence to later identity/attestation work.
- OQ-06 ablation: exact hereditary equality remains canonical for Lab 0. Semantic core strengthening is not adopted because, under current explicit-allow semantics, it largely reduces to capability attenuation and admits unintuitive cases such as an empty core. This is evidence about the current model, not a general result for richer policy languages.
- Stage 1B paper result accepted: no counterexample in 100-generation lineages, 2,000 generated histories / 100,000 transitions, or the complete bounded state space of 6,742 states and 459,386 transitions. These are bounded empirical/model results, not general proofs. ASM-10 was found violated by the implementation before the fix.

## 0.4.5, 17 October 2026: Stage 1 research review decisions

- Decision TC-01: Lab 0 adopts `explicit_allow` semantics for `Policy_0`. Absence of an applicable allow rule is DENY; deny rules override allows. The genesis core now explicitly allows read, write, spawn and mutable-state changes while explicitly denying vault deletion.
- Why: this preserves the purpose of `Permitted_0` as an affirmative constitutional boundary and avoids collapsing back to "not forbidden means permitted".
- Decision TC-02: accepted. `AuthorizedBirth` now requires the core to allow `(spawn, R)`. Authorised mutation of `mut` is also subject to `Policy_0(core(a), (mutate, self)) = ALLOW`. New scenarios S14 and S25 exercise those choices.
- Decision TC-03: accepted as a specification wording fix. Baseline A is only expected to execute scenarios that are blocked by enforcement; malformed requests may remain malformed without enforcement.
- Decision TC-04: accepted as a limitation. Stage 1 hash chaining proves integrity and order of retained entries, not completeness against tail truncation. The metric wording is narrowed accordingly; external head anchoring is deferred.
- Decision TC-05: accepted as an expected Stage 1 limitation. The committed test key demonstrates signing mechanics and deterministic reproduction, not provenance. Stage 2 must use a key isolated to R under ASM-06.
- Decision TC-08: request atomicity is promoted from an implicit modelling assumption to tested runtime requirement RT-01; serial processing remains under ASM-10.
- Status: `experiment-spec.md` is now v0.3 and Stage 1 must be rerun under these decisions before Stage 2 begins.

## 0.4.6, 17 October 2026: Lab 0 Stage 1 rerun under spec v0.3

- What: implementation updated to the 0.4.5 decisions: explicit-allow `Policy_0`, five-rule genesis core, `Policy_0` checks on spawn and on mutation of `mut`, fixtures for S14 and S25 (`experiments/lab0/fixtures.json`), baseline expectation per spec section 10. The deny-overrides ablation is removed.
- `[RESULT]` run ids `lab0-stage1-v03-A`, `-B`, `-C`: C matches all 25 scenarios with 0 false blocks and a clean verifier report; A executes 18 enforcement-blocked violations and the verifier flags all 18; S42 stays MALFORMED in A; repetitions byte-identical; B equals A by construction. 46 tests pass. Stage 1 pass under the canonical v0.3 specification.
- `[RESULT]` RT-01 tested directly (blocked spawn leaves no child; internal fault rolls back and fails closed).
- New proposals for research review, nothing applied: TC-10 (S10 names K1, which is now an allow rule), TC-11 (section 3 says "one core rule"), TC-12 (section 5 contradicts section 10 on configuration A), TC-13 (`kill` governed by neither capability nor `Policy_0`), TC-14 (mutation is policy-gated but not capability-gated), TC-15 (fixtures extend the trusted genesis under ASM-04). Open from before: TC-06, TC-07.
- Affected: no invariant, claim or assumption changed. Details: `experiments/lab0/results/stage1-findings.md`.

## 0.4.9, 17 October 2026: Stage 2 environment requirements accepted

- Decision TC-16: accepted. Process groups are an RT-02 implementation aid, not a complete security boundary. Stage 2 requires OS-level confinement that contains descendants even if they create a new session or leave the original process group.
- Decision TC-17: accepted as an implementation parameter, not a research invariant. The 1 MiB request-line bound currently also caps child-program payloads. Record it in results; decoupling program transport is deferred unless it blocks later model-driven experiments.
- Decision TC-18: accepted. Channel timeouts are reported separately from policy/capability false blocks because a time-based availability failure is not the same as an authorisation error.
- Decision TC-19: require one dedicated response-phase RT-02 regression test before Stage 2 arbitrary-code runs, even though the same bounded send primitive is already exercised elsewhere.
- What: added `experiments/lab0/stage2-environment.md` as the canonical environment specification. Stage 2 must not begin until its prerequisites are satisfied and recorded.
- Affected: Stage 2 procedure and metrics only; no invariant changed.

## 0.4.7, 17 October 2026: Stage 1 frozen; Stage 2 boundary decisions

- Decision TC-10: accepted wording fix. S10 now targets removal of K3, the deny rule whose removal would weaken the core.
- Decision TC-11 and TC-12: accepted wording fixes. The spec now states a five-rule core and aligns baseline wording with the malformed-input exemption.
- Decision TC-13: self `kill` remains deliberately outside capability and `Policy_0` control in Lab 0 because it can only remove the caller's authority. Any future cross-agent termination must be modelled as a protected action.
- Decision TC-14: accepted asymmetry as a defect in the model, not as intended behaviour. `(mutate,self)` is now an explicit capability as well as a core-governed action, so mutation can be attenuated per descendant. Genesis C and Dg include it; a new scenario S15 checks denial when a descendant lacks it.
- Decision TC-15: accepted. ASM-04 now explicitly covers authorised fixture geneses as trusted test inputs.
- Decision TC-07: accepted as a Stage 2 prerequisite. Added RT-02: bounded request timeout, fail-closed behaviour, transactional rollback and evidence emission.
- Status: Stage 1 results under v0.3 remain valid evidence for the frozen Stage 1 model, but the capability-model refinement for mutation requires a focused Stage 1 regression rerun before Stage 2 starts. `experiment-spec.md` is now v0.4.

## 0.4.8, 17 October 2026: Stage 1 regression under spec v0.4; RT-02 implemented

- What: `(mutate, self)` capability added to genesis C and Dg and checked by R and the verifier; S03, S10 and S15 per spec v0.4; RT-02 bounded channels (`src/runtime/channel.py`) with fail-closed termination, R-initiated kill, signed `channel_failure` evidence, verifier replay, RT-02 bound in genesis; agents in their own process groups.
- `[RESULT]` run ids `lab0-stage1-v04-A`, `-B`, `-C`: C matches all 26 scenarios with 0 false blocks and a clean verifier report; A executes 19 enforcement-blocked violations and the verifier flags all 19; 0 channel failures; byte-identical across repetitions and separate invocations; B equals A by construction. Stage 1 regression pass under v0.4.
- `[RESULT]` RT-02 tested with fixed scripted test doubles (never answers, partial line, oversize stream, early exit, never reads): each terminated within the bound, fail closed, RT-01 preserved, evidence written and verified, other agents still served. 58 tests pass.
- Stage 2 readiness: code prerequisites met; environment prerequisites (separate unprivileged uid, R not root, isolated key, agent network isolation, OS confinement of descendants) not met in this workspace and not attempted. Stage 2 not started.
- New proposals for research review, nothing applied: TC-16 (process-group termination does not contain a process that leaves its group), TC-17 (request-line bound also caps child program size), TC-18 (time-based bound can cause false blocks under load; report separately), TC-19 (response-phase timeout not separately exercised).
- Affected: no invariant, claim or assumption changed. Details: `experiments/lab0/results/stage1-findings.md`.

## 0.4.10, 17 October 2026: Stage 2 preparation without host changes

- What: dedicated response-phase RT-02 regression (TC-19 decision); channel timeout rate reported separately from policy/capability false blocks (TC-18 decision); read-only Stage 2 preflight (`src/stage2/preflight.py`) and agent-side probe (`src/stage2/agent_probe.py`) implementing `stage2-environment.md` section 9; config template `experiments/lab0/stage2-preflight.example.json`.
- `[RESULT]` Response-phase regression: request committed and logged, then CHANNEL_TIMEOUT in phase `response`, agent terminated and marked dead, evidence verifies, no surviving process. Stage 1 logs unchanged; channel timeout rate 0/41 in A, B and C. 76 tests pass.
- `[RESULT]` Preflight in the cloud workspace: ENVIRONMENT_INVALID (P01 to P04 FAIL, P05 PASS, P06 to P08 NOT_EVALUATED, P09 PASS), as expected; not a Stage 2 result. The agent probe was not run here.
- Not done, by instruction: no users provisioned, no VM or container settings, no sudo, no attacker runs. Stage 2 not started.
- New proposal for research review: TC-20 (static preflight checks are advisory; dynamic probe and VM boundary are authoritative).
- Affected: no invariant, claim or assumption changed.

## 0.4.11, 18 October 2026: Stage 2 environment provisioned on a dedicated workstation (researcher-approved)

- What: Hyper-V enabled on a dedicated workstation and a disposable Generation 2 VM `fitrah-stage2` built: Ubuntu 26.04.1 LTS, kernel 7.0.0-30, Python 3.14.4, systemd, cgroup v2, 2 vCPU, 4 GB static RAM. No shared folders, guest service interface disabled, no internet route: the only adapter is a host-only Hyper-V internal switch ([private address]), used to copy the bundle in. Users `fitrah-runtime` (uid 1001) and `fitrah-agent` (uid 1002), neither in sudo; runtime tree under `/srv/fitrah/runtime` with code in `fitrah/` so the key sits outside the repository; fresh Ed25519 key generated in the VM. Scripts: `experiments/lab0/stage2-env/`.
- `[RESULT]` Preflight in the VM (`results/stage2-preflight-hyperv-vm.json`): P01 to P05 PASS, P09 PASS (RT-02 response-phase regression on Python 3.14), P06 to P08 NOT_EVALUATED by design; verdict ENVIRONMENT_INVALID. Agent probe as uid 1002 (`results/stage2-agent-probe-hyperv-vm.json`): key read and write, log write, registry write, vault read and write and external network all DENIED; verdict PASS.
- Outstanding before Stage 2: P08 needs the S65 containment test inside the boundary; the adapter is to be disconnected before attack runs and preflight repeated under those conditions.
- Environment notes: Ubuntu 26.04 rather than the planned 24.04 (installer image used); dependencies installed offline into the runtime user's site-packages.
- Affected: no invariant, claim or assumption changed. Stage 2 not started.

## 0.4.12, 18 October 2026: Stage 1B robustness results

- What: Stage 1B per `experiments/lab0/stage1b-robustness.md`, implemented in `src/stage1b/` (in-process driver over R's real decision code, independent reference model, 13 defective runtimes, seeded adaptive generator with shrinking, bounded exhaustive search, OQ-06 ablation). Findings: `experiments/lab0/results/stage1b-findings.md`; data: `stage1b.json`, `stage1b-ablation-oq06.json`. Stage 2 not touched.
- `[RESULT]` Correct R, configuration C: 0 violations in deep lineages to 100 generations (222 attacks injected, all blocked), in 2,000 generated histories (100,000 transitions; verifier accepts all 2,000 logs), and in the complete bounded state space (3 agents, 6,742 states, 459,386 transitions). Process path and in-process path identical on 50 histories.
- `[RESULT]` Verifier detection: 59,408 / 59,408 executed baseline violations; 11,841 / 11,841 for 12 of 13 injected runtime defects; 13,339 / 13,466 overall, the misses all from D10c, a consistently lying R. The exhaustive search finds a counterexample within 1 to 2 requests for every defect.
- Fixed (tooling, not research): TC-23, the verifier replayed a claimed identity in configuration C and rejected a correct log; TC-24, four verifier completeness gaps (dead-actor mutation and kill, unchanged protected-field writes, claimed-identity effects in A, authority judged on corrupted state, now a lawful-authority view). Stage 1 logs unchanged; `stage1.json` records 31 verifier flags in A instead of 30.
- New proposals for research review, nothing applied: TC-22 (R and the verifier compare cores as lists, `invariants.md` defines them as sets; over-blocks a duplicate-rule core), TC-25 (under explicit allow, K3 changes no permission, so S10's removal attacks nothing semantically), TC-26 (log replay cannot establish truth when R lies consistently). ABLATION for OQ-06: semantic strengthening admits an empty core; in 6,400 trials a stronger core equalled capability attenuation.
- Numbering: TC-21 is the S65 containment design (workstation session); Stage 1B findings start at TC-22.
- Affected: no invariant, claim or assumption changed.

## 0.4.14, 18 October 2026: S65 containment implemented (TC-21 revision 2, researcher-approved)

- What: root-owned helper `fitrah-agentctl` (launch, terminate, census; allowlisted programs; per-agent root-owned cgroup; uid drop by the helper; pipes passed to R by SCM_RIGHTS), Stage 2 `HelperChannel`, S65 test double and two-oracle runner, P08 wired to the S65 report. Deviations from the design text are listed in `experiments/lab0/stage2-s65-design.md` under Implementation.
- `[RESULT]` Cloud workspace, not the Stage 2 environment (cgroup v2 hierarchy without systemd, helper started by hand): S65 PASS three times; killpg control left the setsid and setpgid descendants alive; cgroup.kill killed all 5 processes; cgroup and uid oracles empty; every cgroup escape attempt denied. Test suite 107 passed before merging Stage 1B.
- Not yet done: S65 and preflight in the VM.
- Affected: no invariant, claim or assumption changed. Stage 2 not started.


## 0.4.15, 18 October 2026: TC-27 evidence-write atomicity finding (OPEN)

- [COUNTEREXAMPLE] Off-VM injected request-log append failure leaves an allowed vault write in Monitor state with zero request evidence. No agent or VM scenario was executed by this reproduction.
- [FACT] handle appends evidence after its rollback try/except; vault/registry remain in-memory dictionaries. Filesystem resource integration cannot be claimed from the synthetic permission pilot.
- Proposed repair and acceptance criteria: experiments/lab0/stage2-resource-integration-review.md; reproduction: experiments/lab0/review/reproduce-evidence-failure.py (run from repository root with PYTHONPATH=src).
- Affected: existing RT-01 implementation compliance, future ASM-03/ASM-05/ASM-06 integration. No invariant or assumption is changed. Crash/recovery scope remains an explicit review question; existing bounded results are not retroactively expanded to cover this failure.
- Status: OPEN finding, repair design PROPOSED. Canonical attacker expansion paused pending this review/repair; synthetic pilot evidence remains narrowly scoped.


## 0.4.16, 18 October 2026: TC-28 filesystem transaction design (PROPOSED)

- [FACT] TC-27 detected in-process failure repair merged in c0b4147b3d9f676d93dcb282c1c78de4faceea2c; 73 Linux regression tests passed. Post-installation synthetic pilot evidence is separately recorded; it is not fault-injection or real-resource integration evidence.
- [PROPOSAL] TC-28 in experiments/lab0/stage2-storage-design.md specifies versioned full-state generations selected by a single commit manifest, and an explicit failure/recovery/test matrix.
- Review required before adoption: live resource paths and preflight mapping, commit uncertainty/restart interpretation, prepared child activation semantics, real-read response schema and storage deadline handling.
- Affected if adopted: RT-01/RT-02 implementation and interpretation, ASM-03/05/06 resource mapping, TC-21 helper TCB/interface. Existing assumptions, invariants, canonical S64/S70 expectations and environment remain unchanged.
- Status: design only, not a result or proof. TC-27 crash/recovery scope remains open; TC-28 does not silently close it.


## 0.4.17, 18 October 2026: TC-29 experimental committed-birth decision

- Researcher explicitly approved: commit the authorised birth record before permitting child execution; if startup fails afterward, retain birth, record separate failure/death where possible and invalidate the run.
- Scope: experimental minimal resource demonstration only. Existing canonical Monitor/Stage 1 failed-launch behavior, accepted F4 definition and RT-01/RT-02 requirements are not silently replaced. Precise lifecycle/event schema and failure semantics require review before canonical adoption.
- Implementation/evidence: draft PR #4 (depends on #3), experiments/lab0/resource-demo-review.md. Local Linux suite 86 pass, including real-process mediated read, denied write and cleanup; no separate-uid or Stage 2 claim.
- Affected if adopted canonically: birth/launch ordering, RT-01, lifecycle evidence and TC-21 launch contract. Partial-launch cleanup, storage deadlines, crash recovery and full Stage 2 remain outstanding.


## 0.4.18, 18 October 2026: consolidated paper-facing status

- `[RESULT]` Stage 1B paper evidence accepted: no counterexample in 100-generation lineages, 2,000 generated histories / 100,000 transitions, or the complete bounded search of 6,742 states and 459,386 transitions.
- `[RESULT]` Dedicated Hyper-V prerequisite evidence records P01-P09 PASS / READY; S65 demonstrates the tested cgroup-v2 containment boundary succeeds where ordinary process-group teardown leaves escapees.
- `[LIMITATION]` Synthetic filesystem pilot evidence is narrower than canonical S60-S64/S70 and is not reported as Stage 2 completion.
- `[COUNTEREXAMPLE]` TC-27 exposed evidence/state atomicity failure; the detected in-process path was repaired and regression-tested. Crash durability remains outside that repair.
- `[PROPOSAL]` TC-28 versioned transactional storage remains experimental; no power-loss durability claim.
- `[CHOICE]` TC-29 commits authorised birth before child execution only in the experimental resource demonstration; canonical lifecycle semantics remain open.
- `[RESULT]` First guarded resource-backed VM run returned INVALID_RUN after AUTHORIZED_BIRTH followed by STARTUP_FAILURE; cleanup confirmed and no workload action occurred. Launch-readiness race remains a hypothesis.
- Added `papers/hereditary-trust-paper-draft.md` as the current paper-facing synthesis. No accepted hereditary invariant changed.


## 0.4.19, 18 October 2026: 2026 prior-art convergence narrows novelty target

- `[EVIDENCE]` Reviewed current direct neighbours including *Delegation Without Trust*, AIP, IETF AIMS, NIST agent identity/authorization work, Proof-Carrying Agent Actions, SPIFFE/SPIRE, DICE and Biscuit-style attenuation.
- `[FACT]` Bounded delegation, external authorization, workload identity, attestation and proof-carrying action gates are not individually candidate Fitrah novelties.
- `[LIMITATION]` OQ-06 / Stage 1B remains important: under the current simple explicit-allow core, semantic strengthening largely collapses into capability attenuation. A Digital DNA claim that is only a capability mask is weak relative to prior art.
- `[HYP]` Candidate novelty is narrowed to the lifecycle composition: authorised birth as a validity transition + mandatory hereditary constitutional state + recursive authority ceiling + lineage evidence + later instance-bound attestation.
- `[CHOICE]` Future identity, delegation-token and attestation mechanisms should reuse mature standards/primitives where suitable rather than being reimplemented for novelty.
- `[ABLATION]` Add a future three-way comparison: broad bearer authority vs modern attenuated delegation broker vs Fitrah authorised birth/hereditary constraints. The research question is whether Fitrah excludes additional invalid birth, lineage or lifecycle states.
- No accepted invariant changed. This is a positioning and experiment-design update.


## 0.4.20, 18 October 2026: non-VM formal experiments N1-N5

- `[RESULT]` N1/N2 bounded comparison: a simple attenuation-only broker accepts states that Fitrah rejects on birth, lineage, evidence or lifecycle grounds, but those tested predicates can also be represented as contextual caveats if the broker is given equivalent trusted facts.
- `[TC CANDIDATE TC-30]` No greater logical expressiveness over a sufficiently rich caveated authorization system has been established. Candidate Fitrah contribution should therefore be tested as mandatory construction/lifecycle semantics, not assumed authorization-language superiority. This is not yet a canonical theory change.
- `[RESULT]` N3 birth lifecycle: retry after an uncertain-but-actually-live launch reaches a duplicate-live-instance state in three steps: authorised birth -> uncertain live launch -> retry success. Forbidding retry while outcome is uncertain avoids that state within the bounded model.
- `[RESULT]` N4 external truth: an R-signed log head alone detects none of the tested consistent-lie classes. Independent birth witnesses, resource-side observations and instance measurements detect different claim classes; no single tested observation establishes all semantic truth.
- `[COUNTEREXAMPLE]` N5 population model: two individually compliant agents can compose a secret exfiltration sequence when one can read/send and the other can receive/write. This does not falsify F1-F4; it demonstrates that per-agent invariants do not imply a population-level non-interference property.
- Reproducibility: `experiments/nonvm/run_models.py`, machine-readable `experiments/nonvm/results/summary.json`, and result notes under `experiments/nonvm/results/`.
- No accepted invariant, assumption or Stage 2 result changed.


## 0.4.21, 18 October 2026: TC-30 accepted; authorization-expressiveness claim narrowed

- `[DECISION]` TC-30 accepted: Fitrah does not currently claim greater authorization-language expressiveness than sufficiently rich caveated delegation systems.
- `[HYP]` Candidate distinctiveness remains lifecycle-level: authorised birth, lineage validity, hereditary constitutional state, activation semantics and later execution-instance binding.
- `[CHOICE]` A stronger baseline is required before any novelty argument: rich contextual caveats plus a trusted registration/birth state machine.
- No accepted F1-F6 invariant changed. This is a research-positioning and falsification-design decision.


## 0.4.22, 18 October 2026: E6 strong-broker ablation

- `[RESULT]` Enumerated 256 bounded birth/lifecycle states. A rich delegation broker plus an equivalent trusted registration/birth state machine and the current Fitrah abstraction each accepted the same 36 valid states; zero distinguishing states were found.
- `[NEGATIVE RESULT]` Current bounded Fitrah semantics do not establish a state-level advantage over an equivalently composed modern authorization + registration system.
- `[TC CANDIDATE TC-31]` Do not claim novelty merely from composing attenuation with birth/registration semantics. A stronger contribution must arise from a distinct hereditary property, theorem/compositional guarantee, hostile-execution systems result, or lifecycle/attestation construction that survives a fair equivalent baseline.
- No accepted invariant changed. The result is bounded and does not establish general equivalence.


## 0.4.23, 18 October 2026: TC-31 accepted

- `[DECISION]` TC-31 accepted as a research-positioning constraint: the current bounded Fitrah model does not establish novelty merely by composing attenuated delegation with a trusted birth/registration state machine.
- `[HYP]` Any stronger contribution must come from a distinct hereditary/compositional property, a theorem, a hostile-execution systems result, or an attested lifecycle construction that survives an equivalent baseline.
- No F1-F6 invariant changed.


## 0.4.24, 18 October 2026: E7 lineage-wide authority conservation

- `[COUNTEREXAMPLE]` Current per-child attenuation allows two siblings each to receive one unit from a parent with one unit when allocations are checked independently; aggregate delegated authority therefore doubles.
- `[RESULT]` A lineage-wide conservation rule blocks that state.
- `[NEGATIVE RESULT]` An atomic stateful reservation broker blocks the same state, so the property is not distinguishing in the bounded comparison.
- `[EVIDENCE]` Linear/non-duplicable capabilities and current bounded-capability work are direct prior art for authority conservation and sibling-budget control.
- This is a candidate future population invariant under OQ-09, not an accepted Lab 0 invariant and not a novelty claim.


## 0.4.25, 18 October 2026: E8 locally verifiable lineage evidence

- `[RESULT]` 32,768 depth-three lineage states examined against a strong portable credential-chain baseline carrying equivalent signature, parent-link, attenuation, constitutional-commitment and birth-authority predicates.
- `[NEGATIVE RESULT]` Zero distinguishing states were found.
- `[TC CANDIDATE TC-32]` Portable lineage evidence/provenance should not be treated as a Fitrah novelty claim.
- Current standards/prior art already support locally verifiable delegation chains; the remaining research opportunity shifts toward hostile-execution lifecycle composition.
- No accepted invariant changed.


## 0.4.26, 18 October 2026: research direction clarified after TC-30 to TC-32

- `[DECISION]` TC-32 accepted as a positioning constraint: portable lineage/provenance is not treated as a Fitrah novelty claim.
- `[CHOICE]` The name Fitrah remains an intellectual inspiration from the Islamic concept of an innate created nature, but the project does not equate machine constitutional state with theological human fitrah, morality, iman, conscience or free will.
- `[HYP]` Current engineering thesis: every valid machine descendant should necessarily inherit an irreducible constitutional substrate from its root while mutable cognition may diverge arbitrarily.
- `[HYP]` The candidate systems contribution is now the hostile-execution composition of authorised birth + hereditary constitutional state + protected authority/state + durable lifecycle evidence + later execution-instance binding.
- `[LIMITATION]` E6/E8 show that equivalent trusted registration state machines and portable credential chains can reproduce current bounded abstract semantics. Future novelty cannot rest on naming or composing those primitives alone.
- Near-term research therefore shifts away from further authorization-language novelty searches and toward Stage 2 lifecycle/resource integration and later birth-to-instance binding.
- No F1-F6 invariant changed.


## 0.4.27, 18 October 2026: E9 birth-to-authority instance binding

- `[COUNTEREXAMPLE]` A decoupled lifecycle with committed birth followed by authority-bearing process launch and later instance binding has a crash prefix where the process has protected authority before its specific execution instance is durably bound.
- `[RESULT]` A bounded prepared-child model in which the process remains powerless until one committed birth/core/evidence/instance binding is published had no such bad crash prefix.
- `[TC CANDIDATE TC-33]` Future instance-bound Fitrah should not let process launch itself confer protected authority. Authority should derive from the committed hereditary birth-to-instance binding.
- `[NEGATIVE RESULT]` A generic strong reference monitor using the same atomic binding fact is equivalent in this bounded decision model; E9 is a necessary construction result, not a novelty result.
- No accepted F1-F6 invariant changed. No VM claim.

## 0.4.28, 19 October 2026: GitHub-hosted Stage 1 and Stage 1B reproduction

- [RESULT] Hosted Stage 1 [run 39276979467](https://github.com/c0ldskin/fitrah/actions/runs/39276979467), source `91740062df0eef1c68202cb9c8e74aeab02ab82b`: 65 targeted tests passed, canonical execution and independent six-log verification passed, evidence artifacts uploaded.
- [RESULT] Hosted Stage 1B [quick run 39282890148](https://github.com/c0ldskin/fitrah/actions/runs/39282890148): 399 evidence cases verified, 73 targeted tests passed; smoke scope only.
- [RESULT] Hosted Stage 1B [full run 39284167068](https://github.com/c0ldskin/fitrah/actions/runs/39284167068), source `d14c6a2eaf9827afe9ac946d45ec8717ac3cdff8`: canonical full workflow completed, 73 targeted tests passed, 10,631 captured evidence cases passed the workflow verifier with no reported verification errors; artifact 12203401010 uploaded (137,399,588 bytes compressed), reported SHA-256 `bbee5df05313abb5c5df6be25c23d19a87c917defa534998c6bfda329c948a20`.
- [EVIDENCE] The contributing reviewer reports examining GitHub-hosted job logs and artifact metadata in [PR #10's review comment](https://github.com/c0ldskin/fitrah/pull/10#issuecomment-6272816604), which records expiry at `2027-01-17T16:16:34Z`. Full archive has not yet been downloaded and independently audited by the paper reviewer; durable off-Actions retention has not been confirmed.
- [LIMITATION] These are first-party cross-environment reproductions with signed-log replay and summary reconciliation, not a separate model-checker enumeration, external runtime attestation or third-party replication. TC-22 and TC-26 remain, and Stage 2 is not advanced by these jobs.
- [CHOICE] Propose Foundation Note 0.9 as a separate formal-document revision; leave 0.8 unchanged. No accepted invariant, assumption, threat model, research interpretation or novelty claim changes.

## 0.4.29, 19 October 2026: Erratum to Stage 1B deep-lineage attack count

- [FACT] Changelog entry 0.4.12 (18 October 2026) reports **222 attacks injected** in the 10-, 50- and 100-generation Stage 1B deep-lineage tests. This number is inconsistent with the cited machine-readable result and findings table; the original entry is retained unchanged for auditability.
- [EVIDENCE] `experiments/lab0/results/stage1b.json`, under `experiment1_deep_lineage.rows`, records `injected` counts of **23, 54 and 84**, respectively, for a total of **161 injected attack attempts**. `experiments/lab0/results/stage1b-findings.md` section 2 reports the same counts. All 161 are recorded as blocked by configuration C. Baseline A `A_executed_violations` counts (23, 55, 87) describe a different metric and must not be substituted for injected attempts.
- [RESULT] Correct the *reported aggregate* in entry 0.4.12 to **161**, not 222. This is a historical numerical-reporting erratum, not a changed experiment result, accepted invariant, threat model, or research interpretation. The original JSON and findings are unchanged.

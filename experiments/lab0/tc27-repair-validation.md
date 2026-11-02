# TC-27 repair candidate

Status: implementation for review; not merged or deployed to the Stage 2 VM.

EvidenceLog now uses unbuffered writes and checkpoints the append offset. Signing,
write, short-write and flush failures mark the writer failed and attempt to
truncate back to the checkpoint. Sequence and chain head advance only on success.
Failure to restore the suffix is explicit and retains the damaged artifact.

Monitor.handle restores its pre-request registry/vault state and tears down new
children if evidence append fails. It raises RunInvalid rather than returning an
allow/block response. The monitor refuses further handle/run calls. All evidence
failures abort the run, including cases where restoration succeeds; resuming an
interrupted run is deliberately not implemented. Existing identifier consumption
semantics remain unchanged.

Rollback attempts every new child's cleanup, retains handles whose cleanup
failed, and restores model state even when cleanup fails. Run shutdown attempts
every remaining channel close; any failure makes the run invalid. These failures
propagate to the caller; there is no new success summary or forged chain event.
The caller must preserve the raised error and artifacts when classifying the run.

Validation:

- Windows: 54 passed, 1 process-path test deselected across the new fault tests
  and in-process Stage 1B regressions.
- Linux/WSL: 71 passed across test_evidence_atomicity.py, test_stage1.py and
  test_rt02.py, using cached dependencies. This includes existing verifier,
  reproducibility, rollback and request/response timeout checks.
- An initial selection of five process-based tests was mistakenly run on Windows
  and failed due to Linux-only channel APIs; all are included in the passing
  Linux run. Host inspection found no surviving test agents afterward.
- Ten new tests check retained bytes, sequence/head, state rollback, rejection
  of subsequent requests, failed cleanup handle retention, all-channel cleanup,
  and successful signed-log replay. Injected failures include signing, before
  write, partial write, short write, flush and failed truncation.

Limits: ordinary regression tests in WSL are not Stage 2 isolation evidence.
No new attacker scenario or VM deployment occurred. This repair does not add
fsync, recovery after process/power loss, atomic multi-file persistence, or a
filesystem vault adapter. It does not narrow RT-01 or resolve its crash-scope
review question; TC-27 should remain open until the repair is reviewed.

## Follow-up implementation review

Same-assistant review found and fixed two further exception paths: evidence
entry preparation (including state digests) was outside the rollback guard;
timeout cleanup removed its channel handle before kill succeeded. The former
now restores state and aborts, and the latter retains the handle for shutdown
retry. Neither path emits an allowed result or a false successful termination.

The updated Linux suite passes 73 tests, including 12 targeted failure/cleanup
tests. This is a source review plus regression evidence, not independent review,
VM deployment, crash recovery or resolution of the remaining storage design.

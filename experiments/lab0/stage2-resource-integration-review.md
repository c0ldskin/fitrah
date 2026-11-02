# TC-27: evidence-write failure breaks request atomicity

Status: OPEN finding; proposed repair design, not a change to RT-01.
Inspected canonical main: eb251070e8156c9040fffc9ce54b3f0b888b46c3.

## Evidence and scope

[FACT] runtime.monitor.Monitor.handle snapshots registry/vault state, evaluates
the request and applies effects, then calls log.append outside its rollback
try/except. runtime.evidence.EvidenceLog.append signs, writes and flushes a line
before updating its sequence/head.

[COUNTEREXAMPLE] An injected OSError from request evidence append leaves an
allowed write in Monitor.vault with zero request evidence entries. The attached
off-VM reproduction creates no agent processes, keys or protected-resource files.
Observed output: vault_changed=true; request_evidence_count=0.
This establishes an exception-path implementation defect against existing RT-01,
not a counterexample to hereditary attenuation, and not an observed disk failure
in the VM. Earlier bounded Stage 1/1B results and the synthetic pilot remain
evidence for their exercised paths; they do not cover this failure.

[FACT] Monitor.vault and Monitor.registry are dictionaries. The protected VM
ledger and registry files are not the authoritative state of this monitor.
Consequently the synthetic pilot cannot close the actual resource-integration
gap. Copying dictionaries to files after handle returns would introduce another
state/evidence failure window.

Affected: RT-01, evidence completeness during failures, future filesystem
integration under ASM-03/ASM-05/ASM-06. F5 wording and TC-04/TC-26 limits remain
unchanged. No claim of crash durability or protection against a compromised R.

## Proposed repair and acceptance criteria

1. Make evidence append an explicit commit boundary. Snapshot the evidence
   offset, sequence and chain head before a request. Prepare/sign the complete
   entry before publishing state. Handle short writes and flush exceptions.
2. On a recoverable append failure, restore registry, vault and new-child
   processes under the existing rollback semantics; restore the evidence
   suffix/head to the checkpoint before continuing. Identifier consumption
   retains its existing rule. Do not emit an allowed response.
3. If evidence rollback or child cleanup cannot be confirmed, abort the run,
   retain diagnostic artifacts and classify it invalid. Do not suppress the
   failure or describe it as a policy block. Further requests must not execute.
   A secondary out-of-band run-failure record must not masquerade as a committed
   event in the damaged chain.
4. Cover signing failure, write failure before bytes, short/partial write,
   flush failure, failed evidence rollback, and failed child cleanup. Assert
   actual retained bytes, registry/vault state, sequence/head and inability to
   continue after an unrecoverable error, not only exception types.
5. Preserve ordinary Stage 1 semantic outcomes and canonical evidence on
   successful paths. Re-run targeted RT-01/RT-02 and independent verifier
   regressions after repair. Windows in-process tests do not establish Linux
   process/cgroup behavior.

[OPEN QUESTION] These steps address detected in-process I/O failures. Atomicity
across power loss, kernel crash or multi-file persistence needs a separate
commit/recovery protocol. Do not silently narrow RT-01 or claim that truncating
a JSONL suffix makes several filesystem writes atomic. Any scope clarification
must go through research review.

## Filesystem integration sequence

After TC-27 review/repair, introduce a separately reviewed storage adapter with
one authority for committed state. Bind the configured fixed ledger, registry
and evidence paths to actual runtime operations. Do not add arbitrary paths to
agent requests or to the privileged helper.

Before selecting a storage format, define transaction visibility, error recovery,
and how exported JSONL, registry digest and actual ledger bytes correspond.
A database plus exported files, or a versioned snapshot scheme, cannot be
substituted without documenting that mapping and validating the real protected
resource boundary. Preserve the existing verifier's independent decision logic.

Required controls: permitted read/write through R have observable resource
effects; denied requests leave both resource and evidence state consistent;
injected persistence failures cannot leave an unlogged successful effect;
repeatability is assessed semantically under the VM keying model.

S64 retains its canonical expectation: an inherited channel carries Q's authority.
Do not relabel successful channel reuse as a security failure or add nontransferable
identity by implementation fiat. S70 tests bounded authority under ASM-09, not
general prevention of data sharing or cooperation.

No new VM run, helper grant, research assumption change or scenario result is
authorised by this proposal alone. The existing user authorisation covers
continuing reviewed implementation work; new research semantics remain proposals.

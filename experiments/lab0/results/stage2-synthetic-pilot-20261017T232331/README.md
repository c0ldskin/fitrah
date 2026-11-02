# Synthetic pilot VM result: 20261017T232331

[RESULT] PILOT_PASS, scope SYNTHETIC_FILES_ONLY. Canonical Stage 2 is not complete.

The researcher executed the gated wrapper in the disconnected Hyper-V guest.
Fresh prerequisite evidence records exactly P01-P09 PASS / READY. S65 records
five processes terminated and empty cgroup/uid oracles; the killpg control
detects surviving setsid/setpgid descendants. Environment capture shows eth0 DOWN.

The pilot records runtime uid1001 and agent uid1002, successful public-file
positive control, eight denied read/append attempts against four dummy files,
unchanged fixture hashes, helper and independent cgroup membership for pid2346,
successful termination, removed cgroup and no survivors. Link carrier is zero
before and after. No real secret or private signing key is included.

[EVIDENCE] Host-side verification using the public Ed25519 key succeeded:
signature, claimed-result consistency, exact preflight file digest, all nine
prerequisite PASS entries, and public-key fingerprint binding. Raw public key
SHA-256: 7eab91567921bdd0b1380b75ce27adb08112479bbf818fedf4f7d45c0580ba1e.
The manifest hashes the seven exported raw evidence/public-key files.

Pilot implementation: draft PR #1, commit
6b9e80d58153c444f4982807a5af4640a6c1e752. Base VM prerequisite implementation:
8ce6aeeda93644f198f01baf75f8793ee87d5caa. The staged wrapper checked runner
SHA-256 51e1f0a55506d6b9f90b1727bf7c397cdda705f3a3de4d1ad7ffabdd11f8e371
and worker SHA-256 3efff9fe5ac4617e43c25295ec70fe4e670761217f56a9bbf7b5711240bba604.
Installed TCB hashes are in the raw capture. The TCB capture precedes the pilot,
so its journal is prerequisite context, not a pilot termination journal.

[LIMITATION] Signed observations trust R and the worker (TC-26); this is not
independent OS attestation or an independent external review. The report hashes
the preflight input but does not contain its filesystem modification time, so
freshness is enforced by the reviewed runner rather than independently
reconstructed from the signed report. Network observations bracket execution;
they are not continuous switch monitoring. This run does not satisfy S60-S64/S70
or close the real-resource integration gap. The adapter was reconnected to the
prior internal switch for export after observed cleanup; no new scenario ran
during retrieval. A subsequent SSH process listing showed no agent-uid process.

> **Public copy note:** the raw environment and trusted-computing-base captures (`environment-*.txt`, `tcb-*.txt`) are withheld because they contain host network details. Their SHA-256 hashes remain in `manifest.json`, so the originals can be verified on request.

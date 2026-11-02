# Post-TC-27 synthetic pilot: 20261017T234107

[RESULT] PILOT_PASS, SYNTHETIC_FILES_ONLY; canonical Stage 2 remains incomplete.
The researcher ran the gated prerequisite/pilot wrapper after installing the
two runtime sources merged in c0b4147b3d9f676d93dcb282c1c78de4faceea2c.
Installation hashes were observed separately and recorded in the private research log.
Pilot source remains the reviewed implementation from PR #1.

[EVIDENCE] Host verification passed for the Ed25519 signature, recomputed pilot
result, exact prerequisite digest, all P01-P09 PASS and public-key binding.
Runtime uid1001 and agent uid1002 are distinct non-root identities. Agent pid3056
is recorded in the helper and independent cgroup census. All eight dummy-file
read/append attempts were denied; positive control succeeded; fixture hashes
were unchanged; termination succeeded, cgroup removed and survivors empty.
Link carrier is zero before/after. Environment capture records eth0 DOWN.
The subsequent SSH process listing after reconnect found no agent-uid process.

Raw prerequisite/public-key exports and the signed pilot report are retained
unchanged; manifest.json supplies SHA-256 hashes. No private key is included.

[LIMITATION] This is synthetic permission/containment integration evidence,
not direct fault-injection validation of TC-27. The repair's 73 Linux/WSL tests
are separate evidence. Runtime source hashes are not embedded in the signed
pilot report; deployment identity relies on the recorded installation procedure.
Preflight content happens to have the same digest as the prior run: it contains
no unique run nonce or timestamp. Its freshness was enforced via file mtime and
the gated wrapper, and cannot be independently reconstructed from that digest.
The signature authenticates recorded observations, not truth against a lying R
(TC-26). Link checks bracket execution rather than continuously observing the
switch. TCB capture precedes this pilot and is not its termination journal.
Real-resource integration and S60-S64/S70 remain outstanding. The adapter was
reconnected to the prior internal switch only for evidence export after observed
successful cleanup. No new scenario was run during retrieval.

> **Public copy note:** the raw environment and trusted-computing-base captures (`environment-*.txt`, `tcb-*.txt`) are withheld because they contain host network details. Their SHA-256 hashes remain in `manifest.json`, so the originals can be verified on request.

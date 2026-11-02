# Hyper-V Stage 2 prerequisite evidence

[RESULT] Guest run 20261017T225135: preflight READY, P01-P09 PASS. This is prerequisite evidence, not completion of the Stage 2 attacker matrix.

Source bundle: commit 8ce6aeeda93644f198f01baf75f8793ee87d5caa. All 80 archive file blobs were compared with that commit before provisioning. No source or research changes were made for this run.

## Reviewed evidence

- Runtime uid 1001; agent uid 1002; distinct non-root identities without shared groups.
- Agent probe: six protected-file accesses denied and external-network probe denied as uid/euid 1002.
- Environment capture: eth0 DOWN; Ubuntu 26.04.1 LTS, Linux 7.0.0-30-generic, Python 3.14.4, systemd and cgroup v2 with cgroup.kill.
- S65: fork, double_fork, setsid and setpgid recorded. All five contained processes run as uid 1002; census covers them; cgroup escape writes denied; cgroup.kill terminates all five; cgroup and uid oracles empty. Control using killpg detects surviving setsid and setpgid descendants.
- P09: 2 passed, 11 deselected in 0.68s. This corrects the earlier console transcription of 0.60s.
- TCB: VM boundary, Linux cgroup v2 implementation, systemd, privileged fitrah-agentctl helper, root-owned allowlist and fixed S65 program. Raw TCB capture records installed hashes, unit configuration, socket/subtree ownership and launch/terminate journal events. Authoritative unit sources are under experiments/lab0/stage2-env/systemd/ at the source commit above.
- After the researcher reconnected the prior internal adapter for retrieval, a fresh process listing found no fitrah-agent process. Adapter is connected for retrieval, not for further scenarios.

## Public key and evidence limits

The researcher exported only stage2-signing.pub from the protected runtime directory. The file is now included. Independent local decoding confirms a 32-byte Ed25519 public key and SHA-256 of its raw bytes equal to the preflight fingerprint: 7eab91567921bdd0b1380b75ce27adb08112479bbf818fedf4f7d45c0580ba1e. The public-key export requirement in stage2-environment.md section 6 is satisfied for this prerequisite bundle. No private key was retrieved or included.

P04/P05 are static/advisory checks; the probe and VM boundary provide the dynamic environment evidence under TC-20. Reports and hashes establish captured evidence consistency, not independent attestation of the guest. Host Hyper-V adapter configuration was not queried successfully by automation; eth0 DOWN is guest evidence and disconnection was performed by the researcher.

The earlier reported reboot remains unexplained. Visible previous-boot journal lines showed an orderly reboot; no failure cause is inferred. This successful invocation is a separate run with its own saved reports.

No S60-S64 or S70 experiment was performed in this session. Before further attacker runs, restore adapter disconnection and refresh prerequisites as required by the canonical environment documents.

> **Public copy note:** the raw environment and trusted-computing-base captures (`environment-*.txt`, `tcb-*.txt`) are withheld because they contain host network details. Their SHA-256 hashes remain in `manifest.json`, so the originals can be verified on request.

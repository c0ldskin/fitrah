# Fitrah Assumptions

Every guarantee claimed in this repository is conditional on the assumptions it cites. Changing an assumption requires a `changelog.md` entry listing the affected invariants and experiments.

| ID | Assumption | Type | Affects | Status |
|---|---|---|---|---|
| ASM-01 | The model (M) is untrusted; no deterministic guarantee depends on its behaviour | Security | All | Adopted (Note 0.4 section 3) |
| ASM-02 | The host OS, kernel, Python interpreter running R and the hardware are not compromised | Security | F1 to F5 | Adopted for Lab 0; removed progressively in Labs 2 and later |
| ASM-03 | The only way to change the registry or create a registered agent is through R's transitions | Security | F1, F2, F4 | Adopted; stage 2 attempts to falsify it |
| ASM-04 | The canonical genesis configuration and any explicitly authorised test-fixture geneses are correct and trusted inputs | Security | F1h, F2 | Adopted |
| ASM-05 | The protected resource is reachable only through R (no direct file, socket or credential path from agent processes) | Security | F3, L2 | Adopted; stage 2 attempts to falsify it |
| ASM-06 | Agent processes cannot read R's key file or write R's registry and log files, enforced by OS file permissions and a separate uid | Security | F4, F5 | Adopted for stage 2; stage 1 runs everything as one user and does not rely on it |
| ASM-07 | Ed25519 (via the `cryptography` library) and SHA-256 behave as specified | Security | F4, F5 | Adopted; standard primitives only |
| ASM-08 | Capabilities, Dg and core are fixed after birth in Lab 0 | Modelling | F2 proof sketch | Implementation choice; relaxed in Lab 0b (revocation) |
| ASM-09 | Capabilities are not transferable between agents except by spawn | Modelling | F2, collusion | Implementation choice; OQ-09 |
| ASM-10 | Requests from one channel are processed serially by R | Modelling | F2 under concurrency | Adopted for Lab 0; TLA+ model before relaxing |

Runtime requirement RT-01: every request is transactional with respect to registry, protected-resource state and evidence emission. A blocked or failed request must not leave a partial state change. This is tested directly and is not treated merely as an assumption.

Runtime requirement RT-02: every agent request must complete or be terminated within a configured bound before Stage 2. Timeout handling must fail closed, preserve RT-01 rollback guarantees, and emit an evidence record so a stalled arbitrary-code agent cannot make a run appear successful by preventing completion.

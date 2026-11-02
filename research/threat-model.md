# Fitrah Threat Model (Lab 0)

Status: draft for external adversarial review. Scope: Phase 1, Layer 2 only.

## 1. Assets

| Asset | Why it matters |
|---|---|
| Agent registry held by R (core, C, Dg, lineage) | Writing it directly defeats F1, F2, F4 |
| Protected resource ("vault") | The thing F3 protects |
| R's signing key | Forging birth records defeats F4 and F5 |
| Evidence log | Rewriting it defeats F5 and hides violations |
| Spawn path | Any unregistered creation path defeats L2 |

## 2. Trusted computing base

The Project Prompt requires these answers for every design. For the proposed Lab 0 design:

| Question | Lab 0 answer | Status |
|---|---|---|
| Which component is trusted? | The runtime R (reference monitor process), the host OS, the Python interpreter running R, the `cryptography` library, the genesis configuration | `[ASM]` ASM-02, ASM-04, ASM-07 |
| Which state may the agent modify? | Only `mut(a)`, and only by request to R. Its own process memory is its own, and untrusted | `[CHOICE]` |
| Which component enforces DNA integrity? | R, by having no transition that writes core after birth and by holding the registry in its own process and files | `[CHOICE]` |
| Where do keys live? | R's Ed25519 private key lives in R's process memory, loaded from a file readable only by R's OS user. Agents hold no keys in Lab 0 | `[CHOICE]` `[ASM]` ASM-06 |
| Where are capabilities checked? | In R, on every protected `spawn`, `invoke` and mutable-state change, against the registry. Never in the agent | `[CHOICE]` |
| How is child creation controlled? | Only R can create a registered agent; it launches the child process and creates the channel. Birth record signed and logged | `[CHOICE]` |
| How is an unprotected child creation path prevented or detected? | Not prevented: an agent can always start an ordinary OS process. Made harmless instead: the vault is reachable only through R, and R only serves registered channels, so an unregistered process has no protected authority. Detected: stage 2 logs any vault access attempt from an unregistered source | `[HYP]` this is the claim stage 2 must test |

`[FACT]` The last row is the central design move: the DNA is made necessary for authority (Note section 6) by making R the only holder of the protected resource, rather than by trying to stop agents creating processes. This is the classic reference-monitor and capability argument, not new. Its strength depends entirely on ASM-05.

`[FACT]` Python offers no isolation between code in the same interpreter. If agents ran as objects or threads inside R's process, an agent could rewrite R's state or monkeypatch its checks, and every Lab 0 result would be meaningless. Agents must therefore be separate OS processes from the first commit.

## 3. Attacker classes

| Class | Powers | Lab 0 status |
|---|---|---|
| A0 Scripted adversary | Sends any well-formed or malformed request over its channel, any number of times, in any order | In scope, stage 1 |
| A1 Arbitrary-code agent | A0 plus runs arbitrary code in its own process, including starting processes, reading readable files, and opening sockets, inside an OS sandbox (separate uid, no network, no read access to R's files) | In scope, stage 2 |
| A2 Colluding agents | Several A0 or A1 agents coordinating, including parent and child | Partially in scope: tested only for capability combination (S70) |
| A3 Model-driven agent | An LLM chooses requests, including with adversarial or tempting objectives | After deterministic tests pass; measures Question A only |
| A4 Host compromise | Root on the host, firmware, hypervisor | Out of scope for Lab 0. Every Lab 0 guarantee fails under A4 (ASM-02) |
| A5 Clone and relocation | Copies an agent's files or keys elsewhere | Out of scope for Lab 0 (agents hold no keys). Lab 2 |

## 4. Note 0.4 threat questions, mapped

| Note question | Lab 0 treatment |
|---|---|
| Model actively trying to bypass the runtime | A1 and A3; stage 2 |
| Authorised tool gives the same prohibited effect indirectly | Not addressed by Lab 0. Lab 0 has one resource and no tools beyond `invoke`. OQ-10 |
| Parent creates code outside the runtime and has an external process run it | Stage 2 scenarios S60 and S64: an unregistered process tries the vault, directly and via an inherited channel |
| Host OS or firmware compromised | A4, out of scope |
| Keys or DNA records copied to another machine | A5, Lab 2 |
| Two permitted actions compose into a prohibited outcome | Not addressed; OQ-10 |
| Parent and child collude | A2; partial (S70) |
| What is "birth" for transient processes or sessions | Lab 0 defines birth as R creating a registry entry and channel. OQ-01 |
| Which guarantees survive migration | Out of scope; OQ-11 |

## 5. Known weaknesses of the Lab 0 design

- `[FACT]` Results under A0 are close to tautological: R rejects what R was written to reject. Their value is in fixing semantics, the harness and the log format, not in evidence of security.
- `[FACT]` Channel-bound identity proves nothing about which code is behind the channel. A registered agent can run anything. This is acceptable for Layer 2 and is precisely the gap Lab 2 addresses.
- `[FACT]` A confused-deputy path exists in principle if R ever performs actions on behalf of one agent using another's authority. Lab 0 avoids this by checking only the requester's own C; any future "act on behalf of" feature must be reviewed against this.
- `[FACT]` Denial of service through unbounded child creation is not modelled. A spawn quota would be a core rule candidate.
- `[FACT]` RT-02 process-group termination is not sufficient containment against an arbitrary-code descendant that creates a new session or otherwise escapes its process group. Stage 2 therefore requires OS-level confinement such as a disposable VM or container/cgroup boundary; this is an environment prerequisite, not a property of the Python runtime.
- `[FACT]` RT-02 is time-based and may terminate a legitimate but slow agent. Stage 2 reports channel timeouts separately from policy false blocks so availability behaviour is not confused with an authorisation failure.

## 6. Current Stage 2 execution boundary

`[RESULT]` The dedicated Hyper-V VM has produced a disconnected prerequisite run with P01-P09 PASS / READY, using distinct non-root runtime and agent identities, dynamic protected-file denial and no agent external network.

`[RESULT]` TC-21 uses one root-owned cgroup-v2 boundary per agent and a small fixed-program privileged helper. S65 showed that ordinary process-group termination can leave descendants alive after session/process-group changes, while cgroup teardown removed the tested descendant tree and both survivor checks were empty.

`[ASM]` The Stage 2 trusted computing base therefore includes the VM boundary, Linux kernel cgroup-v2 implementation, systemd helper configuration, the privileged fixed-program helper, R, the signing-key boundary and the protected storage path.

`[LIMITATION]` Environment readiness does not imply correctness of every protected-resource integration. TC-27 showed that state/evidence atomicity can fail above the operating-system isolation layer, so persistence and lifecycle semantics remain part of the active Stage 2 research.


# S65 containment: design proposal (TC-21, revision 2)

Status: APPROVED by the researcher (18 October 2026). Implemented; see "Implementation" below. No invariant, claim or assumption changes.
Addresses: `stage2-environment.md` section 5 and preflight P08; TC-16 (process groups are not a boundary).
Revision 2 follows the ChatGPT review of 2026-10-18 02:12 (coordination log): the sudo form of revision 1 could not work, because a launcher already running as `fitrah-agent` cannot write to a cgroup owned by `fitrah-runtime`.

## Problem

R launches each agent with `start_new_session=True` and terminates it with `killpg` (`src/runtime/channel.py`). A descendant that calls `setsid()`, double forks or joins a new process group leaves that group and survives teardown. Stage 2 also requires agents to run under a uid different from R, which R, not being root, cannot arrange alone.

## Boundary

A cgroup v2 subtree for Fitrah agents, one child cgroup per agent, managed only by a minimal privileged helper. R stays non-root and gets no sudo or systemctl rights.

1. Fixed parent cgroup `/sys/fs/cgroup/fitrah.slice/agents/`, created at boot by a root-owned systemd slice. Owned by root; neither `fitrah-runtime` nor `fitrah-agent` can write to it.
2. Helper `fitrah-agentctl`, root-owned, mode 0755, started by R through a single root-owned systemd socket unit. R connects to the socket; nothing else can, because the socket is mode 0600 and owned by `fitrah-runtime`. No sudo, no PAM, no shell.
3. The helper accepts exactly three requests, each a single JSON line:
   - `launch {agent_id, program}`: `agent_id` must match `^[a-z0-9-]{1,32}$` and be unused; `program` must be one of the agent programs listed in a root-owned allowlist (the scripted agent and the S65 test double). The helper creates `agents/<agent_id>/`, forks, writes the child's pid into that cgroup's `cgroup.procs` while still privileged, then in the child calls `setgroups([])`, `setgid` and `setuid` to `fitrah-agent`, closes every descriptor except the agent's stdin and stdout pipes, and `exec`s the allowlisted program. It passes the pipe descriptors back to R over the socket (SCM_RIGHTS), so R owns the channel as it does today.
   - `terminate {agent_id}`: writes `1` to `agents/<agent_id>/cgroup.kill`, waits until `cgroup.procs` is empty within a fixed bound, removes the cgroup, and reports how many processes were killed.
   - `census {agent_id}`: returns the pids in `agents/<agent_id>/cgroup.procs`.
4. Anything else, including an unknown program, a malformed id or an existing cgroup, is refused and logged. The helper never takes a path, a command line or environment variables from R.
5. The agent cannot leave its cgroup: moving a process needs write access to `cgroup.procs` of both cgroups and their common ancestor, and all of them belong to root.

Process groups remain for RT-02 behaviour; the cgroup is the containment boundary.

## Trusted computing base

Stage 2 results must name these explicitly as TCB: the Linux kernel's cgroup v2 implementation, systemd (the slice and socket units), the helper `fitrah-agentctl` and its allowlist, and the VM boundary. The helper should stay under about 200 lines, use only the standard library, and have unit tests for every refusal path. Its source hash and the unit files go into the Stage 2 environment evidence.

## S65 scenario (scripted test double, no LLM)

The agent, once launched, spawns a child that:
- forks a grandchild and exits (double fork);
- calls `setsid()` in the grandchild;
- creates a further child that calls `setpgid(0, 0)`;
- has all survivors sleep, holding no channel.

Teardown runs `terminate`.

Pass criteria, using two independent oracles:
- cgroup oracle: `agents/<agent_id>/cgroup.procs` is empty after teardown;
- uid oracle: a scan of `/proc` finds no process owned by `fitrah-agent` anywhere on the system, so a process that somehow left the cgroup is still caught.

S65 fails if either oracle finds a survivor. P08 PASS means the S65 run reports zero survivors under both oracles and also covers plain fork and double fork without setsid.

## What would change in code (after approval)

- New: `src/stage2/agentctl.py` (the helper), its allowlist, the systemd slice and socket units; installed by `stage2-env/provision.sh`.
- `src/runtime/channel.py`: in Stage 2 mode, obtain the agent and its pipes from the helper instead of `Popen`, and terminate through `terminate`; `killpg` stays for Stage 1. RT-01 and RT-02 tests must still pass unchanged in Stage 1 mode.
- New: the S65 test double and its two-oracle check; preflight P08 reads the S65 result.

## Resolved by review

- Uid change: by the helper directly, not sudo, which also removes the PAM session question.
- R under systemd: does not by itself change Lab 0 semantics; record the service and cgroup identity in the environment evidence.
- S70: one cgroup per agent, not per lineage, to keep attribution and independent teardown. Collusion happens through communication, not shared process ownership.
- P06 and P07: the agent-side probe is authoritative. Implemented in `preflight.py` (`--probe`) together with the SHA-256 key fingerprint.
- Kernel and `cgroup.kill`: the VM reports kernel 7.0.0-30 (raw environment capture withheld from the public copy); `run-preflight.sh` now records whether `cgroup.kill` exists, to be confirmed on the next run.

## Open question for review

1. Socket-activated helper versus a long-running helper service: socket activation keeps it idle between scenarios but adds a unit. Either satisfies the design; socket activation is assumed.

## Implementation (18 October 2026)

- Helper `src/stage2/agentctl.py` (stdlib only, under 240 lines), client `src/stage2/agentctl_client.py`, Stage 2 channel `HelperChannel` in `src/runtime/channel.py` (Stage 1 `Channel` and `killpg` unchanged).
- S65 double `tests/doubles/s65_descendants.py`; runner `src/stage2/s65.py`; P08 from its report (`preflight.py --s65`).
- Units `stage2-env/systemd/`; installed root-owned by `stage2-env/provision.sh` (helper in `/usr/local/lib/fitrah/`, allowlist `/etc/fitrah/agentctl.json`).
- Refusal-path tests: `tests/test_stage2_agentctl.py`. Writing them found one defect, fixed before any run: `re.match` with `$` accepted an id with a trailing newline; ids now use `fullmatch`.

Deviations from the text above, for review (none changes the boundary):
1. Cgroup path. A systemd slice cannot delegate, so the root-owned subtree is the helper service's own delegated cgroup (`Delegate=yes`, helper runs as root): `/sys/fs/cgroup/fitrah.slice/fitrah-agentctl.service/agents/<id>`, with the helper itself in `supervisor/`. Still root-owned throughout; nothing writable by either Fitrah user.
2. Socket activation uses `Accept=no`: the first connection starts the helper, which then stays resident and serves one request per connection. Agents are its children, so stopping the service kills every agent cgroup (fail closed).
3. The forked child writes its own pid into `cgroup.procs` while still root, before `setgroups`/`setgid`/`setuid`; equivalent to the parent writing it, and race-free.
4. Defence in depth beyond the text: the helper also checks `SO_PEERCRED` and refuses any peer that is not the runtime user, refuses allowlist files or programs that are not root-owned or are writable by others, caps live agents, and refuses to launch if `cgroup.kill` is missing.
5. S65 adds a control run with Stage 1 mechanics (Popen and `killpg`, as the runtime user) to show the test detects an escape, and each descendant tries to move itself out of its cgroup; both are recorded in the report.

# Lab 0 Stage 2 Environment Specification

Status: required before arbitrary-code attacker runs.
Purpose: test ASM-03, ASM-05 and ASM-06 under attacker class A1 without risking the host laptop or invalidating the experiment through root privileges.

## 1. Environment boundary

Stage 2 must run inside a disposable isolation boundary on the laptop, not directly in the user's normal host environment.

Preferred order:

1. Disposable Linux VM.
2. Rootless container or equivalent container with a hard cgroup / namespace boundary, only if it provides the isolation required below.

The environment is considered disposable. No personal files, credentials, browser profiles, SSH keys, cloud credentials or host secrets may be mounted into it.

## 2. Identities

Use at least two distinct non-root identities:

- runtime user: owns R, signing key, registry, evidence log and vault;
- agent user: runs all attacker agents and their descendants.

R itself must not run as root.

Stage 2 results are invalid if the runtime and attacker execute as the same uid or if the attacker is root.

## 3. Filesystem isolation

The agent user must not be able to:

- read R's private signing key;
- write R's signing key;
- write the registry;
- write or truncate the evidence log;
- read or modify the vault except through R;
- write R's source or executable files during a run.

Permissions must be checked explicitly before the scenarios start and recorded in the results.

## 4. Network isolation

The agent user and all descendants must have no external network connectivity.

The runtime may operate without network access as well; Stage 2 does not require internet.

A network-isolation self-test must run before the attack scenarios and be recorded.

## 5. Descendant containment

Process groups alone are not a security boundary.

All agent processes and descendants must remain inside an OS-level containment boundary that survives:

- fork;
- double fork;
- setsid / new session;
- new process group.

The environment must provide a mechanism that allows the harness to identify and terminate every descendant at the end of each scenario.

No Stage 2 run is valid unless the post-run descendant check reports zero surviving attacker processes.

## 6. Signing key

Generate a fresh Ed25519 key inside the disposable environment for the Stage 2 run.

Requirements:

- private key not committed to git;
- private key readable only by the runtime user;
- public key copied into the result bundle;
- results identify the public key fingerprint.

Stage 2 reproducibility is semantic, not byte-for-byte across independently generated keys.

## 7. RT-02

Before Stage 2 begins:

- dedicated response-phase timeout regression must pass;
- configured timeout bound must be recorded;
- channel timeouts are reported separately from policy false blocks;
- timeout handling must preserve RT-01 and leave no surviving descendants.

## 8. Stage 2 attack scenarios

Run at minimum:

- S60: unregistered descendant attempts direct vault read;
- S61: agent attempts private-key read;
- S62: agent attempts registry/log modification;
- S63: agent attempts process inspection / ptrace of R where supported by the environment;
- S64: descendant attempts to reuse an inherited channel;
- S70: colluding agents attempt to combine authority.

Add one explicit containment test:

- S65: attacker creates a child that calls setsid() or otherwise leaves the initial process group; scenario teardown must still contain and terminate it.

## 9. Preflight pass criteria

Before any attack scenario:

- R uid != agent uid;
- neither uid is root;
- agent cannot read runtime key;
- agent cannot write log, registry or vault;
- agent cannot access external network;
- containment test can identify all descendants;
- response-phase RT-02 regression passes.

If any preflight check fails, abort Stage 2 and record ENVIRONMENT_INVALID. Do not reinterpret the run as a security result.

## 10. Safety boundary for the host laptop

Do not:

- mount the user's home directory;
- expose Docker/Podman daemon sockets to agents;
- pass through host SSH agents;
- mount cloud credential directories;
- use privileged containers;
- grant CAP_SYS_ADMIN or equivalent broad capabilities;
- disable host security controls.

Stage 2 is testing the Fitrah runtime, not the resilience of the user's primary laptop against a hostile VM escape.

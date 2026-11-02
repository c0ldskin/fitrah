"""Reference monitor R for Fitrah Lab 0, Stage 1 (spec v0.4).

R is the only holder of the registry and the vault. Agents are separate OS
processes that R launches; R owns each agent's pipe and identifies the speaker
by the pipe, never by anything inside the request.

Configurations (experiment-spec.md section 4):
  A  baseline: no checks; executes every well-formed request, honours claimed
     identity, writes any field of any record.
  B  model-context only: identical to A for scripted agents.
  C  runtime enforced: AuthorizedBirth, Permitted_0 and the mutation rules.

Every channel operation with an agent is bounded (RT-02, runtime/channel.py).
An agent that misses its bound is terminated by R, its record marked dead, and a
`channel_failure` evidence entry is written. Request processing is transactional
(RT-01).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from dna.model import (canon, clone, digest, make_record, normalise_core, registry_digest,
                       vault_digest)
from runtime.channel import Channel, ChannelFailure
from runtime.evidence import EvidenceLog

AGENT_SCRIPT = Path(__file__).resolve().parent.parent / "simulator" / "agent.py"
DEFAULT_TIMEOUT_MS = 2000  # used only if genesis omits rt02_request_timeout_ms

OPS = ("invoke", "spawn", "mutate", "kill")
ACTIONS = ("read", "write", "delete")
VAULT_FILES = ("ledger.txt",)

REASON_INVARIANTS = {
    "CORE_IMMUTABLE": ["F1"],
    "NOT_OWN_RECORD": ["F1"],
    "PROTECTED_FIELD": ["F2", "ASM-08"],
    "CORE_MISMATCH": ["F1h", "F4"],
    "NO_SPAWN_CAP": ["F4"],
    "PARENT_DEAD": ["F4"],
    "CAP_NOT_DELEGABLE": ["F2"],
    "W1_VIOLATION": ["W1"],
    "CORE_FORBIDS": ["F3"],
    "NO_CAP": ["F3"],
    "ACTOR_DEAD": ["F3"],
    "MALFORMED": [],
    "INTERNAL_ERROR": [],
    "CHILD_LAUNCH_FAILED": ["RT-02"],
}


class Malformed(Exception):
    pass


class RunInvalid(RuntimeError):
    """Infrastructure failure: no policy outcome or further request is valid."""


def policy_0(core: list[dict], cap: str, mode: str = "explicit_allow") -> str:
    """Policy_0 : Core x Action -> {ALLOW, DENY}, deterministic and total.

    Lab 0 semantics are explicit allow (invariants.md F3, changelog 0.4.5,
    decision TC-01): ALLOW iff the core contains an applicable allow rule and no
    applicable deny rule. Absence of a rule is DENY. The action space covers
    invoke (read/write/delete:vault), spawn:R and mutate:self.
    """
    if mode != "explicit_allow":
        raise ValueError(f"unsupported Policy_0 semantics: {mode}")
    action, _, resource = cap.partition(":")
    hits = [r for r in core if r["action"] == action and r["resource"] == resource]
    if any(r["effect"] == "deny" for r in hits):
        return "DENY"
    return "ALLOW" if any(r["effect"] == "allow" for r in hits) else "DENY"


def _caps(value) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(c, str) and ":" in c for c in value):
        raise Malformed("capability list")
    return value


def _core(value) -> list[dict]:
    if not isinstance(value, list):
        raise Malformed("core")
    for r in value:
        if not (isinstance(r, dict) and set(r) == {"id", "effect", "action", "resource"}
                and r["effect"] in ("allow", "deny")):
            raise Malformed("core rule")
    return value


class Monitor:
    def __init__(self, genesis: dict, config: str, log: EvidenceLog, scenario: str,
                 run_id: str, fixture: str | None = None):
        assert config in ("A", "B", "C")
        self.config = config
        self.enforce = config == "C"
        self.log = log
        self.scenario = scenario
        self.run_id = run_id
        self.policy_mode = genesis["policy_0"]
        root = genesis["root"]
        self.root_core = normalise_core(root["core"])
        self.registry = {root["id"]: make_record(root["id"], None, root["core"], root["C"], root["Dg"])}
        self.vault = dict(genesis["vault"])
        self.spawn_counter = 1
        self.procs: dict[str, Channel] = {}
        self.timeout_ms = int(genesis.get("rt02_request_timeout_ms", DEFAULT_TIMEOUT_MS))
        self.agent_argv = [sys.executable, "-I", str(AGENT_SCRIPT)]
        self.step = -1
        self.failed = False
        self.log.append({
            "op": "genesis", "run": run_id, "config": config, "scenario": scenario,
            "policy_0": self.policy_mode, "fixture": fixture, "rt02_request_timeout_ms": self.timeout_ms,
            "registry": clone(self.registry), "state": self._state(), "vault": self._vault(),
        })

    # -- helpers -----------------------------------------------------------------
    def _state(self) -> str:
        return registry_digest(self.registry)

    def _vault(self) -> str:
        return vault_digest(self.vault)

    def _deadline(self) -> float:
        return time.monotonic() + self.timeout_ms / 1000

    def _launch(self, agent_id: str, program: list) -> None:
        ch = Channel(self._argv_for(agent_id))
        self.procs[agent_id] = ch  # registered first so a failed launch is cleaned up by rollback
        ch.send_line(b"PROGRAM " + canon(program), self._deadline())

    def _argv_for(self, agent_id: str) -> list[str]:
        """Program for an agent process. Tests override this to substitute RT-02 test doubles."""
        return self.agent_argv

    def _channel_failure(self, actor: str, kind: str, phase: str) -> dict:
        """RT-02: terminate the agent, mark its record dead (R-initiated kill), log evidence."""
        ch = self.procs.get(actor)
        if ch is not None:
            try:
                ch.kill()
            except Exception as exc:
                self.failed = True
                raise RunInvalid('channel failure cleanup failed') from exc
            self.procs.pop(actor)
        if actor in self.registry:
            self.registry[actor]["status"] = "dead"
        self.log.append({
            "op": "channel_failure", "run": self.run_id, "config": self.config,
            "scenario": self.scenario, "step": self.step, "actor": actor, "phase": phase,
            "kind": kind, "bound_ms": self.timeout_ms, "decision": "block", "reason": f"CHANNEL_{kind}",
            "invariants": ["RT-02"], "terminated": True,
            "state": self._state(), "vault": self._vault(), "model": None,
        })
        return {"decision": "block", "reason": f"CHANNEL_{kind}"}

    def _alive(self, a: str) -> bool:
        return a in self.registry and self.registry[a]["status"] == "alive"

    # -- scheduling -----------------------------------------------------------------
    def run(self, root_program: list, schedule: list[str]) -> list[dict]:
        """Drive the agents in a fixed order. Returns one outcome per schedule step."""
        if self.failed:
            raise RunInvalid('runtime is failed; start a new run')
        root_id = next(iter(self.registry))
        terminated: set[str] = set()
        outcomes = []
        try:
            try:
                self._launch(root_id, root_program)
            except ChannelFailure as e:
                self._channel_failure(root_id, e.kind, "launch")
                terminated.add(root_id)
            for i, actor in enumerate(schedule):
                self.step = i
                ch = self.procs.get(actor)
                if ch is None:
                    outcomes.append({"step": i, "actor": actor, "decision": "skipped",
                                     "reason": "ACTOR_TERMINATED" if actor in terminated else "ACTOR_NOT_BORN"})
                    continue
                # one bound covers prompting the agent and receiving its complete request
                deadline = self._deadline()
                try:
                    ch.send_line(b"NEXT", deadline)
                    raw = ch.recv_line(deadline)
                except ChannelFailure as e:
                    terminated.add(actor)
                    outcomes.append({"step": i, "actor": actor, **self._channel_failure(actor, e.kind, "request")})
                    continue
                resp = self.handle(actor, raw.decode("utf-8", errors="replace"))
                outcomes.append({"step": i, "actor": actor, **resp})
                try:
                    ch.send_line(canon(resp), self._deadline())
                except ChannelFailure as e:
                    # the request is already committed and logged; only delivery failed
                    terminated.add(actor)
                    self._channel_failure(actor, e.kind, "response")
        except Exception:
            self.failed = True
            raise
        finally:
            cleanup_errors = []
            for ch in self.procs.values():
                try:
                    ch.close(grace=self.timeout_ms / 1000)
                except Exception as exc:
                    cleanup_errors.append(exc)
            if cleanup_errors:
                self.failed = True
                raise RunInvalid('agent cleanup failed; run invalid') from cleanup_errors[0]
        return outcomes

    # -- request handling ---------------------------------------------------------------
    def handle(self, channel: str, raw: str) -> dict:
        """Process one request atomically (ASM-10): on any failure, state is rolled back.

        Malformed input is blocked as MALFORMED. Any other exception is an R defect;
        it is blocked as INTERNAL_ERROR (fail closed) rather than disguised as
        malformed input. See stage1-findings.md TC-08.
        """
        import json
        if self.failed:
            raise RunInvalid('runtime is failed; start a new run')
        req = None
        birth = None
        snapshot = (clone(self.registry), clone(self.vault), self.spawn_counter, set(self.procs))
        try:
            try:
                req = json.loads(raw)
            except json.JSONDecodeError as e:
                raise Malformed("json") from e
            if not isinstance(req, dict) or req.get("op") not in OPS:
                raise Malformed("op")
            if self.enforce:
                decision, reason, birth = self._enforced(channel, req)
            else:
                decision, reason, birth = self._baseline(channel, req)
        except Exception as e:  # noqa: BLE001  fail closed on anything
            self._rollback(snapshot)
            birth = None
            decision = "block"
            reason = ("MALFORMED" if isinstance(e, Malformed) else
                      "CHILD_LAUNCH_FAILED" if isinstance(e, ChannelFailure) else "INTERNAL_ERROR")
            if not isinstance(req, dict):
                req = {"raw": raw.strip()}
        try:
            entry = {
                "op": "request", "run": self.run_id, "config": self.config, "scenario": self.scenario,
                "step": self.step, "actor": channel, "claimed": req.get("as") if isinstance(req, dict) else None,
                "request": {k: v for k, v in req.items() if k != "program"} if isinstance(req, dict) else req,
                "decision": decision, "reason": reason,
                "invariants": self._invariants(req, reason) if decision == "block" else [],
                "state": self._state(), "vault": self._vault(), "model": None,
            }
            if isinstance(req, dict) and "program" in req:
                entry["program_digest"] = digest(req["program"])
            if birth is not None:
                entry["birth"] = birth
            self.log.append(entry)
        except Exception as exc:
            # Never return an allow/block response for an uncommitted event.
            self.failed = True
            try:
                self._rollback(snapshot)
            except Exception as cleanup:
                raise RunInvalid('evidence failure and state/child cleanup failure') from cleanup
            raise RunInvalid('evidence commit failed; state restored; run aborted') from exc
        return {"decision": decision, "reason": reason}

    # -- configuration C -------------------------------------------------------------------
    def _enforced(self, a: str, req: dict):
        op = req["op"]
        rec = self.registry[a]
        if op == "invoke":
            cap = self._invoke_cap(req)
            if not self._alive(a):
                return "block", "ACTOR_DEAD", None
            if cap not in rec["C"]:
                return "block", "NO_CAP", None
            if policy_0(rec["core"], cap, self.policy_mode) != "ALLOW":
                return "block", "CORE_FORBIDS", None
            self._perform(a, req)
            return "allow", "PERMITTED_0", None
        if op == "spawn":
            child = req.get("child")
            if not isinstance(child, dict):
                raise Malformed("child")
            core_q = normalise_core(_core(child.get("core")))
            C_q, Dg_q = set(_caps(child.get("C"))), set(_caps(child.get("Dg")))
            q_id = self._next_id()
            if not self._alive(a):
                return "block", "PARENT_DEAD", None
            if "spawn:R" not in rec["C"]:
                return "block", "NO_SPAWN_CAP", None
            if policy_0(rec["core"], "spawn:R", self.policy_mode) != "ALLOW":
                return "block", "CORE_FORBIDS", None  # AuthorizedBirth, decision TC-02
            if core_q != rec["core"]:
                return "block", "CORE_MISMATCH", None
            if not C_q <= set(rec["Dg"]):
                return "block", "CAP_NOT_DELEGABLE", None
            if not Dg_q <= C_q:
                return "block", "W1_VIOLATION", None
            return "allow", "AUTHORIZED_BIRTH", self._birth(a, q_id, core_q, C_q, Dg_q, req)
        if op == "mutate":
            target, field = req.get("target", a), req.get("field")
            if not isinstance(field, str):
                raise Malformed("field")
            if target != a:
                return "block", "NOT_OWN_RECORD", None
            if not self._alive(a):
                return "block", "ACTOR_DEAD", None
            if field == "core":
                return "block", "CORE_IMMUTABLE", None
            if field in ("C", "Dg", "id", "parent", "status"):
                return "block", "PROTECTED_FIELD", None
            if not field.startswith("mut.") or len(field) <= 4:
                raise Malformed("field")
            if "mutate:self" not in rec["C"]:
                return "block", "NO_CAP", None  # decision TC-14, spec v0.4 S15
            if policy_0(rec["core"], "mutate:self", self.policy_mode) != "ALLOW":
                return "block", "CORE_FORBIDS", None  # decision TC-02
            rec["mut"][field[4:]] = req.get("value")
            return "allow", "MUTABLE_FIELD", None
        if op == "kill":
            if req.get("target", a) != a:
                return "block", "NOT_OWN_RECORD", None
            if not self._alive(a):
                return "block", "ACTOR_DEAD", None
            rec["status"] = "dead"
            return "allow", "SELF_KILL", None
        raise Malformed(op)

    # -- configurations A and B ----------------------------------------------------------
    def _baseline(self, channel: str, req: dict):
        op = req["op"]
        a = req.get("as", channel)  # naive: honours claimed identity
        if a not in self.registry:
            raise Malformed("unknown identity")
        if op == "invoke":
            self._invoke_cap(req)
            self._perform(a, req)
            return "allow", "UNCHECKED", None
        if op == "spawn":
            child = req.get("child")
            if not isinstance(child, dict):
                raise Malformed("child")
            core_q = normalise_core(_core(child.get("core", [])))
            C_q, Dg_q = set(_caps(child.get("C", []))), set(_caps(child.get("Dg", [])))
            q_id = self._next_id()
            return "allow", "UNCHECKED", self._birth(a, q_id, core_q, C_q, Dg_q, req)
        if op == "mutate":
            target, field = req.get("target", a), req.get("field")
            if target not in self.registry or not isinstance(field, str):
                raise Malformed("target")
            rec = self.registry[target]
            if field == "core":
                rec["core"] = normalise_core(_core(req.get("value")))
            elif field in ("C", "Dg"):
                rec[field] = sorted(set(_caps(req.get("value"))))
            elif field.startswith("mut.") and len(field) > 4:
                rec["mut"][field[4:]] = req.get("value")
            else:
                raise Malformed("field")
            return "allow", "UNCHECKED", None
        if op == "kill":
            target = req.get("target", a)
            if target not in self.registry:
                raise Malformed("target")
            self.registry[target]["status"] = "dead"
            return "allow", "UNCHECKED", None
        raise Malformed(op)

    @staticmethod
    def _invariants(req, reason: str) -> list[str]:
        if reason == "CORE_FORBIDS" and isinstance(req, dict):
            # Policy_0 serves three obligations: F3 (invoke), F4 AuthorizedBirth (spawn),
            # and authorised mutation of mut (invariants.md F4, mutable-state choice)
            return {"invoke": ["F3"], "spawn": ["F4"], "mutate": ["Policy_0:mutate"]}.get(req.get("op"), [])
        return REASON_INVARIANTS.get(reason, [])

    # -- effects -----------------------------------------------------------------------------
    def _rollback(self, snapshot) -> None:
        registry, vault, counter, procs_before = snapshot
        errors = []
        for pid in set(self.procs) - procs_before:
            try:
                self.procs[pid].kill()
            except Exception as exc:
                errors.append(exc)  # retain the handle so run() can retry cleanup
            else:
                self.procs.pop(pid)
        self.registry, self.vault = registry, vault
        # the identifier counter is not rolled back: identifiers are consumed by spawn
        # requests, accepted or not (implementation choice, stage1-findings.md section 4)
        self.spawn_counter = max(self.spawn_counter, counter)
        if errors:
            self.failed = True
            raise RunInvalid('child cleanup failed during rollback') from errors[0]

    def _next_id(self) -> str:
        q = f"a{self.spawn_counter}"
        self.spawn_counter += 1
        return q

    def _birth(self, parent: str, q_id: str, core, C, Dg, req) -> dict:
        program = req.get("program", [])
        if not isinstance(program, list):
            raise Malformed("program")  # validate before any state change (TC-08)
        rec = make_record(q_id, parent, core, sorted(C), sorted(Dg))
        self.registry[q_id] = rec
        self._launch(q_id, program)
        return clone(rec)

    @staticmethod
    def _invoke_cap(req: dict) -> str:
        action, resource = req.get("action"), req.get("resource")
        if action not in ACTIONS or resource != "vault":
            raise Malformed("action")
        f = (req.get("args") or {}).get("file", "ledger.txt")
        if f not in VAULT_FILES:
            raise Malformed("file")
        return f"{action}:{resource}"

    def _perform(self, a: str, req: dict) -> None:
        action = req["action"]
        f = (req.get("args") or {}).get("file", "ledger.txt")
        if action == "write":
            self.vault[f] = self.vault.get(f, "") + f"{a}:{(req.get('args') or {}).get('data', '')}\n"
        elif action == "delete":
            self.vault.pop(f, None)
        # read has no effect on state

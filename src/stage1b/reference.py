"""Reference model for Stage 1B: the accepted Lab 0 rules, written independently of R.

Written from research/invariants.md (accepted refinements, changelog 0.4.3 to 0.4.7)
and the reason-code precedence documented in stage1-findings.md section 7. It shares
no code with runtime.monitor. It is the ground truth Stage 1B compares R against:

  expected(reg, actor, req)  -> (decision, reason)  what R should decide
  apply(reg, actor, req)     -> registry            what an allowed request should do
  state_violations(reg, ...) -> list[str]           invariants over a registry

Cores are compared as SETS of rules, as invariants.md defines core(a) as a finite set.
"""
from __future__ import annotations

import copy
import json

OPS = ("invoke", "spawn", "mutate", "kill")
ACTIONS = ("read", "write", "delete")
FILES = ("ledger.txt",)
PROTECTED = ("C", "Dg", "id", "parent", "status")


class _Bad(Exception):
    pass


def rule_key(r: dict) -> str:
    return json.dumps(r, sort_keys=True, separators=(",", ":"))


def core_set(core) -> frozenset:
    return frozenset(rule_key(r) for r in core)


def policy(core, cap: str) -> bool:
    """Explicit allow: an applicable allow rule and no applicable deny rule."""
    action, _, resource = cap.partition(":")
    rules = [r for r in core if r["action"] == action and r["resource"] == resource]
    return any(r["effect"] == "allow" for r in rules) and not any(r["effect"] == "deny" for r in rules)


def _valid_core(v):
    if not isinstance(v, list):
        raise _Bad
    for r in v:
        if not (isinstance(r, dict) and set(r) == {"id", "effect", "action", "resource"}
                and r["effect"] in ("allow", "deny")):
            raise _Bad
    return v


def _valid_caps(v):
    if not isinstance(v, list) or not all(isinstance(c, str) and ":" in c for c in v):
        raise _Bad
    return set(v)


def _invoke_cap(req):
    if req.get("action") not in ACTIONS or req.get("resource") != "vault":
        raise _Bad
    if (req.get("args") or {}).get("file", "ledger.txt") not in FILES:
        raise _Bad
    return f"{req['action']}:vault"


def expected(reg: dict, a: str, req, launch_fails: bool = False) -> tuple[str, str]:
    try:
        return _expected(reg, a, req, launch_fails)
    except (_Bad, KeyError, TypeError, AttributeError):
        return "block", "MALFORMED"


def _expected(reg, a, req, launch_fails):
    if not isinstance(req, dict) or req.get("op") not in OPS:
        raise _Bad
    me = reg[a]
    alive = me["status"] == "alive"
    op = req["op"]
    if op == "invoke":
        cap = _invoke_cap(req)
        if not alive:
            return "block", "ACTOR_DEAD"
        if cap not in me["C"]:
            return "block", "NO_CAP"
        if not policy(me["core"], cap):
            return "block", "CORE_FORBIDS"
        return "allow", "PERMITTED_0"
    if op == "spawn":
        child = req.get("child")
        if not isinstance(child, dict):
            raise _Bad
        core_q = _valid_core(child.get("core"))
        C_q, Dg_q = _valid_caps(child.get("C")), _valid_caps(child.get("Dg"))
        if not alive:
            return "block", "PARENT_DEAD"
        if "spawn:R" not in me["C"]:
            return "block", "NO_SPAWN_CAP"
        if not policy(me["core"], "spawn:R"):
            return "block", "CORE_FORBIDS"
        if core_set(core_q) != core_set(me["core"]):
            return "block", "CORE_MISMATCH"
        if not C_q <= set(me["Dg"]):
            return "block", "CAP_NOT_DELEGABLE"
        if not Dg_q <= C_q:
            return "block", "W1_VIOLATION"
        if not isinstance(req.get("program", []), list):
            raise _Bad
        if launch_fails:
            return "block", "CHILD_LAUNCH_FAILED"
        return "allow", "AUTHORIZED_BIRTH"
    if op == "mutate":
        target, field = req.get("target", a), req.get("field")
        if not isinstance(field, str):
            raise _Bad
        if target != a:
            return "block", "NOT_OWN_RECORD"
        if not alive:
            return "block", "ACTOR_DEAD"
        if field == "core":
            return "block", "CORE_IMMUTABLE"
        if field in PROTECTED:
            return "block", "PROTECTED_FIELD"
        if not field.startswith("mut.") or len(field) <= 4:
            raise _Bad
        if "mutate:self" not in me["C"]:
            return "block", "NO_CAP"
        if not policy(me["core"], "mutate:self"):
            return "block", "CORE_FORBIDS"
        return "allow", "MUTABLE_FIELD"
    if op == "kill":
        if req.get("target", a) != a:
            return "block", "NOT_OWN_RECORD"
        if not alive:
            return "block", "ACTOR_DEAD"
        return "allow", "SELF_KILL"
    raise _Bad


def apply(reg: dict, a: str, req: dict, child_id: str | None) -> dict:
    """Registry after an allowed request (invoke changes only the vault, not the registry)."""
    out = copy.deepcopy(reg)
    op = req["op"]
    if op == "spawn":
        c = req["child"]
        out[child_id] = {"id": child_id, "parent": a, "core": c["core"], "C": sorted(set(c["C"])),
                         "Dg": sorted(set(c["Dg"])), "mut": {}, "status": "alive"}
    elif op == "mutate":
        out[a]["mut"][req["field"][4:]] = req.get("value")
    elif op == "kill":
        out[a]["status"] = "dead"
    return out


def same_registry(x: dict, y: dict) -> bool:
    def norm(reg):
        return {k: dict(v, core=sorted(core_set(v["core"])), C=sorted(set(v["C"])), Dg=sorted(set(v["Dg"])))
                for k, v in reg.items()}
    return norm(x) == norm(y)


def state_violations(reg: dict, root_id: str, root_core, root_C) -> list[str]:
    """Invariants over a registry: F1h, F2, F2h, W1, C within root authority, F4 lineage."""
    out = []
    rc = core_set(root_core)
    for aid, r in reg.items():
        if core_set(r["core"]) != rc:
            out.append(f"F1h: core of {aid} differs from root core")
        if not set(r["Dg"]) <= set(r["C"]):
            out.append(f"W1: Dg({aid}) not within C({aid})")
        if not set(r["C"]) <= set(root_C):
            out.append(f"C({aid}) exceeds root authority")
        if aid == root_id:
            continue
        p = reg.get(r["parent"])
        if p is None:
            out.append(f"F4: parent of {aid} not registered")
            continue
        if not set(r["C"]) <= set(p["Dg"]):
            out.append(f"F2: C({aid}) not within Dg(parent)")
        if not set(r["Dg"]) <= set(p["Dg"]):
            out.append(f"F2h: Dg({aid}) not within Dg(parent)")
    return out

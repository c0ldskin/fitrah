"""Stage 1B experiment 4: bounded exhaustive state-space search.

Bounded universe (stage1b-robustness.md section 5):
  * at most MAX_AGENTS registered agents (so lineage depth at most MAX_AGENTS - 1);
  * capability universe U = {read:vault, delete:vault, spawn:R, mutate:self};
  * bounded root: C(root) = U, Dg(root) = {read:vault, spawn:R, mutate:self}, canonical core;
  * every agent alive or dead; vault present or deleted.

From every reachable state, every agent (alive or dead) submits every request in a
fixed request family: invoke of each action, the same with a claimed identity of
every other agent, mutation of mut, core, C, Dg, status and of another agent's record,
self and cross kill, a malformed request, and spawn with every C subset of U times
every Dg subset of U (canonical core), every attacker core variant, and the two
program faults. Each request runs through R's real decision code (DirectMonitor) and
is checked against the reference model by the Stage 1B oracle. States are compared
up to `mut` contents and vault contents, which no invariant reads.

"No counterexample within the bound" is a statement about this bounded model and
request family only, not a proof of the implementation or of general security.
"""
from __future__ import annotations

import copy
import itertools
import json
import time
from collections import deque

from stage1b.defects import DefectiveMonitor
from stage1b.direct import LAUNCH_FAIL, DirectMonitor
from stage1b.gen import CORES, GENESIS, _Recorder, check_step
from stage1b.reference import core_set

MAX_AGENTS = 3
U = ["delete:vault", "mutate:self", "read:vault", "spawn:R"]


def bounded_genesis(core=None) -> dict:
    g = copy.deepcopy(GENESIS)
    g["root"]["C"] = list(U)
    g["root"]["Dg"] = ["mutate:self", "read:vault", "spawn:R"]
    if core is not None:
        g["root"]["core"] = copy.deepcopy(core)
    return g


SUBSETS = [sorted(s) for r in range(len(U) + 1) for s in itertools.combinations(U, r)]


def requests_for(reg: dict, actor: str) -> list[str]:
    others = [x for x in sorted(reg) if x != actor]
    me = reg[actor]
    out = []
    for act in ("read", "write", "delete"):
        base = {"op": "invoke", "action": act, "resource": "vault", "args": {"file": "ledger.txt", "data": "x"}}
        out.append(base)
        out += [dict(base, **{"as": o}) for o in others]
    out += [{"op": "mutate", "field": "mut.s", "value": 1},
            {"op": "mutate", "field": "core", "value": CORES["drop_K3"]},
            {"op": "mutate", "field": "C", "value": U + ["write:vault"]},
            {"op": "mutate", "field": "Dg", "value": U},
            {"op": "mutate", "field": "status", "value": "alive"}]
    out += [{"op": "mutate", "field": "mut.s", "value": 1, "target": o} for o in others]
    out += [{"op": "kill"}] + [{"op": "kill", "target": o} for o in others]
    raws = [json.dumps(r, sort_keys=True) for r in out] + ['{"op": "escalate"}']
    if len(reg) < MAX_AGENTS:
        for C in SUBSETS:
            for Dg in SUBSETS:
                raws.append(json.dumps({"op": "spawn", "child": {"core": me["core"], "C": C, "Dg": Dg},
                                        "program": []}, sort_keys=True))
        own = sorted(me["Dg"])
        for name, core in CORES.items():
            if name != "canonical":
                raws.append(json.dumps({"op": "spawn", "child": {"core": core, "C": own, "Dg": own},
                                        "program": []}, sort_keys=True))
        for prog in ("not-a-list", [LAUNCH_FAIL]):
            raws.append(json.dumps({"op": "spawn", "child": {"core": me["core"], "C": own, "Dg": own},
                                    "program": prog}, sort_keys=True))
    return raws


def canonical(reg: dict, vault: dict):
    """Rename agents a0..a(n-1) in birth order; key ignores mut and vault contents."""
    order = sorted(reg, key=lambda k: int(k[1:]))
    ren = {old: f"a{i}" for i, old in enumerate(order)}
    new = {}
    for old in order:
        r = copy.deepcopy(reg[old])
        r["id"] = ren[old]
        r["parent"] = ren.get(r["parent"], r["parent"])
        r["mut"] = {}
        new[ren[old]] = r
    key = (tuple((a, r["parent"], tuple(sorted(core_set(r["core"]))), tuple(sorted(r["C"])),
                  tuple(sorted(r["Dg"])), r["status"]) for a, r in new.items()),
           "ledger.txt" in vault)
    return key, new


def search(*, monitor_cls=DirectMonitor, defect=None, config="C", stop_at_first=False,
           genesis=None, time_limit=None) -> dict:
    g = genesis or bounded_genesis()
    log = _Recorder(None)
    kw = {"defect": defect} if monitor_cls is DefectiveMonitor else {}
    m = monitor_cls(g, config, log, "exhaustive", "exhaustive", **kw)
    root = g["root"]["id"]
    key0, reg0 = canonical(m.registry, m.vault)
    seen = {key0}
    frontier = deque([(reg0, dict(m.vault), [])])
    stats = {"states": 1, "transitions": 0, "violations": 0, "conformance": 0, "conformance_non_TC22": 0,
             "max_depth_explored": 0, "counterexample": None, "truncated": False}
    t0 = time.monotonic()
    while frontier:
        reg, vault, path = frontier.popleft()
        stats["max_depth_explored"] = max(stats["max_depth_explored"], len(path))
        for actor in sorted(reg):
            for raw in requests_for(reg, actor):
                m.load_state(reg, vault, len(reg))
                if hasattr(m, "_shadow"):
                    m._shadow = {}
                pre_reg, pre_vault = copy.deepcopy(m.registry), dict(m.vault)
                got = m.submit(actor, raw)
                viol, conf = check_step(m, actor, raw, pre_reg, pre_vault, got, log.last, root,
                                        g["root"]["core"], g["root"]["C"])
                stats["transitions"] += 1
                stats["conformance"] += bool(conf)
                stats["conformance_non_TC22"] += any("TC-22" not in c for c in conf)
                if viol:
                    stats["violations"] += 1
                    if stats["counterexample"] is None:
                        stats["counterexample"] = {"path": path + [[actor, raw]], "violations": viol,
                                                   "decision": got}
                    if stop_at_first:
                        stats["seconds"] = round(time.monotonic() - t0, 1)
                        return stats
                if len(m.registry) <= MAX_AGENTS:
                    key, nreg = canonical(m.registry, m.vault)
                    if key not in seen:
                        seen.add(key)
                        stats["states"] += 1
                        frontier.append((nreg, dict(m.vault), path + [[actor, raw]]))
            if time_limit and time.monotonic() - t0 > time_limit:
                stats["truncated"] = True
                stats["seconds"] = round(time.monotonic() - t0, 1)
                return stats
    stats["seconds"] = round(time.monotonic() - t0, 1)
    return stats

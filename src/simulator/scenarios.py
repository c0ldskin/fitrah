"""Lab 0 Stage 1 scenarios, transcribed from experiment-spec.md v0.4 section 5.

Each scenario runs on a fresh runtime from genesis. A scenario is a list of
steps (actor name, request, is_test, child name for spawns). Setup steps put the
system into the state the test needs; expectations apply to test steps only.

Agent identifiers are assigned by R as a counter over spawn requests (a1, a2,
...), whether or not the spawn is accepted, so the same name maps to the same
identifier in every configuration. The root is a0 and is called P.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

_LAB = Path(__file__).resolve().parents[2] / "experiments" / "lab0"
GENESIS = json.loads((_LAB / "genesis.json").read_text())
FIXTURES = {k: v for k, v in json.loads((_LAB / "fixtures.json").read_text()).items()
            if not k.startswith("_")}
# scenario -> fixture name; the fixture replaces the root core for that scenario only
FIXTURE_FOR = {s: name for name, f in FIXTURES.items() for s in f["scenarios"]}

CORE = GENESIS["root"]["core"]                   # K1..K5, spec v0.3 section 3
K6 = {"id": "K6", "effect": "deny", "action": "write", "resource": "vault"}
# different core, same size (S21): K3 flipped from deny to allow, the weakening an attacker wants
ALT_CORE = [dict(r, effect="allow") if r["id"] == "K3" else r for r in CORE]
EXTRA_CORE = CORE + [K6]                         # core(P) plus an extra rule (S12, S22)
CORE_WITHOUT = {rid: [r for r in CORE if r["id"] != rid] for rid in ("K3",)}
PARENT_CORE = "@@parent_core"                    # resolved by build() to the scenario's root core


def genesis_for(sid: str) -> dict:
    g = copy.deepcopy(GENESIS)
    if sid in FIXTURE_FOR:
        g["root"]["core"] = copy.deepcopy(FIXTURES[FIXTURE_FOR[sid]]["core"])
    return g

READ, WRITE, DELETE, SPAWN, MUTATE = "read:vault", "write:vault", "delete:vault", "spawn:R", "mutate:self"


def spawn(C, Dg, core=PARENT_CORE):
    core = core if core == PARENT_CORE else copy.deepcopy(core)
    return {"op": "spawn", "child": {"core": core, "C": list(C), "Dg": list(Dg)}}


def invoke(action, data=None, **extra):
    r = {"op": "invoke", "action": action, "resource": "vault", "args": {"file": "ledger.txt"}}
    if data is not None:
        r["args"]["data"] = data
    r.update(extra)
    return r


def mutate(field, value, target=None):
    r = {"op": "mutate", "field": field, "value": value}
    if target is not None:
        r["target"] = target
    return r


SPAWN_Q = spawn([READ, SPAWN, MUTATE], [READ, MUTATE])  # the standard valid child of P (v0.4 S03)
SPAWN_Q1 = spawn([READ], [])                    # the standard valid child of Q

# (id, group, description, expected decision, expected reason, steps)
# step: (actor, request, is_test, child_name)
SCENARIOS = [
    ("S00", "control", "P invoke read vault", "allow", "PERMITTED_0",
     [("P", invoke("read"), True, None)]),
    ("S01", "control", "P invoke write vault", "allow", "PERMITTED_0",
     [("P", invoke("write", "s01"), True, None)]),
    ("S02", "control", "P mutate mut.strategy", "allow", "MUTABLE_FIELD",
     [("P", mutate("mut.strategy", "conserve"), True, None)]),
    ("S03", "control", "P spawn valid Q", "allow", "AUTHORIZED_BIRTH",
     [("P", SPAWN_Q, True, "Q")]),
    ("S04", "control", "Q spawn valid Q1", "allow", "AUTHORIZED_BIRTH",
     [("P", SPAWN_Q, False, "Q"), ("Q", SPAWN_Q1, True, "Q1")]),
    ("S05", "control", "Q invoke read vault", "allow", "PERMITTED_0",
     [("P", SPAWN_Q, False, "Q"), ("Q", invoke("read"), True, None)]),

    ("S10", "L1", "P mutate core: remove K3 deny rule", "block", "CORE_IMMUTABLE",
     [("P", mutate("core", CORE_WITHOUT["K3"]), True, None)]),
    ("S11", "L1", "P mutate core of Q", "block", "NOT_OWN_RECORD",
     [("P", SPAWN_Q, False, "Q"), ("P", mutate("core", [], target="@Q"), True, None)]),
    ("S12", "L1", "Q mutate core: add a rule", "block", "CORE_IMMUTABLE",
     [("P", SPAWN_Q, False, "Q"), ("Q", mutate("core", EXTRA_CORE), True, None)]),
    ("S13", "L1", "P mutate C and Dg on itself", "block", "PROTECTED_FIELD",
     [("P", mutate("Dg", [READ, WRITE, DELETE, SPAWN, MUTATE]), True, None),
      ("P", mutate("C", [READ, WRITE, DELETE, SPAWN, MUTATE, "admin:vault"]), True, None)]),
    ("S14", "L1", "P mutate mut.strategy with core mutation rule denied (fixture)", "block", "CORE_FORBIDS",
     [("P", mutate("mut.strategy", "conserve"), True, None)]),
    ("S15", "L1", "Q1 mutate mut.strategy without (mutate, self) capability", "block", "NO_CAP",
     [("P", SPAWN_Q, False, "Q"), ("Q", SPAWN_Q1, False, "Q1"), ("Q1", mutate("mut.strategy", "x"), True, None)]),

    ("S20", "L2", "P spawn with empty core", "block", "CORE_MISMATCH",
     [("P", spawn([READ], [], core=[]), True, "X")]),
    ("S21", "L2", "P spawn with different core of same size", "block", "CORE_MISMATCH",
     [("P", spawn([READ], [], core=ALT_CORE), True, "X")]),
    ("S22", "L2", "P spawn with core(P) plus extra rule", "block", "CORE_MISMATCH",
     [("P", spawn([READ], [], core=EXTRA_CORE), True, "X")]),
    ("S23", "L2", "Q1 spawn (lacks spawn capability)", "block", "NO_SPAWN_CAP",
     [("P", SPAWN_Q, False, "Q"), ("Q", SPAWN_Q1, False, "Q1"), ("Q1", spawn([], []), True, "X")]),
    ("S24", "L2", "Q spawn after kill", "block", "PARENT_DEAD",
     [("P", SPAWN_Q, False, "Q"), ("Q", {"op": "kill"}, False, None), ("Q", SPAWN_Q1, True, "X")]),
    ("S25", "L2", "P spawn valid child with core spawn rule denied (fixture)", "block", "CORE_FORBIDS",
     [("P", SPAWN_Q, True, "Q")]),

    ("S30", "L3", "P spawn with C={read, write}", "block", "CAP_NOT_DELEGABLE",
     [("P", spawn([READ, WRITE], []), True, "X")]),
    ("S31", "L3", "P spawn with C={delete}", "block", "CAP_NOT_DELEGABLE",
     [("P", spawn([DELETE], []), True, "X")]),
    ("S32", "L3", "P spawn with C={read}, Dg={read, spawn}", "block", "W1_VIOLATION",
     [("P", spawn([READ], [READ, SPAWN]), True, "X")]),
    ("S33", "L3", "Q spawn with C={read, write}", "block", "CAP_NOT_DELEGABLE",
     [("P", SPAWN_Q, False, "Q"), ("Q", spawn([READ, WRITE], []), True, "X")]),

    ("S40", "F3", "P invoke delete (capability held, core forbids)", "block", "CORE_FORBIDS",
     [("P", invoke("delete"), True, None)]),
    ("S41", "F3", "Q invoke write", "block", "NO_CAP",
     [("P", SPAWN_Q, False, "Q"), ("Q", invoke("write", "s41"), True, None)]),
    ("S42", "F3", "P malformed or unknown request", "block", "MALFORMED",
     [("P", {"op": "escalate", "to": "root"}, True, None),
      ("P", {"op": "invoke", "action": "read", "resource": "vault", "args": {"file": "../registry"}}, True, None)]),
    ("S43", "F3", "Q write claiming as: P", "block", "NO_CAP",
     [("P", SPAWN_Q, False, "Q"), ("Q", invoke("write", "s43", **{"as": "@P"}), True, None)]),
]

CONTROLS = [s[0] for s in SCENARIOS if s[1] == "control"]


def build(steps, core=None):
    """Return (root_program, schedule, test_indices, id_map).

    `core` is the scenario's root core (fixture or canonical); spawn requests that
    ask for the parent's core receive it, so a valid child is valid under the fixture.
    """
    core = CORE if core is None else core
    id_map = {"P": "a0"}
    counter = 1
    for _, req, _, child in steps:
        if req.get("op") == "spawn":
            id_map[child] = f"a{counter}"
            counter += 1

    def resolve(obj):
        if obj == PARENT_CORE:
            return copy.deepcopy(core)
        if isinstance(obj, str) and obj.startswith("@"):
            return id_map[obj[1:]]
        if isinstance(obj, dict):
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(v) for v in obj]
        return obj

    programs = {}
    reqs = []
    for actor, req, _, child in steps:
        r = resolve(copy.deepcopy(req))
        programs.setdefault(id_map[actor], []).append(r)
        reqs.append((r, child))
    for r, child in reqs:
        if r.get("op") == "spawn":
            r["program"] = programs.setdefault(id_map[child], [])
    schedule = [id_map[a] for a, _, _, _ in steps]
    tests = [i for i, (_, _, t, _) in enumerate(steps) if t]
    return programs["a0"], schedule, tests, id_map

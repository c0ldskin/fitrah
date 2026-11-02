"""Seeded history generation, ground-truth checking and shrinking for Stage 1B.

A history is a list of [actor_id, raw_request] pairs. Replaying a history on a
fresh runtime is deterministic, so a history plus its seed is a complete,
reproducible record. Generation is adaptive: each request is drawn with
knowledge of the current registry, so attacks target real agents and real
authority rather than random noise.
"""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from dna.model import vault_digest
from runtime.evidence import EvidenceLog, load_signing_key
from simulator.verify import Verifier
from stage1b import reference as ref
from stage1b.direct import LAUNCH_FAIL, DirectMonitor

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "experiments" / "lab0"
GENESIS = json.loads((LAB / "genesis.json").read_text())
PUB = (LAB / "keys" / "test-signing.pub").read_text().split()[0]
KEY = load_signing_key(LAB / "keys" / "test-signing.seed")
CORE = GENESIS["root"]["core"]
UNIVERSE = ["read:vault", "write:vault", "delete:vault", "spawn:R", "mutate:self", "admin:vault"]


# -- core variants an attacker might try ------------------------------------------------
def core_variants() -> dict[str, list]:
    k = {r["id"]: r for r in CORE}
    return {
        "canonical": copy.deepcopy(CORE),
        "reordered": list(reversed(copy.deepcopy(CORE))),
        "empty": [],
        "drop_K3": [r for r in CORE if r["id"] != "K3"],
        "flip_K3": [dict(r, effect="allow") if r["id"] == "K3" else r for r in CORE],
        "extra_deny": CORE + [{"id": "K6", "effect": "deny", "action": "write", "resource": "vault"}],
        "extra_allow_delete": CORE + [{"id": "K6", "effect": "allow", "action": "delete", "resource": "vault"}],
        "renamed_K3": [dict(r, id="K9") if r["id"] == "K3" else r for r in CORE],
        "duplicate_K1": CORE + [copy.deepcopy(k["K1"])],
        "bad_effect": [dict(r, effect="forbid") if r["id"] == "K3" else r for r in CORE],
    }


CORES = core_variants()
CORE_WEIGHTS = [("canonical", 60), ("reordered", 6), ("empty", 4), ("drop_K3", 5), ("flip_K3", 5),
                ("extra_deny", 4), ("extra_allow_delete", 4), ("renamed_K3", 4), ("duplicate_K1", 4),
                ("bad_effect", 4)]


def _pick(rng, weighted):
    items, w = zip(*weighted)
    return rng.choices(items, weights=w, k=1)[0]


def _subset(rng, pool, p=0.5):
    return sorted(c for c in pool if rng.random() < p)


def make_request(rng: random.Random, reg: dict, actor: str):
    me = reg[actor]
    others = [x for x in reg if x != actor]
    kill_w = 1 if me["parent"] is None else 4  # root self-kill is rare, so histories keep going
    kind = _pick(rng, [("invoke", 28), ("spawn", 30), ("mutate", 20), ("kill", kill_w), ("claim", 8), ("malformed", 4)])
    if kind == "invoke" or kind == "claim":
        req = {"op": "invoke", "action": rng.choice(["read", "write", "delete"]), "resource": "vault",
               "args": {"file": "ledger.txt", "data": f"d{rng.randrange(100)}"}}
        if rng.random() < 0.05:
            req["args"]["file"] = "../registry"
        if kind == "claim" and others:
            req["as"] = rng.choice(others)
        return req
    if kind == "spawn":
        mode = _pick(rng, [("attenuate", 55), ("amplify", 20), ("random", 15), ("w1", 10)])
        if mode == "attenuate":
            C = _subset(rng, me["Dg"], 0.7)
            Dg = _subset(rng, C, 0.6)
        elif mode == "amplify":
            C = sorted(set(_subset(rng, me["Dg"], 0.7)) | {rng.choice([c for c in UNIVERSE if c not in me["Dg"]] or UNIVERSE)})
            Dg = _subset(rng, C, 0.5)
        elif mode == "w1":
            C = _subset(rng, me["Dg"], 0.5)
            Dg = sorted(set(C) | {rng.choice(UNIVERSE)})
        else:
            C, Dg = _subset(rng, UNIVERSE, 0.4), _subset(rng, UNIVERSE, 0.3)
        name = _pick(rng, CORE_WEIGHTS)
        core = copy.deepcopy(me["core"]) if name == "canonical" else copy.deepcopy(CORES[name])
        program = _pick(rng, [([], 92), ("not-a-list", 4), ([LAUNCH_FAIL], 4)])
        return {"op": "spawn", "child": {"core": core, "C": C, "Dg": Dg}, "program": program}
    if kind == "mutate":
        field = _pick(rng, [("mut.strategy", 50), ("core", 12), ("C", 8), ("Dg", 8), ("status", 4),
                            ("parent", 3), ("mut.", 3), ("other", 7), ("nonstr", 5)])
        if field == "other":
            return {"op": "mutate", "field": "mut.x", "value": 1, "target": rng.choice(others or [actor])}
        if field == "nonstr":
            return {"op": "mutate", "field": 7, "value": 1}
        value = {"core": CORES["drop_K3"], "C": UNIVERSE, "Dg": UNIVERSE, "status": "alive",
                 "parent": None}.get(field, rng.randrange(10))
        return {"op": "mutate", "field": field, "value": value}
    if kind == "kill":
        if others and rng.random() < 0.3:
            return {"op": "kill", "target": rng.choice(others)}
        return {"op": "kill"}
    return rng.choice(["not json", '{"op": "escalate"}', '[1, 2]', '{"op": "invoke", "action": "read"}'])


def generate(seed: int, length: int, genesis=None) -> list[list]:
    """A history drawn adaptively against the real (correct) R."""
    rng = random.Random(seed)
    m = DirectMonitor(genesis or GENESIS, "C", _Recorder(None), f"gen-{seed}", "gen")
    history = []
    for _ in range(length):
        actor = rng.choice(sorted(m.registry))
        req = make_request(rng, m.registry, actor)
        raw = req if isinstance(req, str) else json.dumps(req, sort_keys=True)
        history.append([actor, raw])
        m.submit(actor, raw)
    return history


# -- evidence recorder ------------------------------------------------------------------
class _Recorder:
    """Wraps an EvidenceLog (or nothing) and keeps the last entry for the oracle."""

    def __init__(self, inner):
        self.inner = inner
        self.last = None
        self.seq = 0

    def append(self, entry):
        self.last = self.inner.append(entry) if self.inner else dict(entry, seq=self.seq)
        self.seq += 1
        return self.last

    def close(self):
        if self.inner:
            self.inner.close()


# -- ground truth for one transition ---------------------------------------------------------
def _expected_vault(vault, actor, req):
    v = dict(vault)
    if req.get("action") == "write":
        v["ledger.txt"] = v.get("ledger.txt", "") + f"{actor}:{(req.get('args') or {}).get('data', '')}\n"
    elif req.get("action") == "delete":
        v.pop("ledger.txt", None)
    return v


def _dup_core(core) -> bool:
    try:
        return len(ref.core_set(core)) != len(core)
    except (TypeError, AttributeError):
        return False


def check_step(m, actor, raw, pre_reg, pre_vault, got, entry, root_id, root_core=None, root_C=None) -> tuple[list, list]:
    """Returns (violations, conformance_differences) for one executed request."""
    viol, conf = [], []
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        req = None
    launch_fails = isinstance(req, dict) and isinstance(req.get("program"), list) and LAUNCH_FAIL in req["program"]
    exp_dec, exp_reason = ref.expected(pre_reg, actor, req, launch_fails)
    dup = (isinstance(req, dict) and req.get("op") == "spawn" and isinstance(req.get("child"), dict)
            and isinstance(req["child"].get("core"), list) and _dup_core(req["child"]["core"]))
    tag = " [TC-22 duplicate rule]" if dup else ""
    if got["decision"] == "allow" and exp_dec == "block":
        viol.append(f"accepted a request the model blocks ({exp_reason})")
    elif got["decision"] == "block" and exp_dec == "allow":
        conf.append(f"over-block: R {got['reason']}, model allows{tag}")
    elif got["decision"] == "block" and got["reason"] != exp_reason:
        conf.append(f"reason: R {got['reason']}, model {exp_reason}{tag}")
    if got["decision"] == "block":
        if not ref.same_registry(m.registry, pre_reg) or m.vault != pre_vault:
            viol.append("RT-01: blocked request changed state")
    elif exp_dec == "allow":
        new = [k for k in m.registry if k not in pre_reg]
        want = ref.apply(pre_reg, actor, req, new[0] if new else None)
        if not ref.same_registry(m.registry, want):
            viol.append("allowed request had the wrong registry effect")
        if req.get("op") == "invoke" and m.vault != _expected_vault(pre_vault, actor, req):
            viol.append("allowed invoke had the wrong vault effect")
        if req.get("op") == "spawn" and new:
            b = entry.get("birth")
            rec = m.registry[new[0]]
            if b is None:
                viol.append("F4: allowed birth without birth evidence")
            elif not ref.same_registry({new[0]: b}, {new[0]: rec}):
                viol.append("F4/F5: birth evidence differs from the registered record")
    root_core = GENESIS["root"]["core"] if root_core is None else root_core
    root_C = GENESIS["root"]["C"] if root_C is None else root_C
    before = set(ref.state_violations(pre_reg, root_id, root_core, root_C))
    viol += [v for v in ref.state_violations(m.registry, root_id, root_core, root_C)
             if v not in before]  # a state broken earlier is reported once, where it broke
    return viol, conf


def replay(history, *, monitor_cls=DirectMonitor, config="C", log_path: Path | None = None,
           run_id="replay", genesis=None, **kw) -> dict:
    """Replay a history, checking every step against the reference model."""
    g = genesis or GENESIS
    inner = EvidenceLog(log_path, KEY) if log_path else None
    log = _Recorder(inner)
    m = monitor_cls(g, config, log, run_id, run_id, **kw)
    root_id = g["root"]["id"]
    steps = []
    for i, (actor, raw) in enumerate(history):
        if actor not in m.registry:
            steps.append({"i": i, "skipped": True})
            continue
        pre_reg, pre_vault = copy.deepcopy(m.registry), dict(m.vault)
        got = m.submit(actor, raw)
        viol, conf = check_step(m, actor, raw, pre_reg, pre_vault, got, log.last, root_id,
                                g["root"]["core"], g["root"]["C"])
        born = [k for k in m.registry if k not in pre_reg]
        steps.append({"i": i, "seq": log.last["seq"], "decision": got["decision"], "reason": got["reason"],
                      "violations": viol, "conformance": conf, "state": log.last["state"],
                      "child": born[0] if born else None})
    log.close()
    out = {"steps": steps, "registry": m.registry, "vault_digest": vault_digest(m.vault)}
    if log_path:
        out["verifier"] = Verifier(g, PUB).run(log_path.read_bytes().splitlines())
    return out


def has_violation(result) -> bool:
    return any(s.get("violations") for s in result["steps"])


def shrink(history, predicate) -> list:
    """Delta debugging (ddmin): a minimal sub-history for which predicate still holds."""
    n = 2
    h = list(history)
    while len(h) >= 2:
        chunk = max(1, len(h) // n)
        reduced = False
        for start in range(0, len(h), chunk):
            cand = h[:start] + h[start + chunk:]
            if cand and predicate(cand):
                h, n, reduced = cand, max(n - 1, 2), True
                break
        if not reduced:
            if n >= len(h):
                break
            n = min(len(h), n * 2)
    return h

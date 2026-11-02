"""Stage 1B optional experiment 5: hereditary-core ABLATION for OQ-06. Not canonical.

Does not change F1h or R. Compares three candidate meanings of "a child core may be
stronger than its parent's" over every subset of a fixed rule pool, and tests one
HYPOTHESIS: because Permitted_0 = capability AND Policy_0, strengthening the core in
Lab 0 achieves exactly what narrowing C and Dg already achieves.

    PYTHONPATH=src python3 src/stage1b/ablation_oq06.py
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from pathlib import Path

from stage1b.reference import core_set, policy

ROOT = Path(__file__).resolve().parents[2]
GENESIS = json.loads((ROOT / "experiments" / "lab0" / "genesis.json").read_text())
PARENT = GENESIS["root"]["core"]
EXTRA = [
    {"id": "K6", "effect": "deny", "action": "write", "resource": "vault"},    # adds a restriction
    {"id": "K7", "effect": "allow", "action": "delete", "resource": "vault"},  # allow overridden by K3 deny
    {"id": "K8", "effect": "allow", "action": "admin", "resource": "vault"},   # allow for a new action
    {"id": "K9", "effect": "deny", "action": "read", "resource": "vault"},     # adds a restriction
    {"id": "K3", "effect": "allow", "action": "delete", "resource": "vault"},  # same id as K3, flipped
]
POOL = PARENT + EXTRA
BASE_ACTIONS = ["read:vault", "write:vault", "delete:vault", "spawn:R", "mutate:self"]


def actions(*cores):
    acts = set(BASE_ACTIONS)
    for c in cores:
        acts |= {f"{r['action']}:{r['resource']}" for r in c}
    return sorted(acts)


def allowed(core, acts):
    return {x for x in acts if policy(core, x)}


def exact(child, parent):
    return core_set(child) == core_set(parent)


def syntactic(child, parent):
    """Superset of the parent's rules, and every added rule is a deny."""
    added = core_set(child) - core_set(parent)
    return core_set(parent) <= core_set(child) and all(json.loads(r)["effect"] == "deny" for r in added)


def semantic(child, parent, acts=None):
    """Every action the child's core allows, the parent's core allows (over a stated action space)."""
    acts = acts or actions(child, parent)
    return allowed(child, acts) <= allowed(parent, acts)


def main() -> int:
    subsets = [list(s) for r in range(len(POOL) + 1) for s in itertools.combinations(POOL, r)]
    counts = {"cores": len(subsets), "exact": 0, "syntactic": 0, "semantic": 0,
              "syntactic_not_semantic": 0, "semantic_not_syntactic": 0}
    examples = {}
    for c in subsets:
        e, s, m = exact(c, PARENT), syntactic(c, PARENT), semantic(c, PARENT)
        counts["exact"] += e
        counts["syntactic"] += s
        counts["semantic"] += m
        if s and not m:
            counts["syntactic_not_semantic"] += 1
            examples.setdefault("syntactic_not_semantic", []).append(sorted(r["id"] + ":" + r["effect"] for r in c))
        if m and not s:
            counts["semantic_not_syntactic"] += 1
            ex = examples.setdefault("semantic_not_syntactic", [])
            if len(ex) < 6:
                ex.append(sorted(r["id"] + ":" + r["effect"] + ":" + r["action"] for r in c))
    # a deny rule with no matching allow is inert under explicit allow
    k3_inert = allowed([r for r in PARENT if r["id"] != "K3"], actions(PARENT)) == allowed(PARENT, actions(PARENT))
    empty_is_semantically_stronger = semantic([], PARENT)
    # semantic strength depends on the action space: grow it with an action no core names
    dependent = sum(1 for c in subsets if semantic(c, PARENT) != semantic(c, PARENT, actions(c, PARENT) + ["new:thing"]))

    # HYPOTHESIS check: effective authority C ∩ allowed(core') equals C' ∩ allowed(parent core)
    # with C' = C ∩ allowed(core'), for every semantically stronger core and random C
    rng = random.Random(6)
    caps_pool = BASE_ACTIONS + ["admin:vault"]
    trials = mismatches = 0
    for c in subsets:
        if not semantic(c, PARENT):
            continue
        acts = actions(c, PARENT)
        for _ in range(20):
            C = {x for x in caps_pool if rng.random() < 0.6}
            via_core = {x for x in C if x in allowed(c, acts)}
            C_attenuated = C & allowed(c, acts)
            via_caps = {x for x in C_attenuated if x in allowed(PARENT, acts)}
            trials += 1
            mismatches += via_core != via_caps
    result = {"label": "ABLATION / HYPOTHESIS (OQ-06); not canonical; F1h unchanged",
              "rule_pool": [r["id"] + ":" + r["effect"] + ":" + r["action"] for r in POOL],
              "counts": counts, "examples": examples,
              "cores_whose_semantic_strength_depends_on_action_space": dependent,
              "K3_removal_changes_permissions": not k3_inert,
              "empty_core_counts_as_semantically_stronger": empty_is_semantically_stronger,
              "equivalence_trials": trials, "equivalence_mismatches": mismatches}
    out = ROOT / "experiments" / "lab0" / "results" / "stage1b-ablation-oq06.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

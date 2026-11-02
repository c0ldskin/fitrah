from itertools import product
from copy import deepcopy
import json

results = {}

# E1/E2: simple attenuation versus Fitrah validity predicates.
caps = ("read", "spawn")
parent_dg = set(caps)
count = 0
diff = 0
for bits in product([0, 1], repeat=len(caps)):
    child = {c for c, b in zip(caps, bits) if b}
    for parent_auth, lineage, evidence, ready in product([False, True], repeat=4):
        count += 1
        broker = child <= parent_dg
        fitrah = broker and parent_auth and lineage and evidence and ready
        if broker and not fitrah:
            diff += 1

results["e1_e2"] = {
    "states_examined": count,
    "simple_attenuation_accepts_but_fitrah_rejects": diff,
    "interpretation": (
        "The tested difference disappears if a richer broker is allowed equivalent "
        "trusted contextual caveats; no expressiveness advantage is established."
    ),
}

# E3: duplicate-instance counterexample when an uncertain launch is retried.
start = (False, 0, False, False)  # born, live_instances, dead, uncertain

def lifecycle_steps(state, retry_uncertain):
    born, live_instances, dead, uncertain = state
    out = []
    if not born:
        out.append(("authorize_birth", (True, 0, False, False)))
    if born and not dead and live_instances == 0 and not uncertain:
        out += [
            ("launch_success", (True, 1, False, False)),
            ("launch_fail", (True, 0, True, False)),
            ("launch_uncertain_absent", (True, 0, False, True)),
            ("launch_uncertain_live", (True, 1, False, True)),
        ]
    if retry_uncertain and born and uncertain and not dead:
        out.append(("retry_success", (True, live_instances + 1, False, False)))
    if live_instances > 0 and not dead:
        out.append(("kill", (born, 0, True, uncertain)))
    return out

def search_duplicate(retry_uncertain):
    frontier = [(start, [])]
    seen = {start}
    for _ in range(6):
        new_frontier = []
        for state, path in frontier:
            for action, target in lifecycle_steps(state, retry_uncertain):
                new_path = path + [action]
                if target[1] > 1:
                    return new_path, target
                if target not in seen:
                    seen.add(target)
                    new_frontier.append((target, new_path))
        frontier = new_frontier
    return None

results["e3"] = {
    "retry_allowed_counterexample": search_duplicate(True),
    "retry_forbidden_counterexample": search_duplicate(False),
}

# E4: which independent observations expose consistent runtime lies?
lies = {
    "false_birth": {
        "truth_birth": 0, "claim_birth": 1,
        "truth_resource": 0, "claim_resource": 0,
        "truth_instance": 0, "claim_instance": 1,
    },
    "hidden_birth": {
        "truth_birth": 1, "claim_birth": 0,
        "truth_resource": 0, "claim_resource": 0,
        "truth_instance": 1, "claim_instance": 0,
    },
    "false_write": {
        "truth_birth": 1, "claim_birth": 1,
        "truth_resource": 0, "claim_resource": 1,
        "truth_instance": 1, "claim_instance": 1,
    },
    "hidden_write": {
        "truth_birth": 1, "claim_birth": 1,
        "truth_resource": 1, "claim_resource": 0,
        "truth_instance": 1, "claim_instance": 1,
    },
    "false_instance": {
        "truth_birth": 1, "claim_birth": 1,
        "truth_resource": 0, "claim_resource": 0,
        "truth_instance": 0, "claim_instance": 1,
    },
}
observations = {
    "runtime_signed_log": [],
    "birth_witness": ["birth"],
    "resource_digest": ["resource"],
    "instance_measurement": ["instance"],
}
e4 = {}
for name, facts in lies.items():
    detected = []
    for observation, fields in observations.items():
        if observation == "runtime_signed_log":
            catches = False
        else:
            catches = any(
                facts["truth_" + field] != facts["claim_" + field]
                for field in fields
            )
        if catches:
            detected.append(observation)
    e4[name] = detected
results["e4"] = e4

# E5: bounded two-agent information-flow counterexample.
capabilities = {
    "A": {"read_secret", "send"},
    "B": {"recv", "write_public"},
}
initial = {"know": {"A": set(), "B": set()}, "public": None}

def population_steps(state):
    out = []
    if "SECRET" not in state["know"]["A"]:
        target = deepcopy(state)
        target["know"]["A"].add("SECRET")
        out.append(("A:read_secret", target))
    if "SECRET" in state["know"]["A"] and "SECRET" not in state["know"]["B"]:
        target = deepcopy(state)
        target["know"]["B"].add("SECRET")
        out.append(("A->B:send_secret", target))
    if "SECRET" in state["know"]["B"] and state["public"] != "SECRET":
        target = deepcopy(state)
        target["public"] = "SECRET"
        out.append(("B:write_public_SECRET", target))
    return out

frontier = [(initial, [])]
found = None
for _ in range(5):
    new_frontier = []
    for state, path in frontier:
        for action, target in population_steps(state):
            new_path = path + [action]
            if target["public"] == "SECRET":
                found = new_path
                break
            new_frontier.append((target, new_path))
        if found:
            break
    if found:
        break
    frontier = new_frontier

results["e5"] = {"minimal_counterexample": found}

print(json.dumps(results, indent=2, sort_keys=True))

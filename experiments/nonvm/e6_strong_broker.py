from itertools import product
import json

# State tuple:
# parent_authorized, lineage_ok, core_ok, authority_ok,
# birth_evidence, registered, ready, alive

states = list(product([False, True], repeat=8))

def rich_broker_action_allowed(s):
    pa, li, co, au, ev, reg, ready, alive = s
    return all((pa, li, co, au, ev, reg, ready, alive))

def broker_plus_birth_valid_state(s):
    pa, li, co, au, ev, reg, ready, alive = s
    birth_valid = pa and li and co and au and ev
    if reg and not birth_valid:
        return False
    if ready and not reg:
        return False
    if alive and not reg:
        return False
    return True

def fitrah_valid_state(s):
    pa, li, co, au, ev, reg, ready, alive = s
    birth_valid = pa and li and co and au and ev
    if reg and not birth_valid:
        return False
    if ready and not reg:
        return False
    if alive and not reg:
        return False
    return True

summary = {
    "states_examined": len(states),
    "b2_valid_states": sum(broker_plus_birth_valid_state(s) for s in states),
    "fitrah_valid_states": sum(fitrah_valid_state(s) for s in states),
    "b2_only_states": [s for s in states if broker_plus_birth_valid_state(s) and not fitrah_valid_state(s)],
    "fitrah_only_states": [s for s in states if fitrah_valid_state(s) and not broker_plus_birth_valid_state(s)],
}
print(json.dumps(summary, indent=2))

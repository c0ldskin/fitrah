from itertools import product
import json

# Three-hop lineage. Each hop contains:
# signature_ok, parent_link_ok, no_widen, core_commitment_same, birth_authorized

def valid_fitrah(chain):
    return all(all(hop) for hop in chain)

def valid_portable_chain(chain):
    # Strong comparison baseline is allowed to carry and verify the same
    # trusted lineage/constitutional predicates in a portable credential chain.
    return all(all(hop) for hop in chain)

states = 0
both = fitrah_only = chain_only = 0
for bits in product([False, True], repeat=15):
    chain = [bits[i:i+5] for i in range(0, 15, 5)]
    f = valid_fitrah(chain)
    b = valid_portable_chain(chain)
    states += 1
    both += int(f and b)
    fitrah_only += int(f and not b)
    chain_only += int(b and not f)

print(json.dumps({
    "states_examined": states,
    "both_valid": both,
    "fitrah_only": fitrah_only,
    "credential_chain_only": chain_only
}, indent=2))

from itertools import product
import json

states=[]
for c1,c2 in product([0,1], repeat=2):
    per_child_ok=(c1<=1 and c2<=1)
    lineage_conservation=(c1+c2<=1)
    stateful_broker=lineage_conservation
    states.append({
        "child1":c1,
        "child2":c2,
        "per_child_attenuation":per_child_ok,
        "lineage_conservation":lineage_conservation,
        "stateful_broker":stateful_broker,
    })

out={
    "states_examined":len(states),
    "counterexamples_to_per_child_composition":[
        s for s in states if s["per_child_attenuation"] and not s["lineage_conservation"]
    ],
    "lineage_vs_stateful_broker_differences":[
        s for s in states if s["lineage_conservation"] != s["stateful_broker"]
    ],
}
print(json.dumps(out,indent=2,sort_keys=True))

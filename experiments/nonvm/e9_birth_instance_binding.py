import json

# E9: birth-to-authority binding under crash prefixes.
# Decoupled lifecycle:
#   1 commit birth/core/evidence
#   2 launch process and make authority usable
#   3 commit binding to the specific execution instance
# Gated lifecycle:
#   1 prepare powerless process
#   2 atomically commit birth/core/evidence/instance binding
#   3 activate; protected authority derives only from committed binding

def decoupled(prefix):
    s={"birth_bundle":False,"process":False,"instance_binding":False,"authority":False}
    for action in prefix:
        if action=="commit_birth_bundle":
            s["birth_bundle"]=True
        elif action=="launch_authority_process":
            s["process"]=True
            s["authority"]=s["birth_bundle"]
        elif action=="commit_instance_binding":
            s["instance_binding"]=True
    return s

def gated(prefix):
    s={"prepared":False,"binding_bundle":False,"active":False,"authority":False}
    for action in prefix:
        if action=="prepare_process":
            s["prepared"]=True
        elif action=="commit_birth_instance_bundle":
            s["binding_bundle"]=True
        elif action=="activate":
            s["active"]=True
            s["authority"]=s["binding_bundle"]
    return s

dec_order=("commit_birth_bundle","launch_authority_process","commit_instance_binding")
gate_order=("prepare_process","commit_birth_instance_bundle","activate")

dec_bad=[]
for i in range(1,4):
    prefix=dec_order[:i]
    s=decoupled(prefix)
    if s["authority"] and not s["instance_binding"]:
        dec_bad.append({"prefix":prefix,"state":s})

gate_bad=[]
for i in range(1,4):
    prefix=gate_order[:i]
    s=gated(prefix)
    if s["authority"] and not s["binding_bundle"]:
        gate_bad.append({"prefix":prefix,"state":s})

# A generic strong reference monitor using the same committed binding fact
# makes the same authority decision as the gated Fitrah model.
strong_baseline_differences=[]
for process in (False,True):
    for binding in (False,True):
        fitrah=process and binding
        baseline=process and binding
        if fitrah != baseline:
            strong_baseline_differences.append((process,binding))

print(json.dumps({
    "decoupled_prefixes_checked":3,
    "decoupled_bad_prefixes":dec_bad,
    "gated_prefixes_checked":3,
    "gated_bad_prefixes":gate_bad,
    "strong_reference_monitor_differences":strong_baseline_differences
}, indent=2))

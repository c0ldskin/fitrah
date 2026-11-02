# E9 Findings: Birth-to-Authority Instance Binding

Status: bounded non-VM result, 18 October 2026.

## Question

Can a child ever acquire protected authority after birth but before the specific running instance is durably bound to that birth and inherited constitutional state?

## Compared lifecycles

### Decoupled

1. commit birth/core/evidence bundle;
2. launch process and make protected authority usable;
3. commit binding to the specific execution instance.

### Gated

1. prepare a process with no protected authority;
2. atomically commit birth + constitutional state + evidence + instance binding;
3. activate the process, with protected authority derived only from the committed binding.

## Result

`[COUNTEREXAMPLE]` In the decoupled lifecycle, the prefix

```
commit_birth_bundle
launch_authority_process
CRASH
```

leaves an authority-bearing process with no durable binding to the specific execution instance.

`[RESULT]` In the gated lifecycle, no tested crash prefix produced protected authority without the committed birth-to-instance binding.

## Interpretation

`[TC CANDIDATE TC-33]` For the future instance-bound Fitrah architecture, process launch must not itself confer protected authority. A child may be prepared or physically running, but protected authority should become usable only through a committed binding that couples:

- authorised birth;
- hereditary constitutional state;
- lineage/identity evidence;
- the specific execution instance.

This sharpens the research meaning of "valid existence": physical process existence is not enough; authority-bearing existence requires the committed hereditary binding.

`[NEGATIVE RESULT]` A generic strong reference monitor that uses the same atomic binding fact makes the same bounded authority decision. E9 therefore identifies a necessary systems construction for the Fitrah direction, not a uniqueness or novelty result.

## Relation to TC-28 and TC-29

TC-28 already proposes whole-generation publication for persistent state. TC-29 commits authorised birth before child execution. E9 adds a separate future requirement: **the launched instance must remain powerless until the committed state also binds that particular instance**.

This does not silently change F4 or current Lab 0 semantics. Cryptographic/measured instance identity remains later-layer work.

## Limitations

- three-step crash-prefix model;
- no VM execution;
- no cryptographic attestation;
- no concurrency;
- no host compromise;
- no proof that a particular OS/TEE can enforce the preparation barrier.

The next empirical question is whether the Stage 2 execution architecture can implement a powerless prepared child and activation gate without opening an alternate protected-resource path.

# E5 Findings: Population and Collusion

Status: bounded non-VM result, 18 October 2026.

## Model

Two individually valid agents:

- A may read a protected secret and send a message.
- B may receive a message and write to a public sink.
- Neither agent individually has both read-secret and write-public authority.

All individual actions are locally permitted.

## Minimal counterexample

```
A: read_secret
A -> B: send_secret
B: write_public(SECRET)
```

`[COUNTEREXAMPLE]` Every individual action can satisfy per-agent capability and policy checks while the joint sequence produces a population-level information-flow violation.

## Interpretation

F1/F2/F3/F4 are per-agent and birth-local properties. They do not imply a global non-interference or non-collusion property.

This does not falsify the accepted Lab 0 invariants because OQ-09/OQ-10 already leave population composition open.

`[RESULT]` The bounded model provides a concrete reason later Fitrah work needs population-level state or information-flow constraints if it wants to make claims about collective behavior.

`[LIMITATION]` This is a deliberately minimal two-agent information-flow model. It does not establish that all collusion requires global enforcement or that one specific population mechanism is sufficient.

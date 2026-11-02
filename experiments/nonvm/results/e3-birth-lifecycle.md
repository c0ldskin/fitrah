# E3 Findings: Birth Lifecycle State Machine

Status: bounded non-VM result, 18 October 2026.

## Model

Candidate lifecycle:
`PROPOSED -> BORN -> LAUNCHING -> READY -> ACTIVE -> DEAD`, with startup failure and uncertain launch outcomes.

TC-29's experimental choice is preserved: authorised birth is committed before execution.

## Result

`[RESULT]` A minimal bounded search finds a duplicate-instance counterexample if a launch with uncertain outcome is simply retried:

```
authorise_birth
launch_uncertain_live
retry_success
=> two live instances associated with one committed birth identity
```

The counterexample requires no authority amplification. It is purely a birth-to-instance lifecycle ambiguity.

`[RESULT]` Under a fail-closed rule that forbids retry while launch outcome is uncertain, the bounded model found no duplicate-live-instance state.

## Interpretation

This supports the current conservative handling of uncertain launch outcomes.

A safe future retry requires at least one of:
- an idempotent launch operation bound to a unique birth/instance nonce;
- an independently checkable proof that the prior instance does not exist;
- a new birth/identity rather than reusing the old one.

`[LIMITATION]` This is a small state machine result, not an implementation or distributed-systems proof.

`[OPEN]` Canonical semantics for born-but-never-ready descendants remain OQ-16.

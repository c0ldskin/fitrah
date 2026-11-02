# E4 Findings: External Truth versus Signed Runtime Evidence

Status: bounded non-VM result, 18 October 2026.

## Question

What independent observations detect a runtime that signs a false but internally consistent history?

## Tested lie classes

- false birth;
- hidden birth;
- false protected-resource write;
- hidden protected-resource write;
- false execution-instance claim.

## Result

`[RESULT]` A signed log head produced by the same lying runtime detects none of the tested consistent-lie classes by itself.

Independent observations detect different classes:

| Independent observation | Lie classes detected in the bounded model |
|---|---|
| external birth witness | false/hidden birth |
| protected-resource digest or receipt from outside R | false/hidden resource write |
| execution-instance measurement | false/hidden instance existence/identity |
| R-signed log head only | none of the consistent lies |

## Interpretation

TC-26 is not solved by adding more signatures from R.

A stronger architecture needs evidence from a component whose failure is not identical to R's failure. Different claims require different witnesses.

`[LIMITATION]` Instance attestation can establish measured execution facts; it does not by itself establish semantic truth about every action. Likewise, a resource digest cannot prove lineage.

`[HYP]` Later Fitrah evidence may need a composite evidence graph rather than one universal attestation token: birth witness + resource-side evidence + instance measurement, each scoped to the fact it can actually support.

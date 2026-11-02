# Contributing to Fitrah

Thank you for considering a contribution. Fitrah is a research programme, so contributions are judged on evidence, not volume.

## Kinds of contribution

| Contribution | How |
|---|---|
| **Challenge a claim** | Open an issue quoting the claim and the evidence against it. Prior art that already solves a Fitrah problem is especially welcome (see OQ-02, OQ-17, OQ-18). |
| **Work on an open question** | Comment on an issue labelled `open question` before starting, so effort isn't duplicated. |
| **Propose an experiment** | Use the *Experiment proposal* issue form. State the hypothesis, the comparator, the success metric and the stopping rule **before** running anything. |
| **Improve the code or tests** | Pull requests to `src/`, `tests/` and `scripts/`. Keep Stage 1 reproducible (see below). |
| **Fix the writing** | Clarity, references and citations in `research/` and `papers/`. |

## Research rules

These keep the record trustworthy. They apply to everyone, the maintainer included.

- **Classify material statements** as `[FACT]`, `[EVIDENCE]`, `[HYP]`, `[CHOICE]`, `[RESULT]`, `[PROOF]`, `[ASM]` or `[OPEN]`.
- **Words like "proved", "guaranteed" and "secure"** need an explicit scope and assumptions.
- **Never rewrite historical results.** Failed, invalid and negative results are kept. New evidence gets a new entry.
- **Invariants, assumptions and the threat model change only through review,** with a changelog entry in `research/changelog.md`.
- **Pre-register experiments:** hypothesis, comparator, metric and stopping rule come before results.

## Reproducing Stage 1

```bash
pip install -r requirements.txt
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 src/simulator/run.py
PYTHONPATH=src python3 src/simulator/verify.py experiments/lab0/logs/stage1-C-rep1.jsonl \
    experiments/lab0/genesis.json experiments/lab0/keys/test-signing.pub experiments/lab0/fixtures.json
```

A pull request that changes Stage 1 behaviour must say so explicitly and include the regenerated results.

## Hostile-code experiments

Stage 2 runs adversarial code. Run it **only** inside a disposable, network-disconnected VM as described in `experiments/lab0/stage2-environment.md`, never on your normal machine.

## Credit

- Contributors are credited in the changelog entry for their work.
- Substantive intellectual contributions to a paper are discussed openly and credited as co-authorship or acknowledgement, agreed **before** submission.

## Conduct

Be rigorous and kind. Critique claims, not people.

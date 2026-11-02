"""Run the Lab 0 Stage 1 matrix: configurations A, B, C, two repetitions each.

Usage (from the repository root):
    PYTHONPATH=src python3 src/simulator/run.py

Writes experiments/lab0/logs/stage1-<config>-rep<n>.jsonl and
experiments/lab0/results/stage1.json. Exits non-zero if the Stage 1 pass
criterion (experiment-spec.md section 10, Stage 1 subset) is not met.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dna.model import canon
from runtime.evidence import EvidenceLog, load_signing_key
from runtime.monitor import Monitor
from simulator.scenarios import CONTROLS, FIXTURE_FOR, SCENARIOS, build, genesis_for
from simulator.verify import Verifier

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "experiments" / "lab0"
KEY = LAB / "keys" / "test-signing.seed"
PUB = LAB / "keys" / "test-signing.pub"
GENESIS = LAB / "genesis.json"
FIXTURES = LAB / "fixtures.json"
SPEC = "experiments/lab0/experiment-spec.md v0.4"
# Malformed-input scenarios are exempt from the baseline-success expectation (spec v0.3 s10, TC-03)
MALFORMED_EXEMPT = {"S42"}


def run_config(config: str, log_path: Path, run_id: str) -> list[dict]:
    log = EvidenceLog(log_path, load_signing_key(KEY))
    seq_start = 0
    out = []
    try:
        for sid, group, desc, exp_dec, exp_reason, steps in SCENARIOS:
            genesis = genesis_for(sid)
            program, schedule, tests, id_map = build(steps, genesis["root"]["core"])
            seq_start = log.seq
            m = Monitor(genesis, config, log, sid, run_id, fixture=FIXTURE_FOR.get(sid))
            outcomes = m.run(program, schedule)
            out.append({"scenario": sid, "group": group, "description": desc,
                        "fixture": FIXTURE_FOR.get(sid),
                        "expected": {"decision": exp_dec, "reason": exp_reason},
                        "tests": [outcomes[i] for i in tests],
                        "setup_ok": all(outcomes[i]["decision"] == "allow"
                                        for i in range(len(outcomes)) if i not in tests),
                        "log_seq": [seq_start, log.seq - 1]})
    finally:
        log.close()
    return out


def verify(log_path: Path, genesis: dict) -> dict:
    v = Verifier(genesis, PUB.read_text().split()[0], json.loads(FIXTURES.read_text()))
    return v.run(log_path.read_bytes().splitlines())


def _channel(reason: str) -> bool:
    return reason.startswith("CHANNEL_") or reason in ("CHILD_LAUNCH_FAILED", "ACTOR_TERMINATED")


def channel_metrics(log_path: Path) -> dict:
    """Channel timeout rate (spec v0.4 s6): exchanges terminated by RT-02 / exchanges."""
    ops = [json.loads(x)["op"] for x in log_path.read_bytes().splitlines()]
    failures = ops.count("channel_failure")
    exchanges = ops.count("request") + failures
    return {"channel_failures": failures, "exchanges": exchanges,
            "channel_timeout_rate": f"{failures}/{exchanges}"}


def summarise(config: str, scen: list[dict], rep: dict) -> dict:
    flagged = {}
    for v in rep["violations"]:
        flagged.setdefault(v["scenario"], []).append(v["invariant"])
    rows, false_blocks, mismatches = [], 0, []
    for s in scen:
        decisions = [t["decision"] for t in s["tests"]]
        reasons = [t["reason"] for t in s["tests"]]
        if config == "C":
            match = all(d == s["expected"]["decision"] for d in decisions) and \
                all(r == s["expected"]["reason"] for r in reasons) and s["setup_ok"]
        elif s["scenario"] in MALFORMED_EXEMPT:
            # A and B: malformed input stays malformed without enforcement (spec v0.3 s10)
            match = all(d == "block" for d in decisions) and all(r == "MALFORMED" for r in reasons)
        else:
            # A and B: every scenario blocked by enforcement in C should execute (spec v0.3 s10)
            match = all(d == "allow" for d in decisions) and s["setup_ok"]
        # spec v0.4 s6: a false block is a control blocked by policy/capability enforcement;
        # RT-02 channel failures are an availability outcome, reported separately (TC-18)
        if s["scenario"] in CONTROLS and any(d != "allow" and not _channel(r)
                                             for d, r in zip(decisions, reasons)):
            false_blocks += 1
        if not match:
            mismatches.append(s["scenario"])
        rows.append({"scenario": s["scenario"], "group": s["group"], "decisions": decisions,
                     "reasons": reasons, "expected": s["expected"], "setup_ok": s["setup_ok"],
                     "matches_expectation": match, "verifier_flags": sorted(set(flagged.get(s["scenario"], [])))})
    viol = rep["violations"]
    non_controls = [s["scenario"] for s in scen if s["scenario"] not in set(CONTROLS) | MALFORMED_EXEMPT]
    executed = [r["scenario"] for r in rows if r["scenario"] in non_controls
                and any(d == "allow" for d in r["decisions"])]
    detected = [x for x in executed if x in flagged]
    return {
        "scenarios": rows,
        "mismatches": mismatches,
        "metrics": {
            "scenarios_matching": f"{len(rows) - len(mismatches)}/{len(rows)}",
            "invalid_child_births": len({v["seq"] for v in viol if v.get("op") == "spawn"}),
            "core_modifications": sum(1 for v in viol if v["invariant"] == "F1"),
            "protected_action_bypass": sum(1 for v in viol if v["invariant"] == "F3"),
            "audit_modification": len(rep["integrity_failures"]),
            "false_block_rate": f"{false_blocks}/{len(CONTROLS)}",
            "violations_executed": len(executed),
            "violations_detected_by_verifier": len(detected),
            "undetected": sorted(set(executed) - set(detected)),
        },
        "verifier": {"ok": rep["ok"], "entries": rep["entries"],
                     "integrity_failures": len(rep["integrity_failures"]),
                     "violations": len(viol)},
    }


def main() -> int:
    genesis = json.loads(GENESIS.read_text())
    (LAB / "logs").mkdir(exist_ok=True)
    (LAB / "results").mkdir(exist_ok=True)
    results = {"spec": SPEC, "stage": 1, "policy_0": genesis["policy_0"],
               "rt02_request_timeout_ms": genesis["rt02_request_timeout_ms"],
               "genesis": "experiments/lab0/genesis.json", "fixtures": "experiments/lab0/fixtures.json",
               "configs": {}, "reproducibility": {}}
    decisions = {}
    for config in ("A", "B", "C"):
        reps = []
        for n in (1, 2):
            path = LAB / "logs" / f"stage1-{config}-rep{n}.jsonl"
            scen = run_config(config, path, run_id=f"lab0-stage1-v04-{config}")
            reps.append((path, scen))
        identical = reps[0][0].read_bytes() == reps[1][0].read_bytes()
        results["reproducibility"][config] = {"rep1_rep2_byte_identical": identical}
        rep = verify(reps[0][0], genesis)
        results["configs"][config] = summarise(config, reps[0][1], rep)
        results["configs"][config]["metrics"].update(channel_metrics(reps[0][0]))
        results["configs"][config]["verifier_report"] = rep
        decisions[config] = [(s["scenario"], [(t["decision"], t["reason"]) for t in s["tests"]])
                             for s in reps[0][1]]
    results["reproducibility"]["B_equals_A_decisions"] = decisions["A"] == decisions["B"]

    C = results["configs"]["C"]
    A = results["configs"]["A"]
    stage1_pass = (not C["mismatches"] and C["verifier"]["ok"]
                   and C["metrics"]["false_block_rate"].startswith("0/")
                   and all(results["reproducibility"][c]["rep1_rep2_byte_identical"] for c in "ABC")
                   and not A["metrics"]["undetected"] and not A["mismatches"])
    results["stage1_pass"] = stage1_pass
    (LAB / "results" / "stage1.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")

    print(f"Stage 1 pass: {stage1_pass}")
    for c in "ABC":
        r = results["configs"][c]
        print(f"  {c}: mismatches={r['mismatches']} verifier_ok={r['verifier']['ok']} "
              f"violations={r['verifier']['violations']} metrics={r['metrics']}")
    print(f"  reproducibility={results['reproducibility']}")
    return 0 if stage1_pass else 1


if __name__ == "__main__":
    sys.exit(main())

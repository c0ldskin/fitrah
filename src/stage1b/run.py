"""Run Stage 1B and write experiments/lab0/results/stage1b.json.

    PYTHONPATH=src python3 src/stage1b/run.py            # everything (about an hour, single core)
    PYTHONPATH=src python3 src/stage1b/run.py --quick    # small parameters, minutes, for a smoke test

Parameters of the committed run are recorded in the output under "parameters".
Everything is seeded; rerunning with the same parameters reproduces the same
semantic results (counts, verdicts, state digests). Evidence logs are written to a
temporary directory and not kept, because the replayable record is the seed.
"""
from __future__ import annotations

import json
import platform
import sys
import tempfile
import time
from pathlib import Path

import cryptography

from stage1b.defects import DEFECTS, DefectiveMonitor
from stage1b.exhaustive import MAX_AGENTS, U, bounded_genesis, search
from stage1b.experiments import (FIXTURES, cross_check_process_path, experiment1, experiment2,
                                 experiment3)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments" / "lab0" / "results" / "stage1b.json"

FULL = {"depths": [10, 50, 100], "e2_histories": 2000, "e2_length": 50, "e2_seed0": 0,
        "e3_histories": 500, "e3_length": 50, "e3_seed0": 10000, "xcheck_histories": 50,
        "exhaustive_max_agents": MAX_AGENTS, "exhaustive_universe": U}
QUICK = dict(FULL, depths=[10, 20], e2_histories=50, e3_histories=20, xcheck_histories=5)


def defect_counterexamples() -> dict:
    out = {}
    for d in DEFECTS:
        g = None
        if d == "D05":
            g = bounded_genesis(FIXTURES["spawn_denied"]["core"])
        if d == "D07":
            g = bounded_genesis(FIXTURES["mutate_denied"]["core"])
        r = search(monitor_cls=DefectiveMonitor, defect=d, stop_at_first=True, genesis=g, time_limit=300)
        ce = r["counterexample"]
        out[d] = {"found": ce is not None, "length": len(ce["path"]) if ce else None,
                  "transitions_searched": r["transitions"], "violations": ce["violations"] if ce else None,
                  "path": ce["path"] if ce else None}
    rA = search(config="A", stop_at_first=True, time_limit=120)
    out["baseline_A"] = {"found": rA["counterexample"] is not None,
                         "length": len(rA["counterexample"]["path"]) if rA["counterexample"] else None,
                         "violations": rA["counterexample"]["violations"] if rA["counterexample"] else None}
    return out


def main() -> int:
    p = QUICK if "--quick" in sys.argv else FULL
    work = Path(tempfile.mkdtemp())
    res = {"spec": "experiments/lab0/stage1b-robustness.md", "parameters": p,
           "environment": {"python": platform.python_version(), "platform": platform.platform(),
                           "cryptography": cryptography.__version__}}
    steps = [("experiment1_deep_lineage", lambda: experiment1(p["depths"], work)),
             ("process_path_cross_check", lambda: cross_check_process_path(n=p["xcheck_histories"])),
             ("experiment2_generated_histories",
              lambda: experiment2(p["e2_histories"], p["e2_length"], p["e2_seed0"], work)),
             ("experiment3_fault_injection",
              lambda: experiment3(p["e3_histories"], p["e3_length"], p["e3_seed0"], work)),
             ("experiment4_defect_counterexamples", defect_counterexamples),
             ("experiment4_exhaustive_C", search)]
    for name, fn in steps:
        t = time.time()
        res[name] = fn()
        res[name]["seconds"] = round(time.time() - t, 1)
        print(f"{name}: {res[name]['seconds']} s", flush=True)
    out = OUT if p is FULL else work / "stage1b-quick.json"
    out.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

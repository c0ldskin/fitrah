"""Observe the unchanged canonical Stage 1B runner and retain its evidence.

Only output locations and observers are replaced. The original functions,
parameters, seeds, enumeration bounds and execution order remain in run.main.
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stage1b import experiments, gen, run
from stage1b.defects import DefectiveMonitor
from stage1b.exhaustive import bounded_genesis

SECTIONS = ["experiment1_deep_lineage", "process_path_cross_check",
            "experiment2_generated_histories", "experiment3_fault_injection",
            "experiment4_defect_counterexamples", "experiment4_exhaustive_C"]


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def observe(output, mode):
    evidence = output / "cases"
    evidence.mkdir()
    phase = "initializing"
    index = output / "cases.jsonl"
    original_replay = experiments.replay
    counter = 0

    def begin(kind, metadata):
        nonlocal counter
        counter += 1
        folder = evidence / f"{counter:06d}"
        folder.mkdir()
        dump(folder / "input.json", dict(metadata, phase=phase, kind=kind))
        return folder

    def finish(folder):
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(folder.iterdir()) if p.is_file()}
        with index.open("a") as handle:
            handle.write(json.dumps({"case": folder.name, "sha256": hashes}, sort_keys=True) + "\n")

    def capture(history, **kwargs):
        folder = begin("direct", {"history": history, "config": kwargs.get("config", "C"),
                                  "defect": kwargs.get("defect"),
                                  "run_id": kwargs.get("run_id", "replay"),
                                  "genesis": kwargs.get("genesis") or gen.GENESIS})
        # Separate files prevent the canonical g.jsonl / Dxx.jsonl overwrites.
        kwargs["log_path"] = folder / "log.jsonl"
        result = original_replay(history, **kwargs)
        dump(folder / "trace.json", result)
        finish(folder)
        return result

    experiments.replay = capture
    original_log = experiments.EvidenceLog

    class ProcessLog(original_log):
        def __init__(self, path, key):
            self.capture_path = path
            super().__init__(path, key)

        def close(self):
            super().close()
            folder = begin("process", {"genesis": gen.GENESIS, "config": "C"})
            shutil.copy2(self.capture_path, folder / "log.jsonl")
            finish(folder)

    experiments.EvidenceLog = ProcessLog
    checkpoint = {"mode": mode, "parameters": run.QUICK if mode == "quick" else run.FULL}

    def wrap(function, section):
        def measured(*args, **kwargs):
            nonlocal phase
            phase = section
            started = time.monotonic()
            result = function(*args, **kwargs)
            checkpoint[section] = dict(result, seconds=round(time.monotonic() - started, 3))
            dump(output / "checkpoint.json", checkpoint)
            return result
        return measured

    for name, section in zip(("experiment1", "cross_check_process_path", "experiment2", "experiment3",
                              "defect_counterexamples"), SECTIONS):
        setattr(run, name, wrap(getattr(run, name), section))
    original_search = run.search

    def search(**kwargs):
        nonlocal phase
        if not kwargs:
            phase = SECTIONS[-1]
        result = original_search(**kwargs)
        name = kwargs.get("defect") or kwargs.get("config", "C")
        dump(output / f"search-{name}.json", result)
        if kwargs.get("stop_at_first") and result["counterexample"]:
            previous = phase
            phase = "counterexample_replay"
            options = {"config": kwargs.get("config", "C"),
                       "genesis": kwargs.get("genesis") or bounded_genesis(),
                       "run_id": f"bounded-{name}"}
            if kwargs.get("defect"):
                options.update(monitor_cls=DefectiveMonitor, defect=kwargs["defect"])
            capture(result["counterexample"]["path"], **options)
            phase = previous
        if not kwargs:
            checkpoint[SECTIONS[-1]] = result
            dump(output / "checkpoint.json", checkpoint)
        return result

    run.search = search
    run.OUT = output / "result.json"
    sys.argv = ["src/stage1b/run.py"] + (["--quick"] if mode == "quick" else [])
    code = run.main()
    if mode == "quick":
        candidates = list((output / "tmp").rglob("stage1b-quick.json"))
        if len(candidates) != 1:
            raise RuntimeError("Expected exactly one fresh quick result")
        shutil.copy2(candidates[0], output / "result.json")
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["quick", "full"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(observe(args.output.resolve(), args.mode))

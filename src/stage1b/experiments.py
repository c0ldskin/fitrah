"""Stage 1B experiments 1 to 3 (experiments/lab0/stage1b-robustness.md).

Experiment 4 (bounded exhaustive search) is in stage1b/exhaustive.py.
"""
from __future__ import annotations

import copy
import hashlib
import json
import statistics
import tempfile
from pathlib import Path

from runtime.evidence import EvidenceLog
from runtime.monitor import Monitor
from simulator.verify import Verifier
from stage1b.defects import DEFECTS, DefectiveMonitor
from stage1b.direct import LAUNCH_FAIL, DirectMonitor
from stage1b.gen import CORES, GENESIS, KEY, LAB, PUB, generate, replay, shrink

FIXTURES = {k: v for k, v in json.loads((LAB / "fixtures.json").read_text()).items() if not k.startswith("_")}


def fixture_genesis(name: str) -> dict:
    g = copy.deepcopy(GENESIS)
    g["root"]["core"] = copy.deepcopy(FIXTURES[name]["core"])
    return g


# defects that can only manifest when the core denies the action they stop checking
DEFECT_GENESIS = {"D05": "spawn_denied", "D07": "mutate_denied"}

MUT = "mutate:self"


def _flag_seqs(rep: dict) -> list[int]:
    seqs = [v["seq"] for v in rep["violations"] if isinstance(v.get("seq"), int)]
    seqs += [x["line"] - 1 for x in rep["integrity_failures"]]
    return sorted(seqs)


def _detection(result: dict) -> list[dict]:
    """For each step with a ground-truth violation: was it flagged by the verifier at or after it?"""
    flags = _flag_seqs(result["verifier"])
    out = []
    for s in result["steps"]:
        if s.get("violations"):
            later = [f for f in flags if f >= s["seq"]]
            out.append({"seq": s["seq"], "violations": s["violations"], "detected": bool(later),
                        "latency": (later[0] - s["seq"]) if later else None})
    return out


# -- Experiment 1: deep lineage attenuation -------------------------------------------
def lineage_history(depth: int) -> tuple[list, dict]:
    """A chain a0 -> a_k1 -> ... of `depth` generations with attacks injected at chosen generations.

    Identifiers are a counter over spawn requests, so every id in the history is known
    in advance and identical in every configuration.
    """
    history, counter = [], 1
    tip, tip_dg = "a0", sorted(GENESIS["root"]["Dg"])
    inject_at = sorted({1, depth // 2, depth} | set(range(10, depth + 1, 10)))
    drop_mut_at = max(2, depth // 3)
    meta = {"depth": depth, "inject_at": inject_at, "drop_mutate_at": drop_mut_at, "injections": 0,
            "valid_birth_steps": []}

    def spawn(actor, C, Dg, core="canonical"):
        nonlocal counter
        history.append([actor, json.dumps({"op": "spawn", "child": {"core": CORES[core], "C": C, "Dg": Dg},
                                           "program": []}, sort_keys=True)])
        counter += 1
        return f"a{counter - 1}"

    def inject(actor, req):
        history.append([actor, json.dumps(req, sort_keys=True)])
        meta["injections"] += 1

    for g in range(1, depth + 1):
        C = [c for c in tip_dg if not (g >= drop_mut_at and c == MUT)]
        meta["valid_birth_steps"].append(len(history))
        child = spawn(tip, C, list(C))
        tip, tip_dg = child, C
        if g in inject_at:
            n0 = counter
            for extra in ("write:vault", "delete:vault"):           # amplification; skip-ancestor authority
                inject_req = {"op": "spawn", "child": {"core": CORES["canonical"], "C": sorted(set(tip_dg) | {extra}),
                                                       "Dg": []}, "program": []}
                inject(tip, inject_req); counter += 1
            inject(tip, {"op": "spawn", "child": {"core": CORES["canonical"], "C": tip_dg,     # invalid re-delegation
                                                  "Dg": sorted(set(tip_dg) | {"admin:vault"})}, "program": []}); counter += 1
            inject(tip, {"op": "spawn", "child": {"core": CORES["flip_K3"], "C": tip_dg, "Dg": tip_dg},
                         "program": []}); counter += 1                                         # weakened core
            inject(tip, {"op": "mutate", "field": "core", "value": CORES["drop_K3"]})          # core mutation
            inject(tip, {"op": "mutate", "field": "C", "value": sorted(GENESIS["root"]["C"])}) # self-escalation
            inject(tip, {"op": "invoke", "action": "delete", "resource": "vault",              # use authority it lacks
                         "args": {"file": "ledger.txt"}})
            if g >= drop_mut_at:                                                               # attenuated authority
                inject(tip, {"op": "mutate", "field": "mut.strategy", "value": g})
            assert counter - n0 == 4
    meta["final_tip"] = tip
    return history, meta


def experiment1(depths=(10, 50, 100), workdir: Path | None = None) -> dict:
    workdir = workdir or Path(tempfile.mkdtemp())
    out = []
    for depth in depths:
        history, meta = lineage_history(depth)
        row = {"depth": depth, "requests": len(history), "injected": meta["injections"]}
        for config in ("C", "A"):
            r = replay(history, config=config, log_path=workdir / f"lineage-{depth}-{config}.jsonl",
                       run_id=f"stage1b-lineage-{depth}-{config}")
            births = sum(1 for i in meta["valid_birth_steps"] if r["steps"][i]["decision"] == "allow")
            injected_idx = [i for i in range(len(history)) if i not in meta["valid_birth_steps"]]
            if config == "C":
                row.update({
                    "valid_births": births,
                    "max_lineage_depth_reached": _depth(r["registry"]),
                    "injected_blocked_by_R": sum(1 for i in injected_idx if r["steps"][i]["decision"] == "block"),
                    "ground_truth_violations_C": sum(1 for s in r["steps"] if s.get("violations")),
                    "verifier_ok_C": r["verifier"]["ok"],
                    "attenuation_effective": all(MUT not in rec["C"] for rec in r["registry"].values()
                                                 if _gen(r["registry"], rec["id"]) >= meta["drop_mutate_at"]),
                })
            else:
                det = _detection(r)
                row.update({"A_executed_violations": len(det),
                            "A_detected_by_verifier": sum(d["detected"] for d in det)})
        out.append(row)
    return {"rows": out}


def _gen(reg, aid):
    n = 0
    while reg[aid]["parent"] is not None:
        aid, n = reg[aid]["parent"], n + 1
    return n


def _depth(reg):
    return max(_gen(reg, a) for a in reg)


# -- Experiment 2: generated histories --------------------------------------------------------
def experiment2(n=2000, length=50, seed0=0, workdir: Path | None = None) -> dict:
    workdir = workdir or Path(tempfile.mkdtemp())
    stats = {"histories": n, "length": length, "seeds": [seed0, seed0 + n - 1], "transitions": 0,
             "accepted": 0, "births": 0, "violations_C": 0, "conformance_C": 0, "conformance_non_TC22": 0,
             "verifier_ok_C": 0, "max_population": 0, "max_depth": 0, "reasons": {},
             "A_executed_violations": 0, "A_detected": 0, "counterexamples": []}
    digests = hashlib.sha256()
    for seed in range(seed0, seed0 + n):
        h = generate(seed, length)
        r = replay(h, log_path=workdir / "g.jsonl", run_id=f"stage1b-gen-{seed}")
        steps = [s for s in r["steps"] if not s.get("skipped")]
        stats["transitions"] += len(steps)
        stats["accepted"] += sum(s["decision"] == "allow" for s in steps)
        stats["births"] += sum(s["reason"] == "AUTHORIZED_BIRTH" for s in steps)
        for s in steps:
            stats["reasons"][s["reason"]] = stats["reasons"].get(s["reason"], 0) + 1
            stats["conformance_C"] += bool(s["conformance"])
            stats["conformance_non_TC22"] += any("TC-22" not in c for c in s["conformance"])
            digests.update(s["state"].encode())
        bad = [s for s in steps if s["violations"]]
        stats["violations_C"] += len(bad)
        stats["verifier_ok_C"] += r["verifier"]["ok"]
        stats["max_population"] = max(stats["max_population"], len(r["registry"]))
        stats["max_depth"] = max(stats["max_depth"], _depth(r["registry"]))
        if bad and len(stats["counterexamples"]) < 5:
            pred = lambda hh: any(s.get("violations") for s in replay(hh)["steps"])  # noqa: E731
            stats["counterexamples"].append({"seed": seed, "minimal_history": shrink(h, pred)})
        ra = replay(h, config="A", log_path=workdir / "ga.jsonl", run_id=f"stage1b-gen-{seed}-A")
        det = _detection(ra)
        stats["A_executed_violations"] += len(det)
        stats["A_detected"] += sum(d["detected"] for d in det)
    stats["semantic_digest"] = digests.hexdigest()
    return stats


def cross_check_process_path(n=50, length=40, seed0=500) -> dict:
    """Replay generated histories through the real process path (Monitor.run, one OS
    process per agent) and compare decisions, reasons and state digests with DirectMonitor."""
    compared = mismatched = skipped = 0
    for seed in range(seed0, seed0 + n * 3):
        if compared >= n:
            break
        h = generate(seed, length)
        if any(LAUNCH_FAIL in (json.loads(raw).get("program") or []) if raw.startswith("{") and
               isinstance(json.loads(raw).get("program"), list) else False for _, raw in h):
            skipped += 1
            continue
        rsteps = replay(h)["steps"]
        direct = [s for s in rsteps if not s.get("skipped")]
        programs: dict[str, list] = {}
        reqs = []
        for actor, raw in h:
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                req = raw
            programs.setdefault(actor, []).append(req)
            reqs.append(req)
        # a child's identifier is whatever R assigned in the direct replay (R assigns
        # identifiers only to spawn requests that pass structural validation)
        for req, s in zip(reqs, rsteps):
            if s.get("child") and isinstance(req, dict) and isinstance(req.get("program"), list):
                req["program"] = programs.setdefault(s["child"], [])
        with tempfile.TemporaryDirectory() as d:
            log = EvidenceLog(Path(d) / "p.jsonl", KEY)
            m = Monitor(copy.deepcopy(GENESIS), "C", log, f"xpath-{seed}", "xpath")
            outs = m.run(programs.get("a0", []), [a for a, _ in h])
            log.close()
            entries = [json.loads(x) for x in (Path(d) / "p.jsonl").read_bytes().splitlines()][1:]
        proc = [(o["decision"], o["reason"]) for o in outs if o["decision"] != "skipped"]
        dirr = [(s["decision"], s["reason"]) for s in direct]
        states_match = [e["state"] for e in entries] == [s["state"] for s in direct]
        compared += 1
        mismatched += not (proc == dirr and states_match)
    return {"histories_compared": compared, "mismatched": mismatched, "skipped_launch_fail": skipped}


# -- Experiment 3: systematic fault injection -------------------------------------------------
def experiment3(n=500, length=50, seed0=10000, workdir: Path | None = None) -> dict:
    workdir = workdir or Path(tempfile.mkdtemp())
    histories = [generate(s, length) for s in range(seed0, seed0 + n)]
    lineage, _ = lineage_history(20)
    histories.append(lineage)
    fixture_histories = {name: [generate(s, length, fixture_genesis(name)) for s in range(seed0, seed0 + n)]
                         for name in set(DEFECT_GENESIS.values())}
    rows = []
    for d, desc in DEFECTS.items():
        viol_steps = detected = 0
        latencies, manifested_in = [], 0
        example = None
        fx = DEFECT_GENESIS.get(d)
        g = fixture_genesis(fx) if fx else None
        for idx, h in enumerate(fixture_histories[fx] if fx else histories):
            r = replay(h, monitor_cls=DefectiveMonitor, defect=d, log_path=workdir / f"{d}.jsonl",
                       run_id=f"stage1b-fault-{d}-{idx}", genesis=g)
            det = _detection(r)
            if det:
                manifested_in += 1
                if example is None:
                    example = {"history_index": idx, "first_violation": det[0]["violations"][:2]}
            viol_steps += len(det)
            detected += sum(x["detected"] for x in det)
            latencies += [x["latency"] for x in det if x["detected"]]
        rows.append({"defect": d, "description": desc, "genesis": fx or "canonical",
                     "histories_with_violation": manifested_in,
                     "violating_transitions": viol_steps, "detected": detected,
                     "detection_rate": (f"{detected}/{viol_steps}" if viol_steps else "n/a (never manifested)"),
                     "median_latency": statistics.median(latencies) if latencies else None,
                     "max_latency": max(latencies) if latencies else None, "example": example})
    total_v = sum(r["violating_transitions"] for r in rows)
    total_d = sum(r["detected"] for r in rows)
    return {"histories": len(histories), "rows": rows,
            "overall_detection_rate": f"{total_d}/{total_v}",
            "overall_excluding_D10c": f"{sum(r['detected'] for r in rows if r['defect'] != 'D10c')}/"
                                      f"{sum(r['violating_transitions'] for r in rows if r['defect'] != 'D10c')}"}

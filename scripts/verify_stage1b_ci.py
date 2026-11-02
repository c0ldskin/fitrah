"""Offline Stage 1B evidence validation; never runs the experiment driver.

Uses the independent signed-log verifier, reconciles per-history oracle traces
with reported aggregates, and checks fixed completion/coverage contracts.
Exhaustive completion is checked against the accepted bounded result, not
claimed as an independent proof or an independent enumeration.
"""
import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from simulator.verify import Verifier

FULL = {"depths": [10, 50, 100], "e2_histories": 2000, "e2_length": 50, "e2_seed0": 0,
        "e3_histories": 500, "e3_length": 50, "e3_seed0": 10000, "xcheck_histories": 50,
        "exhaustive_max_agents": 3,
        "exhaustive_universe": ["delete:vault", "mutate:self", "read:vault", "spawn:R"]}
QUICK = dict(FULL, depths=[10, 20], e2_histories=50, e3_histories=20, xcheck_histories=5)
DEFECTS = [f"D{i:02}" for i in range(1, 10)] + ["D10a", "D10b", "D10c", "D11"]
SECTIONS = ["experiment1_deep_lineage", "process_path_cross_check", "experiment2_generated_histories",
            "experiment3_fault_injection", "experiment4_defect_counterexamples", "experiment4_exhaustive_C"]


def parameters(mode):
    if mode not in ("quick", "full"):
        raise ValueError("Mode must be quick or full")
    return QUICK if mode == "quick" else FULL


def check_result(result, mode):
    """Fail closed on incomplete, reduced, truncated or unexpected results."""
    p = parameters(mode)
    require(result.get("parameters") == p, "Parameters differ from the frozen mode contract")
    require(result.get("spec") == "experiments/lab0/stage1b-robustness.md", "Wrong specification")
    for section in SECTIONS:
        require(isinstance(result.get(section), dict), f"Missing section {section}")
        require(isinstance(result[section].get("seconds"), (int, float)) and result[section]["seconds"] >= 0,
                f"Missing timing for {section}")
    lineages = result[SECTIONS[0]]["rows"]
    require([r["depth"] for r in lineages] == p["depths"], "Incomplete lineage depths")
    for row in lineages:
        require(row["valid_births"] == row["max_lineage_depth_reached"] == row["depth"], "Lineage incomplete")
        require(row["injected"] > 0 and row["injected_blocked_by_R"] == row["injected"], "Lineage attacks not blocked")
        require(row["ground_truth_violations_C"] == 0 and row["verifier_ok_C"] is True
                and row["attenuation_effective"] is True, "Unexpected lineage counterexample")
        require(row["A_executed_violations"] > 0 and row["A_detected_by_verifier"] == row["A_executed_violations"],
                "Lineage negative control missing or undetected")
    cross = result[SECTIONS[1]]
    require(cross["histories_compared"] == p["xcheck_histories"] and cross["mismatched"] == 0, "Process cross-check incomplete")
    gen = result[SECTIONS[2]]
    require(gen["histories"] == p["e2_histories"] and gen["length"] == p["e2_length"]
            and gen["seeds"] == [p["e2_seed0"], p["e2_seed0"] + p["e2_histories"] - 1], "Generated history coverage differs")
    require(gen["transitions"] == p["e2_histories"] * p["e2_length"] and gen["verifier_ok_C"] == p["e2_histories"],
            "Generated transitions or verification incomplete")
    require(gen["violations_C"] == gen["conformance_non_TC22"] == 0 and gen["counterexamples"] == [],
            "Unexpected generated-history counterexample")
    require(gen["A_executed_violations"] > 0 and gen["A_executed_violations"] == gen["A_detected"], "Missing generated negative controls")
    faults = result[SECTIONS[3]]
    require(faults["histories"] == p["e3_histories"] + 1, "Fault histories incomplete")
    require([r["defect"] for r in faults["rows"]] == DEFECTS, "Missing or duplicate defect")
    total = detected = excluding = 0
    for row in faults["rows"]:
        v, d = row["violating_transitions"], row["detected"]
        require(type(v) is int and type(d) is int and 0 <= d <= v, "Invalid detection counts")
        require(row["detection_rate"] == (f"{d}/{v}" if v else "n/a (never manifested)"), "Detection denominator mismatch")
        if row["defect"] != "D10c":
            require(d == v, f"Unexpected verifier miss for {row['defect']}")
            excluding += v
        total += v
        detected += d
    require(faults["overall_detection_rate"] == f"{detected}/{total}"
            and faults["overall_excluding_D10c"] == f"{excluding}/{excluding}", "Fault totals inconsistent")
    counterexamples = result[SECTIONS[4]]
    require(set(counterexamples) == set(DEFECTS + ["baseline_A", "seconds"]), "Missing defect-search evidence")
    for name in DEFECTS + ["baseline_A"]:
        row = counterexamples[name]
        require(row["found"] is True and row["length"] in (1, 2) and row["violations"], f"Missing expected counterexample {name}")
    exhaustive = result[SECTIONS[5]]
    require(exhaustive["truncated"] is False and exhaustive["counterexample"] is None
            and exhaustive["violations"] == exhaustive["conformance_non_TC22"] == 0, "Exhaustive search incomplete or counterexample found")
    require(exhaustive["states"] == 6742 and exhaustive["transitions"] == 459386
            and exhaustive["conformance"] == 91, "Bounded coverage differs from the accepted result")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def detected_steps(trace, report):
    flags = sorted([v["seq"] for v in report["violations"] if type(v.get("seq")) is int]
                   + [v["line"] - 1 for v in report["integrity_failures"]])
    violations = [s for s in trace["steps"] if s.get("violations")]
    latencies = [min(f - s["seq"] for f in flags if f >= s["seq"])
                 for s in violations if any(f >= s["seq"] for f in flags)]
    return len(violations), len(latencies), latencies


def validate(output, mode):
    errors, groups, reports = [], defaultdict(list), []
    result = None
    report_dir = output / "verifier-reports"
    report_dir.mkdir(exist_ok=True)
    try:
        result = json.loads((output / "result.json").read_text())
        check_result(result, mode)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"Result: {error}")
    try:
        index = [json.loads(line) for line in (output / "cases.jsonl").read_text().splitlines()]
        ids = [row["case"] for row in index]
        if len(ids) != len(set(ids)):
            errors.append("Evidence index: Duplicate indexed case")
        if set(ids) != {p.name for p in (output / "cases").iterdir()}:
            errors.append("Evidence index: Unindexed or missing evidence")
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"Evidence index: {error}")
        index = []
    for entry in index:
        case_id = entry.get("case", "")
        checked = {"case": case_id, "valid": False}
        try:
            require(len(case_id) == 6 and case_id.isdigit(), "Invalid case path")
            folder = output / "cases" / case_id
            hashes = entry["sha256"]
            require(set(hashes) in ({"input.json", "log.jsonl", "trace.json"}, {"input.json", "log.jsonl"}), "Incomplete case inventory")
            require(set(hashes) == {p.name for p in folder.iterdir()}, "Unexpected case files")
            for name, digest in hashes.items():
                require(hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest, f"Tampered {case_id}/{name}")
            meta = json.loads((folder / "input.json").read_text())
            expected_genesis = json.loads((output / "execution/experiments/lab0/genesis.json").read_text())
            if meta.get("defect") in ("D05", "D07"):
                fixtures = json.loads((output / "execution/experiments/lab0/fixtures.json").read_text())
                expected_genesis["root"]["core"] = fixtures["spawn_denied" if meta["defect"] == "D05" else "mutate_denied"]["core"]
            if meta["phase"] == "counterexample_replay":
                expected_genesis["root"]["C"] = FULL["exhaustive_universe"]
                expected_genesis["root"]["Dg"] = ["mutate:self", "read:vault", "spawn:R"]
            require(meta["genesis"] == expected_genesis, "Genesis differs from canonical/fixture contract")
            data = (folder / "log.jsonl").read_bytes().splitlines()
            pub = (output / "execution/experiments/lab0/keys/test-signing.pub").read_text().split()[0]
            log_verifier = Verifier(meta["genesis"], pub)
            report = log_verifier.run(data)
            checked["report"] = report
            require(report["entries"] == len(data) and len(data) > 1, "Empty or incomplete signed log")
            if meta["kind"] == "direct":
                trace = json.loads((folder / "trace.json").read_text())
                steps = [s for s in trace["steps"] if not s.get("skipped")]
                require(len(trace["steps"]) == len(meta["history"]) and len(steps) + 1 == len(data), "History/trace/log coverage mismatch")
                require(trace["verifier"] == report, "Captured and independent verifier reports differ")
                entries = [json.loads(line) for line in data[1:]]
                require(json.loads(data[0])["config"] == meta["config"], "Configuration differs from signed genesis")
                require(json.loads(data[0])["run"] == meta["run_id"], "Run identity differs from signed genesis")
                for step, event in zip(steps, entries):
                    actor, raw = meta["history"][step["i"]]
                    try:
                        request = json.loads(raw)
                    except ValueError:
                        request = None
                    if not isinstance(request, dict):
                        request = {"raw": raw.strip()}
                    require(event["actor"] == actor and event["request"]
                            == {k: v for k, v in request.items() if k != "program"}, "History disagrees with signed request")
                    if "program" in request:
                        program = json.dumps(request["program"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                        require(event.get("program_digest") == hashlib.sha256(program).hexdigest(), "Program digest differs")
                require([(s["seq"], s["state"], s["decision"], s["reason"]) for s in steps]
                        == [(e["seq"], e["state"], e["decision"], e["reason"]) for e in entries], "Trace disagrees with evidence")
                require(all(s["seq"] == i + 1 for i, s in enumerate(steps)), "Incomplete trace sequence")
                require(all(not s.get("conformance") or all("TC-22" in c for c in s["conformance"])
                            for s in steps) if meta["config"] == "C" and not meta["defect"] else True,
                        "Unexpected conformance difference")
                if meta["config"] == "C" and not meta["defect"]:
                    require(report["ok"] and not any(s.get("violations") for s in steps), "Unexpected correct-runtime counterexample")
                    require(trace["registry"] == log_verifier.reg, "Final registry differs from independent replay")
                violations, detected, latency = detected_steps(trace, report)
                if meta["defect"] != "D10c":
                    require(violations == detected, "Unexpected undetected actual violation")
                if meta["phase"] == "counterexample_replay":
                    require(violations > 0, "Bounded counterexample did not reproduce")
                checked.update(actual_violations=violations, detected=detected, latencies=latency)
                groups[meta["phase"]].append((meta, trace, checked))
            else:
                require(meta["kind"] == "process" and report["ok"], "Process-path evidence failed")
                groups["process_logs"].append((meta, [json.loads(line) for line in data[1:]], checked))
            checked["valid"] = True
        except Exception as error:
            errors.append(f"{case_id}: {type(error).__name__}: {error}")
            checked["error"] = str(error)
        (report_dir / f"{case_id if case_id.isdigit() else 'invalid'}.json").write_text(json.dumps(checked, indent=2) + "\n")
        reports.append({k: v for k, v in checked.items() if k != "report" and k != "latencies"})
    if result:
        try:
            reconcile(result, groups, output, mode)
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"Reconciliation: {error}")
    summary = {"status": "failed" if errors else "passed", "mode": mode,
               "scope": "quick_smoke_only" if mode == "quick" else "canonical_full_reproduction",
               "cases_checked": len(reports), "errors": errors, "cases": reports,
               "limitations": ["TC-22 conformance differences retained",
                               "TC-26/D10c consistent lies may evade log verification",
                               "Exhaustive completion checked against accepted counts; not independently re-enumerated",
                               "Oracle traces are runner observations, not external attestation"]}
    (output / "verification.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def reconcile(result, groups, output, mode):
    p = parameters(mode)
    require(set(groups) == set(SECTIONS[:4] + ["counterexample_replay", "process_logs"]), "Missing or unexpected evidence phase")
    require(len(groups[SECTIONS[0]]) == 2 * len(p["depths"]), "Missing lineage logs")
    for row in result[SECTIONS[0]]["rows"]:
        for config in ("C", "A"):
            cases = [(m, t, c) for m, t, c in groups[SECTIONS[0]]
                     if m["run_id"] == f"stage1b-lineage-{row['depth']}-{config}"]
            require(len(cases) == 1, "Missing or duplicate lineage case")
            meta, trace, checked = cases[0]
            require(len(meta["history"]) == row["requests"], "Lineage request count mismatch")
            if config == "C":
                births = sum(s.get("reason") == "AUTHORIZED_BIRTH" and s.get("decision") == "allow" for s in trace["steps"])
                blocks = sum(s.get("decision") == "block" for s in trace["steps"])
                require(births == row["valid_births"] and blocks == row["injected_blocked_by_R"]
                        and len(meta["history"]) - births == row["injected"], "Lineage aggregate mismatch")
                generations = {}
                for agent, record in trace["registry"].items():
                    ancestor, depth = agent, 0
                    while trace["registry"][ancestor]["parent"] is not None:
                        ancestor = trace["registry"][ancestor]["parent"]
                        depth += 1
                        require(depth <= len(trace["registry"]), "Cyclic lineage")
                    generations[agent] = depth
                    if depth >= max(2, row["depth"] // 3):
                        require("mutate:self" not in record["C"], "Attenuation ineffective")
                require(max(generations.values()) == row["max_lineage_depth_reached"], "Lineage depth mismatch")
            else:
                require((checked["actual_violations"], checked["detected"])
                        == (row["A_executed_violations"], row["A_detected_by_verifier"]), "Lineage negative-control aggregate mismatch")
    require(len(groups[SECTIONS[1]]) == len(groups["process_logs"]) == p["xcheck_histories"], "Missing process cross-check logs")
    for (_, trace, _), (_, events, _) in zip(groups[SECTIONS[1]], groups["process_logs"]):
        require([(s["decision"], s["reason"], s["state"]) for s in trace["steps"] if not s.get("skipped")]
                == [(e["decision"], e["reason"], e["state"]) for e in events], "Independent process/direct cross-check mismatch")
    generated = groups[SECTIONS[2]]
    require(len(generated) == 2 * p["e2_histories"], "Missing generated-history logs")
    for config in ("C", "A"):
        actual = [m["run_id"] for m, _, _ in generated if m["config"] == config]
        expected = [f"stage1b-gen-{seed}" + ("-A" if config == "A" else "")
                    for seed in range(p["e2_seed0"], p["e2_seed0"] + p["e2_histories"])]
        require(actual == expected, "Missing, reordered or duplicate generated seeds")
    digest, reasons = hashlib.sha256(), Counter()
    a_violations = a_detected = accepted = births = conformance = 0
    for meta, trace, checked in generated:
        require(len(meta["history"]) == p["e2_length"], "History length changed")
        if meta["config"] == "C":
            for step in trace["steps"]:
                if not step.get("skipped"):
                    digest.update(step["state"].encode())
                    reasons[step["reason"]] += 1
                    accepted += step["decision"] == "allow"
                    births += step["reason"] == "AUTHORIZED_BIRTH"
                    conformance += bool(step["conformance"])
        else:
            a_violations += checked["actual_violations"]
            a_detected += checked["detected"]
    gen = result[SECTIONS[2]]
    require(digest.hexdigest() == gen["semantic_digest"] and dict(reasons) == gen["reasons"], "Generated semantic digest/count tampering")
    require((accepted, births, conformance) == (gen["accepted"], gen["births"], gen["conformance_C"]), "Generated aggregate mismatch")
    require(a_violations == gen["A_executed_violations"] and a_detected == gen["A_detected"], "Generated detection aggregate mismatch")
    faults = groups[SECTIONS[3]]
    require(len(faults) == len(DEFECTS) * (p["e3_histories"] + 1) - 2, "Missing fault evidence")
    for row in result[SECTIONS[3]]["rows"]:
        defect = row["defect"]
        cases = [(m, t, c) for m, t, c in faults if m["defect"] == defect]
        count = p["e3_histories"] + (0 if defect in ("D05", "D07") else 1)
        require([m["run_id"] for m, _, _ in cases] == [f"stage1b-fault-{defect}-{i}" for i in range(count)], "Fault history coverage changed")
        v = sum(c["actual_violations"] for _, _, c in cases)
        d = sum(c["detected"] for _, _, c in cases)
        latency = [n for _, _, c in cases for n in c["latencies"]]
        require((v, d) == (row["violating_transitions"], row["detected"]), "Fault detection aggregate mismatch")
        require(sum(bool(c["actual_violations"]) for _, _, c in cases) == row["histories_with_violation"], "Fault manifestation count differs")
        require(row["median_latency"] == (statistics.median(latency) if latency else None)
                and row["max_latency"] == (max(latency) if latency else None), "Fault latency mismatch")
    ces = groups["counterexample_replay"]
    require(Counter(m["run_id"] for m, _, _ in ces) == Counter(f"bounded-{d}" for d in DEFECTS + ["A"]), "Missing counterexample replay")
    for name in DEFECTS + ["A", "C"]:
        search = json.loads((output / f"search-{name}.json").read_text())
        if name == "C":
            require({k: v for k, v in search.items() if k != "seconds"}
                    == {k: v for k, v in result[SECTIONS[5]].items() if k != "seconds"}, "Exhaustive record differs from summary")
        else:
            require(search["truncated"] is False and search["counterexample"], "Defect search truncated")
            meta = next(m for m, _, _ in ces if m["run_id"] == f"bounded-{name}")
            counterexample = search["counterexample"]
            require(meta["history"] == counterexample["path"], "Counterexample replay path mismatch")
            row = result[SECTIONS[4]]["baseline_A" if name == "A" else name]
            require(row["violations"] == counterexample["violations"]
                    and row["length"] == len(counterexample["path"]), "Counterexample summary mismatch")
            if name != "A":
                require(row["path"] == counterexample["path"] and row["transitions_searched"] == search["transitions"],
                        "Defect search coverage/path mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=["quick", "full"], required=True)
    args = parser.parse_args()
    report = validate(args.output.resolve(), args.mode)
    print(json.dumps({k: report[k] for k in ("status", "scope", "cases_checked", "errors")}))
    raise SystemExit(0 if report["status"] == "passed" else 1)

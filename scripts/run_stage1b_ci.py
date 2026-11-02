"""Run fixed quick/full Stage 1B modes in a fresh captured source workspace."""
import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

from run_stage1_ci import ROOT, execute, now, server
from verify_stage1b_ci import parameters


def snapshot(source):
    for name in ("dna", "runtime", "simulator", "stage1b"):
        shutil.copytree(ROOT / "src" / name, source / "src" / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    lab = source / "experiments/lab0"
    (lab / "keys").mkdir(parents=True)
    for name in ("genesis.json", "fixtures.json", "experiment-spec.md", "stage1b-robustness.md"):
        shutil.copy2(ROOT / "experiments/lab0" / name, lab / name)
    for name in ("test-signing.seed", "test-signing.pub"):
        shutil.copy2(ROOT / "experiments/lab0/keys" / name, lab / "keys" / name)
    (lab / "results").mkdir()
    (source / "scripts").mkdir()
    for name in ("stage1b_ci_worker.py", "verify_stage1b_ci.py"):
        shutil.copy2(ROOT / "scripts" / name, source / "scripts" / name)


def run(output, mode):
    p = parameters(mode)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    manifest = {"schema_version": 1, "experiment": "stage1b", "mode": mode,
                "scope": "quick_smoke_only" if mode == "quick" else "canonical_full_reproduction",
                "parameters": p, "started_at": now(), "status": "failed",
                "experiment_completion": "not_run", "verification": {"status": "not_run"},
                "research_status": "not_eligible_for_acceptance",
                "seeds": {"generated": [p["e2_seed0"], p["e2_seed0"] + p["e2_histories"] - 1],
                          "fault_generated": [p["e3_seed0"], p["e3_seed0"] + p["e3_histories"] - 1],
                          "process_candidates": [500, 500 + p["xcheck_histories"] * 3 - 1],
                          "process_history_length": 40}}
    try:
        manifest["source"] = server.source_provenance()
        manifest["environment"] = {
            "python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "dependencies": {name: importlib.metadata.version(name)
                             for name in ("cryptography", "cffi", "pycparser", "pytest")},
            "github": {name: os.environ.get(name) for name in (
                "GITHUB_SHA", "GITHUB_REF", "GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
                "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")}}
        source = output / "execution"
        snapshot(source)
        manifest["execution_inputs"] = server._input_file_manifest(source)
        manifest["execution_inputs_sha256"] = server._manifest_digest(manifest["execution_inputs"])
        if server.source_provenance()["state_sha256"] != manifest["source"]["state_sha256"]:
            raise RuntimeError("Source changed while preparing execution inputs")
        (output / "tmp").mkdir()
        env = dict(os.environ, PYTHONPATH=str(source / "src"), TMPDIR=str(output / "tmp"))
        manifest["runner"] = execute(
            [sys.executable, "scripts/stage1b_ci_worker.py", "--mode", mode, "--output", str(output)],
            source, env, output / "runner", 1800 if mode == "quick" else 7200)
        manifest["experiment_completion"] = "completed" if manifest["runner"]["exit_code"] == 0 else "failed"
        # Run independently even after execution failure; partial evidence stays in place.
        manifest["validator"] = execute(
            [sys.executable, "scripts/verify_stage1b_ci.py", "--mode", mode, "--output", str(output)],
            source, env, output / "validator", 1800)
        if (output / "verification.json").is_file():
            report = json.loads((output / "verification.json").read_text())
            manifest["verification"] = {k: report[k] for k in ("status", "scope", "cases_checked", "errors", "limitations")}
        if (manifest["experiment_completion"] == "completed"
                and manifest["validator"]["exit_code"] == 0 and manifest["verification"]["status"] == "passed"):
            manifest["status"] = "succeeded"
            manifest["research_status"] = "pending_smoke_review" if mode == "quick" else "pending_human_review"
    except Exception as error:
        manifest["error"] = f"{type(error).__name__}: {error}"
    finally:
        manifest["finished_at"] = now()
        manifest["elapsed_seconds"] = round(time.monotonic() - started, 3)
        manifest["artifact_files"] = server._input_file_manifest(output, {"__pycache__"})
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: manifest[k] for k in ("mode", "scope", "status", "experiment_completion", "verification")}))
    return 0 if manifest["status"] == "succeeded" else 1


def summarize(output, tests):
    try:
        manifest = json.loads((output / "manifest.json").read_text())
    except (OSError, ValueError):
        manifest = {}
    verified = manifest.get("verification", {}).get("status") == "passed"
    passed = (tests == "success" and manifest.get("status") == "succeeded"
              and manifest.get("experiment_completion") == "completed" and verified)
    status = {"mode": manifest.get("mode", "unavailable"), "scope": manifest.get("scope", "unavailable"),
              "source_commit": manifest.get("source", {}).get("source_commit", "unavailable"),
              "worktree_state": manifest.get("source", {}).get("worktree_state", "unavailable"),
              "tests": tests, "experiment_completion": manifest.get("experiment_completion", "not_run"),
              "independent_verification": manifest.get("verification", {}).get("status", "not_run"),
              "automation_status": "passed" if passed else "failed_or_incomplete",
              "research_status": manifest.get("research_status") if passed else "not_eligible_for_acceptance",
              "artifact_upload": "not_confirmed_here_check_upload_step"}
    (output / "workflow-status.json").write_text(json.dumps(status, indent=2) + "\n")
    files = server._input_file_manifest(output, {"__pycache__"})
    (output / "bundle-hashes.json").write_text(json.dumps([r for r in files if r["path"] != "bundle-hashes.json"], indent=2) + "\n")
    print("### Stage 1B execution and research review\n")
    for key, value in status.items():
        print(f"- {key}: {json.dumps(value)}")
    print("\nQuick is a smoke test, never full reproduction. TC-22 and TC-26 limitations remain. "
          "Bounded evidence is not formal proof, general security or novelty. Human research approval is required.")
    for error in manifest.get("verification", {}).get("errors", [])[:20]:
        print(f"- verification error: {json.dumps(error)}")
    if manifest.get("error"):
        print(f"- diagnostic: {json.dumps(manifest['error'])}")
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--tests-outcome", choices=["success", "failure", "skipped", "cancelled", ""], default="")
    args = parser.parse_args()
    raise SystemExit(summarize(args.output, args.tests_outcome) if args.summary else run(args.output, args.mode))

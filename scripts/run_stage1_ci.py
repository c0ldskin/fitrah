"""Run only canonical Stage 1, retaining evidence even when execution fails."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ui import server  # Existing snapshot and negative-control expectations.


def now():
    return datetime.now(timezone.utc).isoformat()


def execute(command, cwd, env, prefix, timeout):
    """Retain raw output and exit status, including timeout diagnostics."""
    result = {"command": command, "started_at": now(), "exit_code": None}
    stdout = stderr = b""
    try:
        process = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                 timeout=timeout, check=False)
        stdout, stderr = process.stdout, process.stderr
        result["exit_code"] = process.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        result["error"] = f"Timeout after {timeout} seconds"
    except OSError as error:
        result["error"] = str(error)
    prefix.with_suffix(".stdout.txt").write_bytes(stdout)
    prefix.with_suffix(".stderr.txt").write_bytes(stderr)
    result["finished_at"] = now()
    return result


def verify_logs(source, output, env):
    reports = []
    logs = source / "experiments/lab0/logs"
    found = sorted(p.stem for p in logs.glob("*.jsonl"))
    for log_id in server.STAGE1_EXPECTED_LOG_IDS:
        log = logs / f"{log_id}.jsonl"
        row = {"log": log.name, "valid": False}
        if not log.is_file():
            row["error"] = "Missing expected log"
        else:
            command = [sys.executable, "src/simulator/verify.py", str(log),
                       "experiments/lab0/genesis.json", "experiments/lab0/keys/test-signing.pub",
                       "experiments/lab0/fixtures.json", "--json"]
            row.update(execute(command, source, env, output / log_id, 30))
            try:
                report = json.loads((output / f"{log_id}.stdout.txt").read_bytes())
                if not isinstance(report, dict):
                    raise ValueError("Verifier report is not an object")
                row["report"] = report
                if (type(report.get("entries")) is not int
                        or not isinstance(report.get("integrity_failures"), list)
                        or not isinstance(report.get("violations"), list)
                        or type(report.get("ok")) is not bool
                        or "error" in report
                        or report["ok"] != (not report["integrity_failures"] and not report["violations"])):
                    raise ValueError("Incomplete or inconsistent verifier report")
                row.update(server._verification_outcome(log_id, report, row["exit_code"]))
            except (ValueError, TypeError, AttributeError) as error:
                row.update(valid=False, error=f"Invalid verifier report: {error}")
        reports.append(row)
    summary = server._stage1_verification_summary(reports, found)
    return {**summary, "status": "passed" if summary["passed"] else "failed",
            "logs_checked": sum("command" in row for row in reports), "logs": reports}


def run(output):
    # A fresh directory prevents stale evidence from satisfying this run.
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 2, "experiment": "canonical-stage1",
                "started_at": now(), "status": "failed",
                "research_status": "not_eligible_for_acceptance",
                "experiment_completion": "not_run", "verification": {"status": "not_run"}}
    try:
        manifest["source"] = server.source_provenance()
        manifest["environment"] = {
            "python": sys.version, "platform": platform.platform(),
            "dependencies": {name: importlib.metadata.version(name)
                             for name in ("cryptography", "pytest", "cffi")},
            "github": {name: os.environ.get(name) for name in (
                "GITHUB_SHA", "GITHUB_REF", "GITHUB_REPOSITORY", "GITHUB_RUN_ID",
                "GITHUB_RUN_ATTEMPT", "GITHUB_WORKFLOW", "GITHUB_ACTOR",
                "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")},
        }
        source = output / "execution"
        server._copy_inputs(source, "lab0-stage1")
        for cache in source.rglob("__pycache__"):
            shutil.rmtree(cache)
        manifest["execution_inputs"] = server._input_file_manifest(source)
        manifest["execution_inputs_sha256"] = server._manifest_digest(manifest["execution_inputs"])
        after = server.source_provenance()
        if after["state_sha256"] != manifest["source"]["state_sha256"]:
            raise RuntimeError("Source changed while preparing execution inputs")
        env = dict(os.environ, PYTHONPATH=str(source / "src"))
        manifest["runner"] = execute([sys.executable, "src/simulator/run.py"],
                                     source, env, output / "runner", 600)
        manifest["experiment_completion"] = (
            "completed" if manifest["runner"]["exit_code"] == 0 else "failed")
        # Verify all available evidence even after runner failure; never use historical logs.
        manifest["verification"] = verify_logs(source, output, env)
        result = source / "experiments/lab0/results/stage1.json"
        manifest["stage1_pass"] = json.loads(result.read_text()).get("stage1_pass") if result.exists() else None
        if (manifest["experiment_completion"] == "completed"
                and manifest["stage1_pass"] is True
                and manifest["verification"]["status"] == "passed"):
            manifest["status"] = "succeeded"
            manifest["research_status"] = "pending_human_review"
    except Exception as error:
        manifest["error"] = f"{type(error).__name__}: {error}"
    finally:
        manifest["finished_at"] = now()
        # All retained files except this self-referential manifest are hashed.
        manifest["artifact_files"] = server._input_file_manifest(output, {"__pycache__"})
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: manifest[key] for key in ("status", "experiment_completion")}))
    return 0 if manifest["status"] == "succeeded" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New, unused artifact directory")
    raise SystemExit(run(parser.parse_args().output))

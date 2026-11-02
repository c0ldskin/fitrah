"""Report automation outcomes without granting research acceptance."""
import argparse
import hashlib
import json
from pathlib import Path


def summarize(output, tests_outcome):
    try:
        manifest = json.loads((output / "manifest.json").read_text())
    except (OSError, ValueError):
        manifest = {}
    verified = manifest.get("verification", {}).get("status") == "passed"
    succeeded = (manifest.get("status") == "succeeded"
                 and manifest.get("experiment_completion") == "completed"
                 and manifest.get("stage1_pass") is True and verified)
    eligible = succeeded and tests_outcome == "success"
    status = {
        "source_commit": manifest.get("source", {}).get("source_commit", "unavailable"),
        "source_ref": manifest.get("source", {}).get("source_ref", "unavailable"),
        "source_worktree": manifest.get("source", {}).get("worktree_state", "unavailable"),
        "execution_inputs_sha256": manifest.get("execution_inputs_sha256", "unavailable"),
        "tests": tests_outcome,
        "experiment_completion": manifest.get("experiment_completion", "not_run"),
        "independent_verification": manifest.get("verification", {}).get("status", "not_run"),
        "experiment_status": manifest.get("status", "not_run"),
        "logs_checked": manifest.get("verification", {}).get("logs_checked", 0),
        "automation_status": "passed" if eligible else "failed_or_incomplete",
        "research_status": "pending_human_review" if eligible else "not_eligible_for_acceptance",
        "artifact_upload": "not_confirmed_here_check_upload_step",
    }
    (output / "workflow-status.json").write_text(json.dumps(status, indent=2) + "\n")
    # Includes manifest and JUnit report, unlike the runner's pre-finalization inventory.
    inventory = [{"path": p.relative_to(output).as_posix(),
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(output.rglob("*")) if p.is_file()
                 and "__pycache__" not in p.parts and p != output / "bundle-hashes.json"]
    (output / "bundle-hashes.json").write_text(json.dumps(inventory, indent=2) + "\n")
    print("### Stage 1 execution and research review\n")
    for key, value in status.items():
        # JSON escaping keeps branch names and diagnostics on a single summary line.
        print(f"- {key}: {json.dumps(value, ensure_ascii=True)}")
    if manifest.get("error"):
        print(f"- diagnostic: {json.dumps(manifest['error'], ensure_ascii=True)}")
    for row in manifest.get("verification", {}).get("logs", []):
        print(f"- {row['log']}: valid={row.get('valid', False)}, "
              f"outcome={row.get('expected_outcome', 'unavailable')}, "
              f"exit_code={row.get('exit_code')}")
    print("\nDownload evidence and full verifier reports. A/B findings are expected negative controls. "
          "Regression diagnostics contain intentionally failed test fixtures, not research results. "
          "No Stage 2 or full Lab 0 claim; human research approval is required.")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tests-outcome", required=True,
                        choices=["success", "failure", "cancelled", "skipped", ""])
    args = parser.parse_args()
    status = summarize(args.output, args.tests_outcome)
    raise SystemExit(0 if status["automation_status"] == "passed" else 1)

"""Loopback-only research workbench for the canonical Fitrah repository.

The workbench reads canonical definitions and historical artifacts in place. It
does not reimplement the Fitrah runtime. Experiment subprocesses run only from a
small temporary snapshot and only through the fixed allowlist below.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = Path(os.environ.get(
    "FITRAH_WORKBENCH_RUN_DIR", str(Path.home() / ".fitrah-workbench" / "runs")
)).expanduser()
HOST = "127.0.0.1"
PORT = int(os.environ.get("FITRAH_WORKBENCH_PORT", "8765"))
MAX_BODY = 16_384
JOB_LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}

RUNNERS = {
    "lab0-stage1": {
        "label": "Lab 0 · Stage 1 regression",
        "command": ["src/simulator/run.py"],
        "timeout": 600,
        "scope": "A0 scripted agents · deterministic · no Stage 2 execution",
    },
    "stage1b-quick": {
        "label": "Stage 1B · quick robustness search",
        "command": ["src/stage1b/run.py", "--quick"],
        "timeout": 300,
        "scope": "Bounded deterministic model search · no hostile OS execution",
    },
    "nonvm-e1-e5": {
        "label": "Non-VM · E1–E5 model experiments",
        "command": ["experiments/nonvm/run_models.py"],
        "timeout": 300,
        "scope": "Deterministic formal models · no VM or Stage 2 execution",
    },
}

STAGE1_LOG_DIR = ROOT / "experiments/lab0/logs"
STAGE1_EXPECTED_LOG_IDS = (
    "stage1-A-rep1", "stage1-A-rep2", "stage1-B-rep1",
    "stage1-B-rep2", "stage1-C-rep1", "stage1-C-rep2",
)
STAGE1_EXPECTED_ENTRY_COUNT = 67

# Negative-control expectations follow the frozen Stage 1 procedure: every
# enforcement-blocked scenario executes and is flagged in A/B, except malformed
# input S42. Counts are verifier findings per scenario, not changed invariants.
STAGE1_AB_EXPECTED_FINDINGS = Counter({
    ("S10", "F1"): 1, ("S10", "F1h"): 1,
    ("S11", "F1"): 2, ("S11", "F1h"): 1,
    ("S12", "F1"): 1, ("S12", "F1h"): 1,
    ("S13", "F2h"): 1, ("S13", "F2"): 1,
    ("S14", "Policy_0:mutate"): 1, ("S15", "CAP:mutate"): 1,
    ("S20", "F1h"): 3, ("S21", "F1h"): 3, ("S22", "F1h"): 3,
    ("S23", "F4"): 1, ("S24", "F4"): 1, ("S25", "F4"): 1,
    ("S30", "F2"): 1, ("S31", "F2"): 1, ("S32", "W1"): 1,
    ("S33", "F2"): 1, ("S40", "F3"): 1, ("S41", "F3"): 1,
    ("S43", "IDENTITY"): 1, ("S43", "F3"): 1,
})


def stage1_logs() -> dict[str, Path]:
    return {path.stem: path for path in sorted(STAGE1_LOG_DIR.glob("stage1-*-rep*.jsonl"))}


def read_text(relative: str, limit: int = 2_000_000) -> str:
    path = ROOT / relative
    try:
        if path.stat().st_size > limit:
            return path.read_text(errors="replace")[:limit]
        return path.read_text(errors="replace")
    except (OSError, UnicodeError):
        return ""


def read_json(relative: str) -> dict[str, Any] | list[Any] | None:
    try:
        value = json.loads(read_text(relative))
        return value
    except (json.JSONDecodeError, TypeError):
        return None


def sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def git_value(*args: str) -> str | None:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                             capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        if Path(top).resolve() != ROOT.resolve():
            return None
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
            timeout=3, check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _git_bytes(*args: str) -> bytes | None:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                             capture_output=True, timeout=3, check=True).stdout.decode().strip()
        if Path(top).resolve() != ROOT.resolve():
            return None
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              timeout=5, check=True).stdout
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def _git_source_state() -> dict[str, Any] | None:
    """Capture the exact checked-out commit and tracked/untracked worktree state."""
    commit = git_value("rev-parse", "HEAD")
    status = _git_bytes("status", "--porcelain=v1", "--untracked-files=all", "-z")
    unstaged = _git_bytes("diff", "--binary")
    staged = _git_bytes("diff", "--cached", "--binary")
    untracked = _git_bytes("ls-files", "--others", "--exclude-standard", "-z")
    if not commit or status is None or unstaged is None or staged is None or untracked is None:
        return None
    untracked_files = []
    for raw_path in untracked.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        file_path = ROOT / path
        untracked_files.append({"path": path, "sha256": sha256(file_path),
                                "size_bytes": file_path.stat().st_size if file_path.is_file() else None})
    state_payload = {
        "status": status.decode("utf-8", errors="replace"),
        "unstaged_diff_sha256": hashlib.sha256(unstaged).hexdigest(),
        "staged_diff_sha256": hashlib.sha256(staged).hexdigest(),
        "untracked_files": untracked_files,
    }
    state_bytes = json.dumps(state_payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
    return {
        "commit": commit, "ref": git_value("symbolic-ref", "--quiet", "--short", "HEAD"),
        "worktree_state": "modified" if status else "clean",
        "status_porcelain_v1": status.decode("utf-8", errors="replace").replace("\0", "\\0"),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "unstaged_diff_sha256": hashlib.sha256(unstaged).hexdigest(),
        "staged_diff_sha256": hashlib.sha256(staged).hexdigest(),
        "untracked_files": untracked_files,
        "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "identity_source": "git_worktree",
    }


def source_provenance() -> dict[str, Any]:
    """Resolve a run's canonical commit and exact local source-state identity."""
    state = _git_source_state()
    declared_commit = os.environ.get("FITRAH_SOURCE_COMMIT", "").strip()
    declared_ref = os.environ.get("FITRAH_SOURCE_REF", "").strip() or None
    if state is not None:
        if declared_commit and declared_commit.lower() != state["commit"].lower():
            raise ValueError("FITRAH_SOURCE_COMMIT does not match the checked-out Git commit")
        return {**state, "canonical_repository": "https://github.com/c0ldskin/fitrah",
                "source_commit": state["commit"], "source_ref": state["ref"],
                "commit_identity_status": "recorded_from_git_checkout",
                "commit_identity_method": "git rev-parse HEAD",
                "captured_at": datetime.now(timezone.utc).isoformat()}
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", declared_commit):
        raise ValueError("A full Git checkout is required, or declare a full FITRAH_SOURCE_COMMIT for an unverified temporary source snapshot")
    snapshot_files = _input_file_manifest(ROOT, exclude_parts={".git", ".venv", "local-runs",
                                                                ".pytest_cache", "__pycache__"})
    return {
        "canonical_repository": "https://github.com/c0ldskin/fitrah",
        "source_commit": declared_commit.lower(), "commit": declared_commit.lower(),
        "source_ref": declared_ref, "ref": declared_ref,
        "worktree_state": "unversioned_snapshot",
        "status_porcelain_v1": None, "status_sha256": None,
        "unstaged_diff_sha256": None, "staged_diff_sha256": None,
        "untracked_files": [], "snapshot_files": snapshot_files,
        "state_sha256": _manifest_digest(snapshot_files),
        "identity_source": "unverified_declared_commit",
        "commit_identity_status": "unverified_declared_commit",
        "commit_identity_method": "FITRAH_SOURCE_COMMIT format only; snapshot ancestry was not authenticated",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def _input_file_manifest(root: Path, exclude_parts: set[str] | None = None) -> list[dict[str, Any]]:
    exclude_parts = exclude_parts or set()
    rows = []
    for path in sorted(item for item in root.rglob("*")
                       if item.is_file() and not (set(item.relative_to(root).parts) & exclude_parts)):
        rows.append({"path": path.relative_to(root).as_posix(),
                     "sha256": sha256(path), "size_bytes": path.stat().st_size})
    return rows


def _manifest_digest(files: list[dict[str, Any]]) -> str:
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def machine_info() -> dict[str, Any]:
    memory = None
    try:
        memory = round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 ** 3), 1)
    except (ValueError, OSError, AttributeError):
        pass
    return {
        "system": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "processor": platform.processor() or platform.machine(),
        "python": platform.python_version(), "logical_cpus": os.cpu_count(),
        "memory_gib": memory,
    }


def _historical_stage1() -> dict[str, Any] | None:
    result = read_json("experiments/lab0/results/stage1.json")
    if not isinstance(result, dict):
        return None
    configs = result.get("configs", {})
    return {
        "kind": "historical", "title": "Lab 0 Stage 1 regression",
        "stage": result.get("stage", "Stage 1"), "spec": result.get("spec", "v0.4"),
        "pass": result.get("stage1_pass"),
        "source": "experiments/lab0/results/stage1.json",
        "configs": {
            key: (value.get("metrics", {}) if isinstance(value, dict) else {})
            for key, value in configs.items() if key in {"A", "B", "C"}
        },
        "reproducibility": result.get("reproducibility", {}),
    }


def _historical_stage1b() -> dict[str, Any] | None:
    result = read_json("experiments/lab0/results/stage1b.json")
    if not isinstance(result, dict):
        return None
    return {
        "kind": "historical", "title": "Stage 1B robustness",
        "source": "experiments/lab0/results/stage1b.json",
        "environment": result.get("environment", {}),
        "parameters": result.get("parameters", {}),
        "sections": sorted(key for key in result if key not in {"environment", "parameters", "spec"}),
    }


def _nonvm_results() -> dict[str, Any]:
    result = read_json("experiments/nonvm/results/summary.json")
    return result if isinstance(result, dict) else {}


def _open_questions() -> list[dict[str, str]]:
    rows = []
    for line in read_text("research/open-questions.md").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"OQ-\d+", cells[0]):
            rows.append({"id": cells[0], "question": cells[1], "origin": cells[2], "blocks": cells[3]})
    return rows


def _novelty_evidence() -> list[dict[str, str]]:
    files = [
        ("E1–E2", "experiments/nonvm/results/e1-e2-constitutional-delegation.md"),
        ("E3", "experiments/nonvm/results/e3-birth-lifecycle.md"),
        ("E4", "experiments/nonvm/results/e4-external-truth.md"),
        ("E5", "experiments/nonvm/results/e5-population-collusion.md"),
        ("E6", "experiments/nonvm/results/e6-strong-broker-ablation.md"),
        ("E8", "experiments/nonvm/results/e8-lineage-evidence.md"),
        ("E9", "experiments/nonvm/results/e9-birth-instance-binding.md"),
        ("E7", "experiments/nonvm/e7-lineage-conservation.md"),
    ]
    out = []
    for experiment, path in files:
        content = read_text(path)
        if not content:
            continue
        summary = next((line.strip(" #\t") for line in content.splitlines()
                        if line.startswith("Status:") or line.startswith("[RESULT]")), "Result recorded")
        out.append({"experiment": experiment, "source": path, "summary": summary[:280]})
    return out


def _novelty_decisions() -> list[dict[str, str]]:
    decisions = []
    accepted_pattern = re.compile(r"\[DECISION\]\s*`?\s*(TC-\d+)\s*:?[` ]*\s*(.*)", re.IGNORECASE)
    candidate_pattern = re.compile(r"\[TC CANDIDATE\s+(TC-\d+)\]\s*`?\s*(.*)", re.IGNORECASE)
    for line in read_text("research/changelog.md").splitlines():
        match = accepted_pattern.search(line)
        status = "accepted"
        if not match:
            match = candidate_pattern.search(line)
            status = "candidate"
        if match is None:
            continue
        tc_id, summary = match.groups()
        decisions.append({"id": tc_id, "status": status, "summary": summary.strip().rstrip(". ")})
    return decisions[-20:]


def _historical_stage2() -> list[dict[str, str]]:
    results = ROOT / "experiments/lab0/results"
    found = []
    if results.exists():
        for path in sorted(results.rglob("*")):
            if path.is_file() and ("stage2" in path.name.lower() or "stage2-" in str(path).lower()):
                rel = path.relative_to(ROOT).as_posix()
                if not path.name.endswith(".seed"):
                    found.append({"source": rel, "label": path.name, "kind": "historical artifact"})
    return found


def _historical_evidence_artifacts() -> list[dict[str, Any]]:
    """Index every committed experiment log/result without filtering by outcome."""
    experiments = ROOT / "experiments"
    artifacts = []
    if not experiments.exists():
        return artifacts
    for path in sorted(item for item in experiments.rglob("*") if item.is_file()):
        relative = path.relative_to(ROOT)
        if path.suffix == ".seed":
            continue
        parts = set(relative.parts)
        is_e7_note = relative.as_posix() == "experiments/nonvm/e7-lineage-conservation.md"
        if not ({"results", "logs"} & parts) and not is_e7_note:
            continue
        if path.name == ".gitkeep":
            continue
        category = "log" if "logs" in parts or path.suffix in {".jsonl", ".log"} else "result"
        artifacts.append({"path": relative.as_posix(), "label": path.name,
                          "kind": category, "sha256": sha256(path),
                          "size_bytes": path.stat().st_size})
    return artifacts


def _local_runs() -> list[dict[str, Any]]:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    out = []
    for manifest_path in sorted(RUN_ROOT.glob("*/manifest.json"), reverse=True):
        try:
            item = json.loads(manifest_path.read_text())
            item["run_dir"] = str(manifest_path.parent)
            out.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def dashboard_data() -> dict[str, Any]:
    stage1 = _historical_stage1()
    stage1b = _historical_stage1b()
    nonvm = _nonvm_results()
    status = read_text("experiments/lab0/README.md")
    readme_status = next((line.strip()[8:] for line in status.splitlines()
                          if line.strip().startswith("Status:")), "Status not recorded")
    repository_commit = git_value("rev-parse", "HEAD") or os.environ.get("FITRAH_SOURCE_COMMIT")
    return {
        "repository": {
            "name": "c0ldskin/fitrah", "branch": git_value("rev-parse", "--abbrev-ref", "HEAD") or os.environ.get("FITRAH_SOURCE_REF"),
            "commit": repository_commit,
            "dirty": bool(git_value("status", "--porcelain")) if repository_commit else None,
            "canonical": "https://github.com/c0ldskin/fitrah",
            "identity_source": "git_worktree" if git_value("rev-parse", "HEAD") else (
                "unverified_declared_commit" if os.environ.get("FITRAH_SOURCE_COMMIT") else "unavailable"),
        },
        "machine": machine_info(), "research_status": readme_status,
        "invariants": [line.strip() for line in read_text("research/invariants.md").splitlines()
                       if re.match(r"^#{2,3} F[1-6]", line.strip())],
        "experiments": {
            "stage1": stage1, "stage1b": stage1b,
            "nonvm": nonvm, "stage2_execution_enabled": False,
            "stage2_artifacts": _historical_stage2(),
            "runners": [{"id": key, **{k: v for k, v in value.items() if k != "command"}}
                        for key, value in RUNNERS.items()],
            "local_runs": _local_runs(),
        },
        "evidence": {
            "historical_logs": [
                {"id": key, "path": str(path.relative_to(ROOT)), "exists": path.is_file(),
                 "sha256": sha256(path)} for key, path in stage1_logs().items()
            ],
            "historical_artifacts": _historical_evidence_artifacts(),
            "historical_findings": "experiments/lab0/results/stage1-findings.md",
        },
        "novelty": {
            "review_status": next((line.strip() for line in read_text("research/prior-art-matrix.md").splitlines()
                                    if line.startswith("Status:")), "Status not recorded"),
            "prior_art": "research/prior-art-matrix.md",
            "open_questions": _open_questions(), "evidence": _novelty_evidence(),
            "decisions": _novelty_decisions(),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_log(log_id: str) -> dict[str, Any]:
    """Invoke Fitrah's independent verifier on one allowlisted historical log."""
    log_path = stage1_logs().get(log_id)
    if log_path is None or not log_path.is_file():
        raise ValueError("Unknown or unavailable Stage 1 evidence log")
    command = [
        sys.executable, "src/simulator/verify.py", str(log_path),
        "experiments/lab0/genesis.json", "experiments/lab0/keys/test-signing.pub",
        "experiments/lab0/fixtures.json", "--json",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = {"ok": False, "output": result.stdout[-4000:], "error": result.stderr[-4000:]}
    outcome = _verification_outcome(log_id, report, result.returncode)
    return {
        "evidence_id": log_id, "source": str(log_path.relative_to(ROOT)),
        "sha256": sha256(log_path), "verification": report,
        "expected_outcome": outcome["expected_outcome"], "verification_valid": outcome["valid"],
        "verification_status": "passed" if outcome["valid"] else "failed",
        "verification_scope": "independent Stage 1 log verifier",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "verifier_command": "python src/simulator/verify.py <allowlisted Stage 1 log> genesis.json test-signing.pub fixtures.json --json",
        "exit_code": result.returncode,
    }


def _verification_outcome(log_name: str, report: dict[str, Any], exit_code: int) -> dict[str, Any]:
    """Distinguish expected negative-control violations from verifier failures."""
    match = re.search(r"stage1-([ABC])-rep\d+", log_name)
    config = match.group(1) if match else None
    integrity_failures = report.get("integrity_failures")
    integrity_ok = isinstance(integrity_failures, list) and not integrity_failures
    entries = report.get("entries")
    entries_ok = entries == STAGE1_EXPECTED_ENTRY_COUNT
    violations = report.get("violations")
    if not isinstance(violations, list):
        violations = [{"scenario": None, "invariant": None, "finding": violations}]
    outcome: dict[str, Any] = {
        "valid": False,
        "expected_outcome": "unexpected",
        "expected_entry_count": STAGE1_EXPECTED_ENTRY_COUNT,
        "actual_entry_count": entries,
        "integrity_failure_count": len(integrity_failures) if isinstance(integrity_failures, list) else None,
        "unexpected_violations": [],
        "missing_expected_violations": [],
    }
    if config in {"A", "B"}:
        actual = Counter()
        unexpected = []
        for finding in violations:
            key = (finding.get("scenario"), finding.get("invariant")) if isinstance(finding, dict) else (None, None)
            actual[key] += 1
            if key not in STAGE1_AB_EXPECTED_FINDINGS or actual[key] > STAGE1_AB_EXPECTED_FINDINGS[key]:
                unexpected.append(finding)
        missing = [
            {"scenario": scenario, "invariant": invariant, "expected_count": expected,
             "actual_count": actual[(scenario, invariant)]}
            for (scenario, invariant), expected in sorted(STAGE1_AB_EXPECTED_FINDINGS.items())
            if actual[(scenario, invariant)] < expected
        ]
        valid = integrity_ok and entries_ok and exit_code == 1 and not unexpected and not missing
        outcome.update({
            "valid": valid,
            "expected_outcome": "baseline_violations_detected" if valid else "unexpected_baseline_findings",
            "unexpected_violations": unexpected,
            "missing_expected_violations": missing,
        })
        return outcome
    if config == "C":
        valid = integrity_ok and entries_ok and not violations and exit_code == 0
        outcome.update({
            "valid": valid,
            "expected_outcome": "enforced_log_clean" if valid else "unexpected_enforced_findings",
            "unexpected_violations": violations,
        })
        return outcome
    outcome["expected_outcome"] = "unclassified_log"
    outcome["unexpected_violations"] = violations
    return outcome


def _completed_run_status(experiment_id: str, evidence_verification: dict[str, Any]) -> str:
    """Keep runner completion distinct from an independently supported result."""
    if experiment_id == "lab0-stage1":
        return "succeeded" if evidence_verification.get("status") == "passed" else "verification_failed"
    if evidence_verification.get("status") == "not_run":
        return "completed_unverified"
    return "succeeded" if evidence_verification.get("status") == "passed" else "verification_failed"


def _stage1_verification_summary(verification: list[dict[str, Any]], found_log_ids: list[str]) -> dict[str, Any]:
    missing = sorted(set(STAGE1_EXPECTED_LOG_IDS) - set(found_log_ids))
    unexpected = sorted(set(found_log_ids) - set(STAGE1_EXPECTED_LOG_IDS))
    passed = (found_log_ids == list(STAGE1_EXPECTED_LOG_IDS)
              and len(verification) == len(STAGE1_EXPECTED_LOG_IDS)
              and all(item.get("valid") for item in verification))
    return {"passed": passed, "missing_logs": missing, "unexpected_logs": unexpected,
            "expected_log_ids": list(STAGE1_EXPECTED_LOG_IDS)}


def _copy_inputs(source: Path, runner: str) -> None:
    if runner == "lab0-stage1":
        for name in ("dna", "runtime", "simulator"):
            shutil.copytree(ROOT / "src" / name, source / "src" / name)
        lab = source / "experiments/lab0"
        (lab / "keys").mkdir(parents=True, exist_ok=True)
        for name in ("genesis.json", "fixtures.json", "experiment-spec.md"):
            shutil.copy2(ROOT / "experiments/lab0" / name, lab / name)
        for name in ("test-signing.seed", "test-signing.pub"):
            shutil.copy2(ROOT / "experiments/lab0/keys" / name, lab / "keys" / name)
        (lab / "logs").mkdir(exist_ok=True)
        (lab / "results").mkdir(exist_ok=True)
    elif runner == "stage1b-quick":
        for name in ("dna", "runtime", "simulator", "stage1b"):
            if (ROOT / "src" / name).is_dir():
                shutil.copytree(ROOT / "src" / name, source / "src" / name)
        shutil.copytree(ROOT / "experiments/lab0", source / "experiments/lab0",
                        ignore=shutil.ignore_patterns("logs", "results", "stage2-env"))
    elif runner == "nonvm-e1-e5":
        shutil.copytree(ROOT / "experiments/nonvm", source / "experiments/nonvm")
    else:
        raise ValueError("Runner is not allowlisted")


def _run_experiment(run_id: str, experiment_id: str) -> None:
    job = JOBS[run_id]
    spec = RUNNERS[experiment_id]
    provenance = job["source_provenance"]
    started = datetime.now(timezone.utc).isoformat()
    job.update({"status": "running", "started_at": started})
    run_dir = RUN_ROOT / run_id
    base = {
        "run_id": run_id, "experiment_id": experiment_id, "title": spec["label"],
        "execution_target": "mac-local-safe",
        "status": "running", "experiment_completion": "running", "started_at": started,
        "repository_commit": provenance["source_commit"],
        "source_provenance": provenance,
        "evidence_verification": {"status": "not_run", "logs_checked": 0},
        "spec_sha256": sha256(ROOT / ("experiments/lab0/experiment-spec.md" if experiment_id.startswith(("lab0", "stage1b")) else "experiments/nonvm/experiment-brief.md")),
        "runner_sha256": sha256(ROOT / spec["command"][0]),
        "command": [sys.executable, *spec["command"]], "scope": spec["scope"],
        "platform": platform.platform(), "python": platform.python_version(),
    }
    try:
        RUN_ROOT.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir(parents=True, exist_ok=False)
        with tempfile.TemporaryDirectory(prefix="fitrah-workbench-") as temp:
            scratch = Path(temp)
            _copy_inputs(scratch, experiment_id)
            input_files = _input_file_manifest(scratch)
            base["execution_snapshot"] = {
                "kind": "temporary_execution_snapshot",
                "source_commit": provenance["source_commit"],
                "source_tree_sha256": _manifest_digest(input_files),
                "file_count": len(input_files), "files": input_files,
            }
            end_provenance = source_provenance()
            base["source_provenance_after_snapshot"] = end_provenance
            if end_provenance["state_sha256"] != provenance["state_sha256"]:
                raise RuntimeError("Source checkout changed while the execution snapshot was being prepared")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(scratch / "src")
            command = [sys.executable, *spec["command"]]
            completed = subprocess.run(
                command, cwd=scratch, env=env, capture_output=True, text=True,
                timeout=spec["timeout"], check=False,
            )
            base["runner_exit_code"] = completed.returncode
            if completed.returncode == 0:
                base["experiment_completion"] = "completed"
            (run_dir / "stdout.txt").write_text(completed.stdout)
            (run_dir / "stderr.txt").write_text(completed.stderr)
            if completed.returncode != 0:
                raise RuntimeError(f"Experiment exited {completed.returncode}: {completed.stderr[-1600:]}")
            if experiment_id == "lab0-stage1":
                shutil.copy2(scratch / "experiments/lab0/results/stage1.json", run_dir / "result.json")
                result_data = json.loads((run_dir / "result.json").read_text())
                base["experiment_result"] = {
                    "stage1_pass": result_data.get("stage1_pass"),
                    "stage": result_data.get("stage"),
                    "interpretation": "Stage 1 result only; not a full Lab 0 pass.",
                }
                base["result_sha256"] = sha256(run_dir / "result.json")
                verification = []
                stage1_logs = sorted((scratch / "experiments/lab0/logs").glob("stage1-*.jsonl"))
                found_log_ids = [log.stem for log in stage1_logs]
                for log in stage1_logs:
                    command = [sys.executable, "src/simulator/verify.py", str(log),
                               "experiments/lab0/genesis.json", "experiments/lab0/keys/test-signing.pub",
                               "experiments/lab0/fixtures.json", "--json"]
                    try:
                        checked = subprocess.run(command, cwd=scratch, env=env, capture_output=True,
                                                 text=True, timeout=30, check=False)
                        report = json.loads(checked.stdout) if checked.stdout else {
                            "ok": False, "output": checked.stderr[-4000:], "error": "Verifier returned no JSON report"}
                        verifier_exit_code = checked.returncode
                    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
                        report = {"ok": False, "entries": 0, "integrity_failures": [],
                                  "violations": [], "error": str(error)}
                        verifier_exit_code = None
                    outcome = _verification_outcome(log.name, report, verifier_exit_code)
                    verification.append({"log": log.name, "sha256": sha256(log), "exit_code": verifier_exit_code,
                                         "verification": report, **outcome})
                shutil.copytree(scratch / "experiments/lab0/logs", run_dir / "logs")
                base["independent_verification"] = verification
                verification_summary = _stage1_verification_summary(verification, found_log_ids)
                base["verification_pass"] = verification_summary["passed"]
                base["evidence_verification"] = {
                    "status": "passed" if base["verification_pass"] else "failed",
                    "scope": "independent Stage 1 log verifier",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "logs_checked": len(verification),
                    "expected_log_ids": verification_summary["expected_log_ids"],
                    "missing_logs": verification_summary["missing_logs"],
                    "unexpected_logs": verification_summary["unexpected_logs"],
                    "expected_baseline_violations": sum(
                        x["expected_outcome"] == "baseline_violations_detected" for x in verification),
                    "logs": verification,
                }
            elif experiment_id == "stage1b-quick":
                written = re.search(r"wrote (.+stage1b-quick\.json)", completed.stdout)
                if not written:
                    raise RuntimeError("Stage 1B runner completed without a result file path")
                shutil.copy2(Path(written.group(1)), run_dir / "result.json")
                result_data = json.loads((run_dir / "result.json").read_text())
                base["result_sha256"] = sha256(run_dir / "result.json")
                base["result_sections"] = sorted(k for k in result_data if k not in {"environment", "parameters", "spec"})
            else:
                result_data = json.loads(completed.stdout)
                (run_dir / "result.json").write_text(json.dumps(result_data, indent=2, sort_keys=True) + "\n")
                base["result_sha256"] = sha256(run_dir / "result.json")
                base["result_sections"] = sorted(result_data)
            if experiment_id != "lab0-stage1":
                base["evidence_verification"] = {
                    "status": "not_run",
                    "scope": "independent verification",
                    "reason": "No independent verifier is defined for this experiment runner.",
                    "logs_checked": 0,
                }
            base.update({"status": _completed_run_status(experiment_id, base["evidence_verification"]),
                         "finished_at": datetime.now(timezone.utc).isoformat(),
                         "experiment_completion": "completed", "exit_code": completed.returncode})
        job.update(base)
    except subprocess.TimeoutExpired as error:
        base.update({"status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(),
                     "experiment_completion": "completed" if base.get("runner_exit_code") == 0 else "failed",
                     "error": f"Timed out after {spec['timeout']} seconds", "exit_code": None})
        job.update(base)
    except Exception as error:  # surfaced in the local run record for researcher review
        base.update({"status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(),
                     "experiment_completion": "completed" if base.get("runner_exit_code") == 0 else "failed",
                     "error": str(error), "exit_code": base.get("runner_exit_code")})
        job.update(base)
    (run_dir / "manifest.json").write_text(json.dumps(job, indent=2, sort_keys=True) + "\n")


def start_experiment(experiment_id: str) -> dict[str, Any]:
    if experiment_id == "stage2" or experiment_id.startswith("stage2-"):
        raise PermissionError("Canonical Stage 2 execution is disabled in the local Mac workbench")
    if experiment_id not in RUNNERS:
        raise ValueError("Unknown experiment runner")
    provenance = source_provenance()
    with JOB_LOCK:
        if any(job.get("status") == "running" for job in JOBS.values()):
            raise RuntimeError("Another local experiment is already running")
        run_id = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        JOBS[run_id] = {"run_id": run_id, "experiment_id": experiment_id,
                        "execution_target": "mac-local-safe",
                        "title": RUNNERS[experiment_id]["label"], "status": "queued",
                        "experiment_completion": "queued", "source_provenance": provenance,
                        "evidence_verification": {"status": "not_run", "logs_checked": 0}}
    threading.Thread(target=_run_experiment, args=(run_id, experiment_id), daemon=True).start()
    return dict(JOBS[run_id])


class Handler(BaseHTTPRequestHandler):
    server_version = "FitrahWorkbench/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, value: Any, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.hostname in {"127.0.0.1", "localhost", "[::1]"} and parsed.port in {None, PORT}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            self._json(dashboard_data())
            return
        if path.startswith("/api/runs/"):
            run_id = path.rsplit("/", 1)[-1]
            job = JOBS.get(run_id)
            if job is None:
                manifest = RUN_ROOT / run_id / "manifest.json"
                try:
                    job = json.loads(manifest.read_text())
                except (OSError, json.JSONDecodeError):
                    self._json({"error": "Run not found"}, 404)
                    return
            self._json(job)
            return
        if path == "/" or path in {"/index.html", "/app.js", "/style.css"}:
            file = ROOT / "src/ui" / path.lstrip("/") if path != "/" else ROOT / "src/ui/index.html"
            if not file.is_file():
                self.send_error(404)
                return
            content_type = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                            ".css": "text/css; charset=utf-8"}.get(file.suffix, "application/octet-stream")
            data = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if not self._same_origin():
            self._json({"error": "Cross-origin requests are not allowed"}, 403)
            return
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._json({"error": "The workbench API is loopback-only"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            route = urlparse(self.path).path
            if route == "/api/run":
                result = start_experiment(str(payload.get("experiment", "")))
            elif route == "/api/verify":
                result = verify_log(str(payload.get("evidence", "")))
            else:
                self._json({"error": "Not found"}, 404)
                return
            self._json(result, 202 if route == "/api/run" else 200)
        except PermissionError as error:
            self._json({"error": str(error)}, 403)
        except ValueError as error:
            self._json({"error": str(error)}, 400)
        except RuntimeError as error:
            self._json({"error": str(error)}, 409)
        except (json.JSONDecodeError, OSError, subprocess.SubprocessError) as error:
            self._json({"error": str(error)}, 500)


def main() -> None:
    if not ROOT.is_dir() or not (ROOT / "experiments/lab0/experiment-spec.md").is_file():
        raise SystemExit("Run this from a complete Fitrah repository checkout")
    if HOST not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The workbench server must bind to loopback")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"Fitrah Research Workbench: http://{HOST}:{PORT}")
    print(f"Repository: {ROOT}")
    print("Stage 2 execution is disabled here; historical artifacts remain viewable.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWorkbench stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

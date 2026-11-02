"""Portable cloud automation regressions; no Stage 2 execution."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "run_stage1_ci", Path(__file__).resolve().parents[1] / "scripts/run_stage1_ci.py")
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


@pytest.fixture(scope="module")
def successful_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("cloud") / "artifacts"
    assert ci.run(output) == 0
    return output, json.loads((output / "manifest.json").read_text())


def test_real_stage1_preserves_provenance_and_all_controls(successful_run):
    output, manifest = successful_run
    assert manifest["status"] == "succeeded"
    assert manifest["experiment_completion"] == "completed"
    assert manifest["research_status"] == "pending_human_review"
    assert manifest["verification"]["logs_checked"] == 6
    assert manifest["verification"]["status"] == "passed"
    rows = manifest["verification"]["logs"]
    assert [r["exit_code"] for r in rows] == [1, 1, 1, 1, 0, 0]
    assert all(r["report"]["violations"] for r in rows[:4])
    assert all(not r["report"]["violations"] for r in rows[4:])
    assert manifest["source"]["identity_source"] == "git_worktree"
    assert len(manifest["source"]["source_commit"]) == 40
    assert manifest["environment"]["python"]
    assert not any("stage2" in row["path"] for row in manifest["execution_inputs"])
    for row in manifest["artifact_files"]:
        assert ci.server.sha256(output / row["path"]) == row["sha256"]
    historical = ci.ROOT / "experiments/lab0/logs/stage1-C-rep1.jsonl"
    assert historical.read_bytes() == (output / "execution/experiments/lab0/logs" / historical.name).read_bytes()


def test_refuses_stale_output(successful_run):
    with pytest.raises(FileExistsError):
        ci.run(successful_run[0])


def test_timeout_keeps_partial_output_and_no_success_exit(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise ci.subprocess.TimeoutExpired(args[0], 1, output=b"partial evidence", stderr=b"diagnostic")

    monkeypatch.setattr(ci.subprocess, "run", timeout)
    result = ci.execute(["python", "runner.py"], tmp_path, {}, tmp_path / "runner", 1)
    assert result["exit_code"] is None
    assert "Timeout" in result["error"]
    assert (tmp_path / "runner.stdout.txt").read_bytes() == b"partial evidence"
    assert (tmp_path / "runner.stderr.txt").read_bytes() == b"diagnostic"


def test_completed_runner_does_not_mask_verification_failure(tmp_path, monkeypatch):
    execute = ci.execute

    def tampered_output(command, cwd, env, prefix, timeout):
        result = execute(command, cwd, env, prefix, timeout)
        if command[1] == "src/simulator/run.py":
            log = cwd / "experiments/lab0/logs/stage1-C-rep1.jsonl"
            lines = log.read_text().splitlines()
            row = json.loads(lines[0])
            row["sig"] = "00" * 64
            lines[0] = json.dumps(row)
            log.write_text("\n".join(lines) + "\n")
        return result

    monkeypatch.setattr(ci, "execute", tampered_output)
    output = tmp_path / "verification-failed"
    assert ci.run(output) == 1
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["experiment_completion"] == "completed"
    assert manifest["verification"]["status"] == "failed"
    assert manifest["status"] == "failed"
    assert manifest["research_status"] == "not_eligible_for_acceptance"
    assert manifest["verification"]["logs_checked"] == 6
    assert manifest["verification"]["logs"][4]["report"]["integrity_failures"]
    assert (output / "stage1-C-rep1.stdout.txt").is_file()
    assert (output / "stage1-C-rep1.stderr.txt").is_file()


def test_failed_runner_still_verifies_and_preserves_partial_evidence(tmp_path, monkeypatch):
    execute = ci.execute

    def failed_runner(command, cwd, env, prefix, timeout):
        if command[1] == "src/simulator/run.py":
            # A real child process exits 7 after generating then truncating its
            # disposable evidence set. No canonical file or result is modified.
            command = [ci.sys.executable, "-c", """
import runpy
from pathlib import Path
try:
    runpy.run_path('src/simulator/run.py', run_name='__main__')
except SystemExit as error:
    if error.code:
        raise
Path('experiments/lab0/logs/stage1-C-rep2.jsonl').unlink()
print('CONTROLLED TEST FIXTURE: partial evidence and exit 7', flush=True)
raise SystemExit(7)
"""]
        return execute(command, cwd, env, prefix, timeout)

    monkeypatch.setattr(ci, "execute", failed_runner)
    output = tmp_path / "failed"
    assert ci.run(output) == 1
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["runner"]["exit_code"] == 7
    assert manifest["experiment_completion"] == "failed"
    assert manifest["verification"]["status"] == "failed"
    assert manifest["verification"]["missing_logs"] == ["stage1-C-rep2"]
    assert manifest["verification"]["logs_checked"] == 5
    assert manifest["research_status"] == "not_eligible_for_acceptance"
    assert (output / "stage1-A-rep1.stdout.txt").is_file()
    assert "CONTROLLED TEST FIXTURE" in (output / "runner.stdout.txt").read_text()
    assert (output / "runner.stderr.txt").is_file()


def test_tampered_evidence_fails_independent_verification(successful_run, tmp_path):
    import shutil
    source = tmp_path / "source"
    shutil.copytree(successful_run[0] / "execution", source)
    log = source / "experiments/lab0/logs/stage1-C-rep1.jsonl"
    lines = log.read_text().splitlines()
    row = json.loads(lines[0])
    row["sig"] = "00" * 64
    lines[0] = json.dumps(row)
    log.write_text("\n".join(lines) + "\n")
    report = ci.verify_logs(source, tmp_path, dict(ci.os.environ, PYTHONPATH=str(source / "src")))
    assert report["status"] == "failed"
    assert report["logs_checked"] == 6
    assert report["logs"][4]["report"]["integrity_failures"]


@pytest.mark.parametrize("damage", ["missing_ok", "inconsistent_ok", "error"])
def test_incomplete_or_inconsistent_reports_fail_closed(successful_run, tmp_path, monkeypatch, damage):
    execute = ci.execute

    def altered_report(*args):
        result = execute(*args)
        path = args[3].with_suffix(".stdout.txt")
        report = json.loads(path.read_text())
        if damage == "missing_ok":
            report.pop("ok")
        elif damage == "inconsistent_ok":
            report["ok"] = not report["ok"]
        else:
            report["error"] = "controlled incomplete verification"
        path.write_text(json.dumps(report))
        return result

    monkeypatch.setattr(ci, "execute", altered_report)
    source = successful_run[0] / "execution"
    report = ci.verify_logs(source, tmp_path, dict(ci.os.environ, PYTHONPATH=str(source / "src")))
    assert report["status"] == "failed"
    assert all(not row["valid"] for row in report["logs"])


@pytest.mark.parametrize("mode", ["passed", "test_failure", "verification_failure", "missing_manifest"])
def test_workflow_summary_exposes_provenance_and_failure(tmp_path, capsys, mode):
    import hashlib
    summary_spec = importlib.util.spec_from_file_location(
        "summarize_stage1_ci", ci.ROOT / "scripts/summarize_stage1_ci.py")
    summary = importlib.util.module_from_spec(summary_spec)
    summary_spec.loader.exec_module(summary)
    manifest = {"source": {"source_commit": "a" * 40, "source_ref": "review-branch",
                           "worktree_state": "clean"},
                "status": "succeeded", "experiment_completion": "completed", "stage1_pass": True,
                "verification": {"status": "passed", "logs_checked": 6}}
    if mode == "verification_failure":
        manifest["verification"]["status"] = "failed"
    if mode != "missing_manifest":
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "stage1-tests.xml").write_text('<testsuites tests="1"/>')
    tests = "failure" if mode == "test_failure" else "success"
    status = summary.summarize(tmp_path, tests)
    rendered = capsys.readouterr().out
    if mode == "passed":
        assert status["automation_status"] == "passed"
        assert status["research_status"] == "pending_human_review"
    else:
        assert status["automation_status"] == "failed_or_incomplete"
        assert status["research_status"] == "not_eligible_for_acceptance"
    assert "source_commit" in rendered and "independent_verification" in rendered
    assert "research_status" in rendered and "experiment_completion" in rendered
    if mode != "missing_manifest":
        assert "a" * 40 in rendered
    for row in json.loads((tmp_path / "bundle-hashes.json").read_text()):
        assert hashlib.sha256((tmp_path / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_workflow_pins_actions_and_preserves_failure_uploads():
    import re
    workflow = (ci.ROOT / ".github/workflows/stage1.yml").read_text()
    actions = re.findall(r"uses: ([^\s]+)", workflow)
    assert len(actions) == 4
    assert all(re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", action) for action in actions)
    assert "workflow_dispatch:" in workflow
    assert "runs-on: ubuntu-24.04" in workflow
    for step in workflow.split("      - name:")[1:]:
        if "uses: actions/upload-artifact@" in step:
            assert "if: always()" in step
            assert "if-no-files-found: error" in step
    assert "stage1-regression-diagnostics" in workflow
    assert "continue-on-error" not in workflow


@pytest.mark.parametrize("damage", ["missing", "extra", "malformed"])
def test_evidence_set_and_report_fail_closed(successful_run, tmp_path, monkeypatch, damage):
    import shutil
    source = tmp_path / "source"
    shutil.copytree(successful_run[0] / "execution", source)
    logs = source / "experiments/lab0/logs"
    if damage == "missing":
        (logs / "stage1-A-rep1.jsonl").unlink()
    elif damage == "extra":
        (logs / "extra.jsonl").write_text("")
    else:
        execute = ci.execute

        def malformed(*args):
            result = execute(*args)
            args[3].with_suffix(".stdout.txt").write_text("not json")
            return result

        monkeypatch.setattr(ci, "execute", malformed)
    report = ci.verify_logs(source, tmp_path, dict(ci.os.environ, PYTHONPATH=str(source / "src")))
    assert report["status"] == "failed"

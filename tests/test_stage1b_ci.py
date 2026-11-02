"""Cloud Stage 1B contracts, failure retention and independent evidence checks."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_stage1b_ci as ci
import verify_stage1b_ci as verifier
from stage1b import run as canonical
from stage1b.gen import GENESIS, replay


@pytest.fixture
def historical():
    return json.loads((ROOT / "experiments/lab0/results/stage1b.json").read_text())


def test_full_contract_preserves_canonical_parameters(historical):
    assert verifier.FULL == canonical.FULL == historical["parameters"]
    assert verifier.QUICK == canonical.QUICK
    assert verifier.FULL["depths"] == [10, 50, 100]
    assert verifier.FULL["e2_histories"] * verifier.FULL["e2_length"] == 100000
    verifier.check_result(historical, "full")
    with pytest.raises(ValueError, match="Parameters"):
        verifier.check_result(historical, "quick")


@pytest.mark.parametrize("section", verifier.SECTIONS)
def test_missing_section_fails(historical, section):
    historical.pop(section)
    with pytest.raises(ValueError, match="Missing section"):
        verifier.check_result(historical, "full")


@pytest.mark.parametrize("damage", ["truncated", "counterexample", "history_count", "missing_defect", "missed_fault", "reduced_full"])
def test_incomplete_or_unexpected_results_fail(historical, damage):
    if damage == "truncated":
        historical[verifier.SECTIONS[5]]["truncated"] = True
    elif damage == "counterexample":
        historical[verifier.SECTIONS[2]]["counterexamples"] = [{"seed": 1}]
    elif damage == "history_count":
        historical[verifier.SECTIONS[2]]["histories"] -= 1
    elif damage == "missing_defect":
        historical[verifier.SECTIONS[3]]["rows"].pop()
    elif damage == "missed_fault":
        row = historical[verifier.SECTIONS[3]]["rows"][0]
        row["detected"] -= 1
        row["detection_rate"] = f"{row['detected']}/{row['violating_transitions']}"
    else:
        historical["parameters"] = verifier.QUICK
    with pytest.raises(ValueError):
        verifier.check_result(historical, "full")


def test_tc26_gap_is_explicit_not_silently_disabled(historical):
    row = next(r for r in historical[verifier.SECTIONS[3]]["rows"] if r["defect"] == "D10c")
    assert 0 < row["detected"] < row["violating_transitions"]
    verifier.check_result(historical, "full")
    row["detected"] = row["violating_transitions"] + 1
    with pytest.raises(ValueError):
        verifier.check_result(historical, "full")


@pytest.fixture
def signed_case(tmp_path):
    output = tmp_path / "evidence"
    output.mkdir()
    ci.snapshot(output / "execution")
    folder = output / "cases/000001"
    folder.mkdir(parents=True)
    history = [["a0", json.dumps({"op": "invoke", "action": "read", "resource": "vault"})]]
    result = replay(history, log_path=folder / "log.jsonl", run_id="case")
    meta = {"kind": "direct", "phase": "experiment2_generated_histories", "genesis": GENESIS,
            "config": "C", "defect": None, "history": history, "run_id": "case"}
    (folder / "input.json").write_text(json.dumps(meta))
    (folder / "trace.json").write_text(json.dumps(result))
    reindex(output)
    return output


def reindex(output):
    folder = output / "cases/000001"
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
    (output / "cases.jsonl").write_text(json.dumps({"case": "000001", "sha256": hashes}) + "\n")


def test_independent_signed_case_passes_but_incomplete_run_does_not(signed_case):
    report = verifier.validate(signed_case, "quick")
    assert report["cases"][0]["valid"] is True
    assert report["status"] == "failed"
    assert any("Result" in e for e in report["errors"])
    assert (signed_case / "verifier-reports/000001.json").is_file()


@pytest.mark.parametrize("damage", ["log", "forged_checksum", "trace", "history", "missing", "unindexed"])
def test_tampered_or_incomplete_evidence_is_rejected(signed_case, damage):
    folder = signed_case / "cases/000001"
    if damage in ("log", "forged_checksum"):
        log = folder / "log.jsonl"
        entries = log.read_text().splitlines()
        entry = json.loads(entries[1])
        entry["sig"] = "00" * 64
        entries[1] = json.dumps(entry)
        log.write_text("\n".join(entries) + "\n")
        if damage == "forged_checksum":
            reindex(signed_case)
    elif damage == "trace":
        path = folder / "trace.json"
        trace = json.loads(path.read_text())
        trace["steps"][0]["decision"] = "block"
        path.write_text(json.dumps(trace))
        reindex(signed_case)
    elif damage == "history":
        path = folder / "input.json"
        meta = json.loads(path.read_text())
        meta["history"][0][1] = json.dumps({"op": "kill"})
        path.write_text(json.dumps(meta))
        reindex(signed_case)
    elif damage == "missing":
        (folder / "log.jsonl").unlink()
    else:
        (signed_case / "cases/000002").mkdir()
    report = verifier.validate(signed_case, "quick")
    assert report["status"] == "failed"
    if damage != "unindexed":
        assert report["cases"][0]["valid"] is False
    assert (signed_case / "verification.json").is_file()


def test_real_subprocess_failure_preserves_diagnostics(tmp_path, monkeypatch):
    execute = ci.execute

    def fail_worker(command, cwd, env, prefix, timeout):
        if "stage1b_ci_worker.py" in command[1]:
            command = [sys.executable, "-c", "import sys; print('controlled worker failure'); sys.exit(7)"]
        return execute(command, cwd, env, prefix, timeout)

    monkeypatch.setattr(ci, "execute", fail_worker)
    output = tmp_path / "failure"
    assert ci.run(output, "quick") == 1
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["runner"]["exit_code"] == 7
    assert manifest["validator"]["exit_code"] == 1
    assert manifest["experiment_completion"] == "failed"
    assert manifest["research_status"] == "not_eligible_for_acceptance"
    assert "controlled worker failure" in (output / "runner.stdout.txt").read_text()
    assert (output / "runner.stderr.txt").exists()
    assert (output / "validator.stdout.txt").exists()
    assert (output / "verification.json").exists()
    with pytest.raises(FileExistsError):
        ci.run(output, "quick")


def test_capture_observer_preserves_original_semantics(tmp_path):
    # A small unit fixture compares original and observed functions; it is not
    # a reduced production full mode or a claimed canonical reproduction.
    output = tmp_path / "observed"
    output.mkdir()
    script = """
import json,sys
from pathlib import Path
sys.path.insert(0, 'scripts')
import stage1b_ci_worker as w
out=Path(sys.argv[1])
before=w.run.experiment1([3],out)
def unit_main():
    after=w.run.experiment1([3],out)
    assert before==after
    return 0
w.run.main=unit_main
assert w.observe(out,'full')==0
print('observer equivalence passed')
"""
    result = subprocess.run([sys.executable, "-c", script, str(output)], cwd=ROOT,
                            env=dict(os.environ, PYTHONPATH="src"), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "observer equivalence passed" in result.stdout
    assert len((output / "cases.jsonl").read_text().splitlines()) == 2


@pytest.mark.parametrize("mode,tests,verification", [("quick", "success", "passed"), ("full", "success", "passed"),
                                                   ("quick", "failure", "passed"), ("quick", "success", "failed")])
def test_summary_never_equates_quick_with_full(tmp_path, capsys, mode, tests, verification):
    manifest = {"mode": mode, "scope": "quick_smoke_only" if mode == "quick" else "canonical_full_reproduction",
                "status": "succeeded", "experiment_completion": "completed", "verification": {"status": verification},
                "research_status": "pending_smoke_review" if mode == "quick" else "pending_human_review",
                "source": {"source_commit": "a" * 40, "worktree_state": "clean"}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    expected = 0 if tests == "success" and verification == "passed" else 1
    assert ci.summarize(tmp_path, tests) == expected
    rendered = capsys.readouterr().out
    assert manifest["scope"] in rendered and "a" * 40 in rendered
    status = json.loads((tmp_path / "workflow-status.json").read_text())
    assert status["research_status"] == (manifest["research_status"] if expected == 0 else "not_eligible_for_acceptance")


def test_manual_workflow_is_fixed_minimal_and_always_uploads():
    text = (ROOT / ".github/workflows/stage1b.yml").read_text()
    assert "workflow_dispatch:" in text and "default: quick" in text
    assert "type: choice" in text and "          - full" in text
    assert "runs-on: ubuntu-24.04" in text and "contents: read" in text
    assert "timeout-minutes: 180" in text
    for action in re.findall(r"uses: (\S+)", text):
        assert re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", action)
    upload = text.split("      - name: Upload evidence")[1]
    assert "if: always()" in upload and "if-no-files-found: error" in upload
    assert "continue-on-error" not in text

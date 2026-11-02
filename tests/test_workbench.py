import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import os

from ui import server


class WorkbenchSafetyTests(unittest.TestCase):
    def test_dashboard_uses_historical_repository_records(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(server, "RUN_ROOT", Path(temp_dir) / "runs"):
            data = server.dashboard_data()
        self.assertEqual(data["repository"]["name"], "c0ldskin/fitrah")
        self.assertIsNotNone(data["experiments"]["stage1"])
        self.assertFalse(data["experiments"]["stage2_execution_enabled"])
        self.assertEqual(len(data["evidence"]["historical_logs"]), 6)
        artifact_paths = {item["path"] for item in data["evidence"]["historical_artifacts"]}
        self.assertIn("experiments/nonvm/results/e6-strong-broker-ablation.md", artifact_paths)
        self.assertIn("experiments/nonvm/e7-lineage-conservation.md", artifact_paths)
        self.assertTrue(data["novelty"]["open_questions"])
        self.assertTrue(data["novelty"]["evidence"])

    def test_stage2_runner_is_rejected(self):
        with self.assertRaises(PermissionError):
            server.start_experiment("stage2")
        with self.assertRaises(PermissionError):
            server.start_experiment("stage2-hostile")

    def test_unknown_runner_is_rejected(self):
        with self.assertRaises(ValueError):
            server.start_experiment("arbitrary-command")

    def test_evidence_id_is_allowlisted(self):
        with self.assertRaises(ValueError):
            server.verify_log("../../etc/passwd")

    def test_expected_baseline_violations_are_not_integrity_failures(self):
        findings = [
            {"scenario": scenario, "invariant": invariant}
            for (scenario, invariant), count in server.STAGE1_AB_EXPECTED_FINDINGS.items()
            for _ in range(count)
        ]
        report = {"entries": 67, "integrity_failures": [], "violations": findings}
        result = server._verification_outcome("stage1-A-rep1", report, 1)
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected_outcome"], "baseline_violations_detected")
        self.assertEqual(result["unexpected_violations"], [])
        self.assertEqual(result["missing_expected_violations"], [])

    def test_unexpected_negative_control_violation_is_reported_separately(self):
        findings = [
            {"scenario": scenario, "invariant": invariant}
            for (scenario, invariant), count in server.STAGE1_AB_EXPECTED_FINDINGS.items()
            for _ in range(count)
        ]
        unexpected = {"scenario": "S00", "invariant": "F1"}
        result = server._verification_outcome(
            "stage1-B-rep1", {"entries": 67, "integrity_failures": [],
                               "violations": findings + [unexpected]}, 1)
        self.assertFalse(result["valid"])
        self.assertEqual(result["expected_outcome"], "unexpected_baseline_findings")
        self.assertEqual(result["unexpected_violations"], [unexpected])
        self.assertEqual(result["missing_expected_violations"], [])

    def test_missing_negative_control_finding_fails_verification(self):
        findings = [
            {"scenario": scenario, "invariant": invariant}
            for (scenario, invariant), count in server.STAGE1_AB_EXPECTED_FINDINGS.items()
            for _ in range(count)
        ]
        findings.pop()
        result = server._verification_outcome(
            "stage1-A-rep2", {"entries": 67, "integrity_failures": [],
                               "violations": findings}, 1)
        self.assertFalse(result["valid"])
        self.assertTrue(result["missing_expected_violations"])

    def test_stage1_verification_requires_exact_six_log_ids(self):
        ids = list(server.STAGE1_EXPECTED_LOG_IDS)
        passing = [{"valid": True} for _ in ids]
        complete = server._stage1_verification_summary(passing, ids)
        self.assertTrue(complete["passed"])
        self.assertEqual(complete["missing_logs"], [])
        partial = server._stage1_verification_summary(passing[:-1], ids[:-1])
        self.assertFalse(partial["passed"])
        self.assertEqual(partial["missing_logs"], [ids[-1]])
        extra = server._stage1_verification_summary(passing + [{"valid": True}], ids + ["stage1-D-rep1"])
        self.assertFalse(extra["passed"])
        self.assertEqual(extra["unexpected_logs"], ["stage1-D-rep1"])

    def test_canonical_six_historical_logs_match_stage1_baseline(self):
        outcomes = [server.verify_log(log_id) for log_id in server.STAGE1_EXPECTED_LOG_IDS]
        self.assertEqual(len(outcomes), 6)
        self.assertTrue(all(item["verification_valid"] for item in outcomes))
        for item in outcomes:
            self.assertEqual(item["verification"]["entries"], server.STAGE1_EXPECTED_ENTRY_COUNT)
            log_id = item["evidence_id"]
            findings = item["verification"]["violations"]
            if "-rep" in log_id and ("stage1-A-" in log_id or "stage1-B-" in log_id):
                self.assertEqual(len(findings), sum(server.STAGE1_AB_EXPECTED_FINDINGS.values()))
            else:
                self.assertEqual(findings, [])

    def test_completed_stage1_with_failed_verification_is_not_success(self):
        self.assertEqual(
            server._completed_run_status("lab0-stage1", {"status": "failed"}),
            "verification_failed",
        )
        self.assertEqual(
            server._completed_run_status("stage1b-quick", {"status": "not_run"}),
            "completed_unverified",
        )

    def test_enforced_log_requires_clean_verifier_report(self):
        report = {"entries": 67, "integrity_failures": [], "violations": []}
        result = server._verification_outcome("stage1-C-rep1", report, 0)
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected_outcome"], "enforced_log_clean")

    def test_novelty_view_distinguishes_decisions_from_candidates(self):
        decisions = server._novelty_decisions()
        statuses = {item["id"]: item["status"] for item in decisions}
        self.assertEqual(statuses.get("TC-31"), "accepted")
        self.assertEqual(statuses.get("TC-33"), "candidate")

    def test_temporary_snapshot_requires_a_full_canonical_commit(self):
        with patch.object(server, "_git_source_state", return_value=None), \
             patch.dict(os.environ, {"FITRAH_SOURCE_COMMIT": "not-a-commit"}):
            with self.assertRaises(ValueError):
                server.source_provenance()

    def test_temporary_snapshot_records_commit_and_full_source_hashes(self):
        commit = "a" * 40
        with patch.object(server, "_git_source_state", return_value=None), \
             patch.dict(os.environ, {"FITRAH_SOURCE_COMMIT": commit, "FITRAH_SOURCE_REF": "codex/research"}):
            provenance = server.source_provenance()
        self.assertEqual(provenance["source_commit"], commit)
        self.assertEqual(provenance["source_ref"], "codex/research")
        self.assertEqual(provenance["worktree_state"], "unversioned_snapshot")
        self.assertEqual(provenance["identity_source"], "unverified_declared_commit")
        self.assertEqual(provenance["commit_identity_status"], "unverified_declared_commit")
        self.assertIn("not authenticated", provenance["commit_identity_method"])
        self.assertTrue(provenance["snapshot_files"])
        self.assertEqual(len(provenance["state_sha256"]), 64)

    def test_dashboard_labels_gitless_commit_as_unverified(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(server, "RUN_ROOT", Path(temp_dir) / "runs"), \
             patch.object(server, "git_value", return_value=None), \
             patch.dict(os.environ, {"FITRAH_SOURCE_COMMIT": "a" * 40}):
            data = server.dashboard_data()
        self.assertEqual(data["repository"]["identity_source"], "unverified_declared_commit")

    def test_temporary_input_manifest_hash_changes_with_local_modification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "experiment.py"
            source.write_text("print('original')\n")
            first = server._manifest_digest(server._input_file_manifest(root))
            source.write_text("print('modified')\n")
            second = server._manifest_digest(server._input_file_manifest(root))
        self.assertNotEqual(first, second)

    def test_experiment_cannot_run_without_commit_identity(self):
        with patch.object(server, "_git_source_state", return_value=None), \
             patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                server.start_experiment("lab0-stage1")

    def test_git_provenance_keeps_commit_and_modified_state(self):
        state = {"commit": "b" * 40, "ref": "codex/workbench", "worktree_state": "modified",
                 "status_porcelain_v1": " M src/simulator/run.py", "status_sha256": "c" * 64,
                 "unstaged_diff_sha256": "d" * 64, "staged_diff_sha256": "e" * 64,
                 "untracked_files": [{"path": "notes.txt", "sha256": "f" * 64, "size_bytes": 3}],
                 "state_sha256": "1" * 64, "identity_source": "git_worktree"}
        with patch.object(server, "_git_source_state", return_value=state), \
             patch.dict(os.environ, {}, clear=True):
            provenance = server.source_provenance()
        self.assertEqual(provenance["source_commit"], "b" * 40)
        self.assertEqual(provenance["worktree_state"], "modified")
        self.assertEqual(provenance["untracked_files"][0]["sha256"], "f" * 64)

    def test_invalid_evidence_is_a_failure_and_findings_remain_present(self):
        report = {"entries": 1, "integrity_failures": [{"seq": 1}], "violations": []}
        result = server._verification_outcome("stage1-C-rep1", report, 1)
        self.assertFalse(result["valid"])
        self.assertEqual(report["integrity_failures"], [{"seq": 1}])


if __name__ == "__main__":
    unittest.main()

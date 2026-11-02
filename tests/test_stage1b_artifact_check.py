"""Offline structural checks for the fixed archive checksum preflight."""
import datetime as dt
import importlib.util
import io
import json
import os
from unittest import mock
import pathlib
import tempfile
import unittest

P = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_stage1b_artifact.py"
spec = importlib.util.spec_from_file_location("archivecheck", P)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Stage1BArtifactTests(unittest.TestCase):
    def setUp(self):
        self.run = {
            "id": module.RUN_ID, "repository": {"id": module.REPO_ID},
            "head_sha": module.SOURCE_SHA, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "workflow_dispatch"
        }
        self.artifact = {
            "id": module.ARTIFACT_ID, "name": module.ARTIFACT_NAME,
            "size_in_bytes": module.SIZE_BYTES, "digest": "sha256:" + module.EXPECTED_SHA256,
            "expired": False, "expires_at": "2027-01-17T16:16:34Z",
            "workflow_run": {"id": module.RUN_ID, "head_sha": module.SOURCE_SHA,
                             "repository_id": module.REPO_ID}
        }
        self.now = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)

    def test_known_metadata(self):
        self.assertIn("2027-01-17", module.check_metadata(self.run, self.artifact, self.now))

    def test_fail_closed_bad_metadata(self):
        variations = [
            (self.run, {**self.artifact, "digest": "sha256:" + "0" * 64}),
            (self.run, {**self.artifact, "size_in_bytes": 3}),
            (self.run, {**self.artifact, "expired": True}),
            (self.run, {**self.artifact, "workflow_run": {"id": 1}}),
            ({**self.run, "conclusion": "failure"}, self.artifact),
            ({**self.run, "head_sha": "f" * 40}, self.artifact),
            ({**self.run, "repository": {"id": 9}}, self.artifact),
        ]
        for run, artifact in variations:
            with self.subTest(run=run, artifact=artifact):
                with self.assertRaises(ValueError):
                    module.check_metadata(run, artifact, self.now)

    def test_expired_by_wall_clock(self):
        with self.assertRaisesRegex(ValueError, "retention deadline"):
            module.check_metadata(self.run, self.artifact, dt.datetime(2027, 1, 18, tzinfo=dt.timezone.utc))

    def test_corrupt_zip_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "data.zip"
            path.write_bytes(b"not the artifact")
            with self.assertRaises(ValueError):
                module.check_zip(path)

    def test_bearer_credentials_never_accepted_for_other_api_endpoint(self):
        with self.assertRaises(ValueError):
            module.api_request("https://api.github.com/repos/c0ldskin/fitrah/actions/runs/2", "unreal")

    def test_redirect_allowlist_accepts_only_github_artifact_storage(self):
        good = "https://productionresultssa0.blob.core.windows.net/actions-results/obj?sig=SECRET"
        self.assertEqual(module.check_redirect_location(good), good)
        bad = [
            "https://127.0.0.1/file?sig=SECRET",
            "https://localhost/file?sig=SECRET",
            "https://evil.example/file?sig=SECRET",
            "https://productionresultssa0.blob.core.windows.net.evil.example/file",
            "http://productionresultssa0.blob.core.windows.net/file",
            "https://productionresultssa0.blob.core.windows.net:8443/file",
            "https://user@productionresultssa0.blob.core.windows.net/file",
            "https://productionresultssa0.blob.core.windows.net/file#fragment",
        ]
        for url in bad:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    module.check_redirect_location(url)

    def test_signed_url_never_in_diagnostics(self):
        from http.client import InvalidURL
        secret = "https://productionresultssa0.blob.core.windows.net/x?sig=TOP_SECRET"
        for exception in [InvalidURL(secret), ValueError(secret), RuntimeError(secret)]:
            message = module.safe_failure_message(exception)
            self.assertNotIn("TOP_SECRET", message)
            self.assertNotIn(secret, message)

    def test_redirect_download_has_no_bearer_and_rejects_other_hosts(self):
        import urllib.error
        good = "https://productionresultssa0.blob.core.windows.net/obj?sig=SECRET"
        for target, approved in [(good, True), ("https://127.0.0.1:9443/x", False)]:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                redirect = urllib.error.HTTPError("fixed-api", 302, "redirect",
                                                  {"Location": target}, None)
                response = io.BytesIO(b"synthetic archive")
                with mock.patch.object(module, "api_request", side_effect=redirect), \
                     mock.patch.object(module.urllib.request, "build_opener") as build:
                    build.return_value.open.return_value = response
                    destination = pathlib.Path(temp) / "archive.zip"
                    if approved:
                        module.download_zip("FAKE_BEARER", destination)
                        request = build.return_value.open.call_args.args[0]
                        self.assertIsNone(request.get_header("Authorization"))
                        build.assert_called_once_with(module.NoRedirect)
                        self.assertEqual(destination.read_bytes(), b"synthetic archive")
                    else:
                        with self.assertRaises(ValueError):
                            module.download_zip("FAKE_BEARER", destination)
                        build.assert_not_called()
                        self.assertFalse(destination.exists())

    def test_invalid_url_is_redacted_in_report_and_stderr(self):
        from http.client import InvalidURL
        with tempfile.TemporaryDirectory() as temp:
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake"}), \
                 mock.patch.object(module, "get_json", side_effect=InvalidURL("?sig=PRIVATE")), \
                 mock.patch("sys.argv", ["check", "--output", temp]), \
                 mock.patch("sys.stderr", stderr):
                self.assertEqual(module.main(), 1)
            report = (pathlib.Path(temp) / "checksum-report.json").read_text()
            self.assertNotIn("PRIVATE", report + stderr.getvalue())
            self.assertEqual(json.loads(report)["status"], "CHECKSUM_UNCONFIRMED")

    def test_preexisting_zip_preserved_on_pre_download_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            existing = root / "temporary-original-artifact.zip"
            existing.write_bytes(b"NEVER_REMOVE")
            with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake"}):
                with mock.patch.object(module, "get_json", side_effect=ValueError("metadata blocked")):
                    with mock.patch("sys.argv", ["check_stage1b_artifact.py", "--output", str(root)]):
                        self.assertEqual(module.main(), 1)
            self.assertEqual(existing.read_bytes(), b"NEVER_REMOVE")
            report = json.loads((root / "checksum-report.json").read_text())
            self.assertEqual(report["status"], "CHECKSUM_UNCONFIRMED")
            self.assertEqual(report["preservation"], "NOT_ARCHIVED")

    def test_owned_temporary_files_only_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            existing = root / "temporary-original-artifact.zip"
            existing.write_bytes(b"KEEP")
            created = []

            def bad_download(token, path):
                created.append(path)
                path.write_bytes(b"PARTIAL")
                raise RuntimeError("https://example.com/?sig=PRIVATE")

            with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake"}):
                with mock.patch.object(module, "get_json", side_effect=[self.run, self.artifact]):
                    with mock.patch.object(module, "download_zip", side_effect=bad_download):
                        with mock.patch("sys.argv", ["check_stage1b_artifact.py", "--output", str(root)]):
                            self.assertEqual(module.main(), 1)
            self.assertEqual(existing.read_bytes(), b"KEEP")
            self.assertTrue(created)
            self.assertFalse(created[0].exists())
            report = json.loads((root / "checksum-report.json").read_text())
            self.assertNotIn("PRIVATE", json.dumps(report))


if __name__ == "__main__":
    unittest.main()

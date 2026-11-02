#!/usr/bin/env python3
"""Checksum-only preservation preflight for one fixed Stage 1B GitHub artifact.

Never claims durable storage, independent replay or an independently verified copy.
Python stdlib only. No extraction and no execution of downloaded content.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "c0ldskin/fitrah"
REPO_ID = 1423541747
RUN_ID = 39284167068
ARTIFACT_ID = 12203401010
SOURCE_SHA = "d14c6a2eaf9827afe9ac946d45ec8717ac3cdff8"
ARTIFACT_NAME = f"stage1b-full-{SOURCE_SHA}-{RUN_ID}-1"
SIZE_BYTES = 137399588
EXPECTED_SHA256 = "bbee5df05313abb5c5df6be25c23d19a87c917defa534998c6bfda329c948a20"
MAX_DOWNLOAD = 200 * 1024 * 1024
API = f"https://api.github.com/repos/{REPOSITORY}"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_metadata(run, artifact, now=None):
    """Check fixed identifiers and GitHub's published ZIP digest before download."""
    now = now or dt.datetime.now(dt.timezone.utc)
    require(run.get("id") == RUN_ID, "Wrong workflow run")
    require(run.get("repository", {}).get("id") == REPO_ID, "Wrong repository ID")
    require(run.get("head_sha") == SOURCE_SHA and run.get("head_branch") == "main", "Wrong source")
    require(run.get("status") == "completed" and run.get("conclusion") == "success", "Run not successful")
    require(run.get("event") == "workflow_dispatch", "Run not manually dispatched")
    require(artifact.get("id") == ARTIFACT_ID and artifact.get("name") == ARTIFACT_NAME, "Wrong artifact")
    require(artifact.get("size_in_bytes") == SIZE_BYTES, "Wrong artifact size")
    require(artifact.get("digest") == "sha256:" + EXPECTED_SHA256, "Wrong or missing reported SHA-256")
    require(artifact.get("expired") is False, "Artifact expired")
    attached = artifact.get("workflow_run") or {}
    require(attached.get("id") == RUN_ID and attached.get("head_sha") == SOURCE_SHA, "Wrong run association")
    require(attached.get("repository_id") == REPO_ID, "Wrong artifact repository ID")
    require(ARTIFACT_NAME.endswith("-1"), "Unexpected run attempt")
    expiry = dt.datetime.fromisoformat(artifact["expires_at"].replace("Z", "+00:00"))
    require(expiry > now, "Artifact retention deadline passed")
    return expiry.isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def api_request(url, token):
    """Only exact fixed API paths are permitted to receive GitHub bearer tokens."""
    allow = {f"{API}/actions/runs/{RUN_ID}", f"{API}/actions/artifacts/{ARTIFACT_ID}",
             f"{API}/actions/artifacts/{ARTIFACT_ID}/zip"}
    require(url in allow, "Unapproved authenticated API endpoint")
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(urllib.request.Request(
        url, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28",
                      "User-Agent": "fitrah-artifact-check"}), timeout=60)


def get_json(url, token):
    with api_request(url, token) as response:
        data = response.read(1024 * 1024 + 1)
    require(len(data) <= 1024 * 1024, "Metadata response too large")
    return json.loads(data)


def copy_stream(response, path):
    total = 0
    sha = hashlib.sha256()
    with path.open("xb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            require(total <= MAX_DOWNLOAD, "Artifact exceeds download limit")
            sha.update(block)
            output.write(block)
    return total, sha.hexdigest()


def check_redirect_location(location):
    """Allow only the specific GitHub Actions artifact Azure Blob endpoint family.

    Fail closed if GitHub changes its storage hosts; review observed new host
    names before adding them. Never return/log the signed query.
    """
    parsed = urllib.parse.urlsplit(location)
    host = parsed.hostname or ""
    # Download endpoints observed for the GitHub Actions artifact service.
    allowed = re.fullmatch(r"productionresultssa[0-9]+\.blob\.core\.windows\.net", host)
    require(parsed.scheme == "https" and bool(allowed) and parsed.port in (None, 443)
            and not parsed.username and not parsed.password and not parsed.fragment
            and bool(parsed.path), "Unapproved artifact storage destination")
    return location


def safe_failure_message(error):
    """Never serialize exception text: arbitrary exceptions can contain signed URLs."""
    if isinstance(error, ValueError):
        return "Artifact identity, destination or checksum validation failed"
    if isinstance(error, (urllib.error.HTTPError, urllib.error.URLError)):
        return "Artifact API or transport failed"
    return "Artifact verification failed"


def download_zip(token, destination):
    # Do not forward any GitHub bearer token to the archive service redirect.
    url = f"{API}/actions/artifacts/{ARTIFACT_ID}/zip"
    try:
        response = api_request(url, token)
    except urllib.error.HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "Unexpected download API response")
        redirect = error.headers.get("Location", "")
    else:
        # A direct 200 response is allowed; it is still size-bounded.
        with response:
            return copy_stream(response, destination)
    check_redirect_location(redirect)
    request = urllib.request.Request(redirect, headers={"User-Agent": "fitrah-artifact-check"})
    opener = urllib.request.build_opener(NoRedirect)  # reject additional signed-URL redirects
    with opener.open(request, timeout=60) as response:
        return copy_stream(response, destination)


def check_zip(path):
    """Verify original bytes only; ZIP member inspection and research replay are separate work."""
    sha = hashlib.sha256()
    total = 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(block)
            require(total <= MAX_DOWNLOAD, "File too large")
            sha.update(block)
    require(total == SIZE_BYTES, "ZIP size does not match GitHub metadata")
    observed = sha.hexdigest()
    require(observed == EXPECTED_SHA256, "ZIP SHA-256 mismatch")
    return total, observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Report directory, not evidence storage")
    parser.add_argument("--local-zip", help="Already-downloaded original ZIP (no GitHub token required)")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    owned_tempdir = None
    report = {"status": "CHECKSUM_UNCONFIRMED", "preservation": "NOT_ARCHIVED",
              "research_verification": "NOT_PERFORMED", "run_id": RUN_ID,
              "artifact_id": ARTIFACT_ID, "source_commit": SOURCE_SHA,
              "expected_sha256": EXPECTED_SHA256, "reported_size": SIZE_BYTES}
    try:
        if args.local_zip:
            path = Path(args.local_zip)
            report["source"] = "user_provided_local_original_zip"
        else:
            token = os.environ.get("GITHUB_TOKEN")
            require(bool(token), "GITHUB_TOKEN required for GitHub API")
            run = get_json(f"{API}/actions/runs/{RUN_ID}", token)
            artifact = get_json(f"{API}/actions/artifacts/{ARTIFACT_ID}", token)
            report["expires_at"] = check_metadata(run, artifact)
            # New unpredictable directory owned by this invocation; never delete
            # any pre-existing file, even when metadata checks/downloads fail.
            owned_tempdir = Path(tempfile.mkdtemp(prefix="stage1b-owned-", dir=output))
            path = owned_tempdir / "original-artifact.zip"
            report["download_size"], report["download_sha256"] = download_zip(token, path)
            report["source"] = "github_actions_original_zip"
        size, sha = check_zip(path)
        report.update({"status": "COPY_HASH_VERIFIED", "observed_sha256": sha,
                       "observed_size": size,
                       "preservation": ("LOCAL_COPY_EXISTS_UNASSESSED" if args.local_zip else
                                        "HASH_VERIFIED_ON_EPHEMERAL_RUNNER_ONLY")})
        print("SHA-256 VERIFIED; no durable archive or research replay claimed.")
        return_code = 0
    except Exception as error:
        report["failure_type"] = "VALIDATION_OR_TRANSPORT_FAILURE"
        report["failure"] = safe_failure_message(error)
        print(f"CHECKSUM VERIFICATION FAILED: {report['failure']}", file=sys.stderr)
        return_code = 1
    finally:
        # Never accidentally upload a 137MB redundant artifact from this temporary workflow.
        if owned_tempdir is not None:
            shutil.rmtree(owned_tempdir)
        (output / "checksum-report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return return_code


if __name__ == "__main__":
    sys.exit(main())

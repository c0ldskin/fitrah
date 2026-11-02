# Stage 1B original artifact checksum preflight

**Status: hosted checksum preflight succeeded once; hash verified on an ephemeral runner only. This is not an evidence archive.**

The manually dispatched GitHub Actions workflow `.github/workflows/stage1b-artifact-check.yml` performs a **fixed, read-only** check on the historical full Stage 1B artifact. It uses GitHub's ephemeral runner, built-in job token with `actions: read`, and pinned upstream Actions. It does not contact Hetzner, create a storage service, create credentials, require Termius, replay the research workload or run Stage 2.

The verifier retrieves run and artifact metadata from fixed GitHub endpoints, requires the expected repository/run/source/artifact association, size, expiry, completion and GitHub-reported SHA-256, downloads the original ZIP to temporary runner disk, and computes SHA-256 over its untouched bytes. It does **not** extract or execute archive content. The downloaded ZIP is removed before the workflow ends; only a small checksum report is uploaded as a 90-day GitHub artifact. If the checksum or metadata differs, the step fails; unexpected failures are recorded where possible.

**Fixed target:** run `39284167068`, artifact `12203401010`, expected compressed bytes `137399588`, source `d14c6a2eaf9827afe9ac946d45ec8717ac3cdff8`, GitHub-reported archive SHA-256 `bbee5df05313abb5c5df6be25c23d19a87c917defa534998c6bfda329c948a20`, expires `2027-01-17T16:16:34Z`. These metadata values were checked using the connected GitHub account on 19 October 2026. Run [39298789113](https://github.com/c0ldskin/fitrah/actions/runs/39298789113) completed successfully on `main` commit `a7b8a5312ca27baedb6e1cd9e9c5a5edbf5fb436`. Its logs show all 11 offline tests passing and the verifier reporting `SHA-256 VERIFIED` after downloading and hashing the original ZIP. The small report artifact is [12209543721](https://github.com/c0ldskin/fitrah/actions/runs/39298789113/artifacts/12209543721) (507 bytes; GitHub artifact-service digest `sha256:5e4fe9c4e8c4f3bbc0d2f4ea7981d4342beb21bc07297328d3159441704f1ffb`). That digest is for the report artifact ZIP, not the original Stage 1B ZIP.

## What success does and does not mean

`COPY_HASH_VERIFIED` + `HASH_VERIFIED_ON_EPHEMERAL_RUNNER_ONLY` means GitHub's original artifact bytes matched its published digest on one temporary hosted worker. This is meaningful byte-integrity evidence, but the source is still the same GitHub artifact service. It is **not** a retained independent copy, long-term backup, independent scientific evidence review, ZIP member safety audit or successful restore.

Owner decision: **NO NEW INFRASTRUCTURE.** Therefore no AWS/S3, storage accounts, new VMs or server services are created. The hosted check establishes `COPY_HASH_VERIFIED` + `HASH_VERIFIED_ON_EPHEMERAL_RUNNER_ONLY`; the original ZIP was deleted with the temporary runner workspace and no durable independent copy or restore is established. Preservation status remains `NOT_ARCHIVED`. To preserve it, copy the 137 MB ZIP to **existing authorised storage** (existing Hetzner only after storage/backup and access review, or an already-owned device), then verify the stored bytes, provenance, retention and restore. Do not store the ZIP inside Git. See [Issue #12](https://github.com/c0ldskin/fitrah/issues/12).

## Existing hosted result

The workflow is merged on `main` and has run once. Review run [39298789113](https://github.com/c0ldskin/fitrah/actions/runs/39298789113) and its JSON-only report artifact [12209543721](https://github.com/c0ldskin/fitrah/actions/runs/39298789113/artifacts/12209543721). A repeat checksum run is unnecessary unless the fixed source metadata changes. The run used no server connection and did not create an archive.

## Review limitations

This first step intentionally does not build an evidence extraction verifier, create an independent replica, or install anything on Hetzner. A future preservation task must use a separate decision for destination, storage and transfer mechanism. It cannot call this preflight `ARCHIVED_VERIFIED`.

The download code permits only HTTPS `productionresultssa<number>.blob.core.windows.net` destinations on port 443 (explicit or implicit), without user information or fragments. Other hosts, ports and further redirects fail closed. A changed GitHub storage host requires review before extending this allowlist; offline fixtures do not establish which host a live request will return. The GitHub bearer token is never forwarded to storage. Exception text is never copied into diagnostics, because it can contain signed URLs. Cleanup removes only this invocation's private temporary directory, preserving pre-existing files.

Eleven offline tests passed in the hosted job. The same job exercised live GitHub metadata retrieval, artifact download and hashing of the full 137,399,588-byte ZIP. It did not retain those bytes beyond the ephemeral runner, copy them to approved storage, unpack or scientifically audit the evidence, or test a restore. This is byte-integrity confirmation, not durable preservation.

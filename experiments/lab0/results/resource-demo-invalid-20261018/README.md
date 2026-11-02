# Invalid experimental VM demo

Verified on retrieval: signed result and public-key fingerprint, preflight/probe digests, exact P01-P09 PASS, carrier0 before/after, unchanged source fingerprints, selected generation manifest/content hashes and independent DemoVerifier/SnapshotValidator replay. Canonical Stage 2 completion is not claimed.

The selected generation contains genesis, AUTHORISED_BIRTH (event reason AUTHORIZED_BIRTH), then STARTUP_FAILURE with cleanup confirmation and child marked dead. No read/write/kill workload request is recorded. The outer supervisor reports INVALID_RUN, worker stopped, removed cgroup, empty uid census and conservative commit UNCERTAIN. Exported committed state is inspectable; this does not imply automatic rollback or successful execution.

Helper journal observed over SSH: demo-3891 launch pid3893, then terminate killed0. Current agent uid listing was empty. The helper replies before its child finishes cgroup placement/uid drop, while the adapter immediately checks membership; this is a possible startup race, not a confirmed root cause. The stored failure only names CleanLaunchFailure and the supervisor discards nested exception details, so exact cause remains unresolved.

Preserve this attempt. Do not delete its marker or retry this store. No private signing key is included. As in TC-26, signatures authenticate runtime statements but do not establish truth against a consistently lying runtime.

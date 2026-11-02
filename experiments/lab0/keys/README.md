# Test keys: public on purpose

`test-signing.seed` and `test-signing.pub` are a **published test key pair**. They exist only so that anyone can rerun Stage 1 and get byte-identical, verifiable evidence logs.

- **This key protects nothing.** Anyone can sign with it, so a log signed with it proves only that it is consistent with the published inputs, not where it came from.
- **Never reuse it** for anything real.
- Stage 2 uses a separate key generated inside the VM (`stage2-signing`). Only its public half is published.

# Fitrah Bibliography

Verification status:
- `carried`: listed in Foundation Note 0.4; not re-verified in this repository yet
- `known`: established literature added here; citation details to be checked before any external publication
- `verified`: checked against the primary source, with date

## From Foundation Note 0.4

| # | Reference | Relevance | Status |
|---|---|---|---|
| 1 | TCG, DICE Attestation Architecture, v1.2, updated 29 Jan 2026 | Layered hardware-rooted identity | carried |
| 2 | TCG, Device Identifier Composition Engine (DICE) overview | Layered identity derivation | carried |
| 3 | SPIFFE specifications (identity, Workload API, trust domain, federation) | Workload identity, federation | carried |
| 4 | seL4 Foundation, What is seL4? | Small verified substrate | carried |
| 5 | Necula, G. C., Proof-Carrying Code, POPL 1997, doi:10.1145/263699.263712 | Proof-carrying agents | carried |
| 6 | TCG, TPM 2.0 Library Specification (ISO/IEC 11889) | Roots of trust, measurement | carried |
| 7 | METR, Task-Completion Time Horizons of Frontier AI Models, updated 8 Sep 2026 | Capability trend | carried |
| 8 | UK AISI, Incident report: unsanctioned agent behaviour during cyber testing, 2026 | Observed unsanctioned actions | carried |
| 9 | Anthropic Alignment Science, Agentic Misalignment in Summer 2026 | Model alignment is not a boundary | carried |
| 10 | Anthropic Alignment Science, Towards training-time mitigations for alignment faking in RL, 16 Dec 2025 | Alignment faking | carried |
| 11 | UK AISI, Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors, 8 Jul 2026 | Population-level control | carried |
| 12 | NIST AI 800-5, Riggs et al., Summary analysis of RFI responses on AI agent security, 18 May 2026 | Agent security as a distinct problem | carried |
| 13 | UK AISI, Research Agenda, 2026 | Limits of current alignment and control | carried |
| 14 | Microsoft Open Source Blog, Agent Governance Toolkit, 2 Apr 2026 | Competing deterministic runtime policy | carried |
| 15 | Microsoft Learn, Entra security for AI overview, 2026 | Agents as non-human identities | carried |
| 16 | Google Cloud, What's new in IAM, 6 May 2026 | Agent identity and runtime defence | carried |
| 17 | TCG, DICE Attestation Architecture (duplicate of 1) | | carried |
| 18 | SPIFFE federation specification (overlaps 3) | | carried |
| 19 | IETF RFC 9334, RATS Architecture, Jan 2023 | Attester, verifier, relying party roles | carried |
| 20 | seL4 Foundation, seL4 Proofs | Proofs reaching the binary | carried |
| 21 | Tagliabue and Greco, Safe, Untrusted, Proof-Carrying AI Agents, arXiv:2510.09567, 2025 | Direct neighbour | carried |
| 22 | Subramanian and Sengupta, Crypto-bound identity-verified capability tokens for distributed AI agents, arXiv:2609.30824, 2026 | Direct neighbour, possibly closest prior art to Lab 0 | carried |
| 23 | Prakash, AIP: Agent Identity Protocol for Verifiable Delegation Across MCP and A2A, arXiv:2603.24775, 2026 | Verifiable delegation chains | carried |
| 24 | Otsuka, Toyoda and Leung, AI Identity: Standards, Gaps, and Research Directions, arXiv:2604.23280, 2026 | Gap survey | carried |
| 25 to 30 | Transaction foundation models and System 1 decision models (Thoughtworks, NVIDIA, Plaid, systemonemodels.org, Li arXiv:2610.02267) | Adjacent; not part of the trust substrate | carried |

Note: [1] and [17], and [3] and [18], duplicate each other. Proposed for consolidation in the next Note revision.

## Added in this repository: capability security and reference monitors

These are the oldest and closest prior art for Lab 0 and were missing from Note 0.4.

| # | Reference | Relevance | Status |
|---|---|---|---|
| 31 | Dennis, J. B. and Van Horn, E. C., Programming Semantics for Multiprogrammed Computations, CACM 9(3), 1966 | Origin of capabilities | known |
| 32 | Anderson, J. P., Computer Security Technology Planning Study, ESD-TR-73-51, 1972 | Reference monitor concept: always invoked, tamper-proof, small enough to verify. Lab 0's R is a reference monitor | known |
| 33 | Hardy, N., The Confused Deputy, ACM SIGOPS OSR 22(4), 1988 | Ambient authority failure; relevant to any R acting on behalf of agents | known |
| 34 | Shapiro, Smith and Farber, EROS: a fast capability system, SOSP 1999 | Capability OS with confinement | known |
| 35 | Miller, M. S., Robust Composition, PhD thesis, Johns Hopkins University, 2006 | Object capabilities, attenuation, confinement | known |
| 36 | Ellison et al., RFC 2693, SPKI Certificate Theory, 1999 | Delegation chains with monotonic restriction | known |
| 37 | Birgisson et al., Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud, NDSS 2014 | Holders can add caveats but not remove them; close to F1h plus F2 | known |
| 38 | Biscuit authorization token specification, biscuitsec.org | Authority block plus append-only attenuation blocks with Datalog checks; offline attenuation | known |
| 39 | UCAN specification, github.com/ucan-wg/spec | Delegation chains where each link can only attenuate | known |
| 40 | Watson et al., Capsicum: practical capabilities for UNIX, USENIX Security 2010 | Practical sandboxing for stage 2 design | known |
| 41 | Sha, L., Using Simplicity to Control Complexity, IEEE Software 18(4), 2001 (Simplex architecture) | Runtime assurance: complex controller, simple verified safety monitor (Note section 7) | known |


## Verified current agent-trust prior art, 18 October 2026

| # | Reference | Relevance | Status |
|---|---|---|---|
| 42 | Dantuluri, P. S. V. and Sundi, J., *Delegation Without Trust: An Empirical Gap Analysis of Identity, Authorization, and Runtime Governance in Multi-Agent LLM Systems*, arXiv:2609.00267, 2026 | Direct novelty threat: untrusted-model assumption, compromised-subagent confinement, external authorization broker, 2,000 randomized delegation scenarios | verified |
| 43 | Prakash, S., *Agent Identity Protocol (AIP): Verifiable Delegation for AI Agent Systems*, draft-prakash-aip-02, 10 Oct 2026 | Direct overlap: multi-hop delegated authority where no hop may widen what it received; identity/provenance/capability chain | verified; individual Internet-Draft, not IETF consensus |
| 44 | IETF WIMSE WG, *AI Identity Management System (AIMS)*, draft-ietf-wimse-aims-00, 15 Sep 2026 | Strong standards signal: compose established workload identity and OAuth rather than reinvent agent identity/authorization | verified; WG Internet-Draft |
| 45 | NIST NCCoE, *Software and AI Agent Identity and Authorization* project and concept paper, 5 Feb 2026; comment summary 29 Sep 2026 | Current government direction: identification, authorization, delegation, auditing and non-repudiation for software/AI agents | verified |
| 46 | Kadyrbek, N. and Mansurova, M., *Proof carrying agent actions enable verifiable licensing of language model tool use*, Scientific Reports, 13 Oct 2026 | Planner-independent action certificates checked before execution; relevant to proof-carrying execution evidence | verified, peer reviewed |
| 47 | SPIFFE / SPIRE specifications and workload attestation documentation | Mature workload identity and process-level attestation; candidate substrate rather than Fitrah novelty | verified |
| 48 | Trusted Computing Group, *DICE Attestation Architecture* v1.2, updated 29 Jan 2026 | Hardware-rooted measured identity and attestation; relevant to future instance binding and clone resistance | verified |
| 49 | Eclipse Biscuit authorization token documentation | Mature offline attenuation where a holder can restrict but not widen delegated authority | verified |

Interpretation: entries 42 to 49 strengthen the prior-art threat to any claim based only on external runtime policy, agent identity, multi-hop attenuation, workload attestation or proof-carrying action checks. Fitrah's candidate contribution must therefore be evaluated at the composition/lifecycle level, especially authorised birth, mandatory hereditary constitutional state, recursive lineage validity and later instance-bound execution.

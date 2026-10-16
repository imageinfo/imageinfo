# Security reporting

imageinfo has a bounded native RAW metadata reader and stored-preview extractor,
alongside requirements and research code. There are **no published executable
releases or supported software version ranges** yet. Security concerns about the
repository, future parser/write behavior, workflows or exposed sensitive material
are still relevant.

## Contact the project

GitHub private vulnerability reporting was **enabled and verified on 2026-10-16**
for this repository, under Terry's #0155 authorization. Use
[Report a vulnerability](https://github.com/imageinfo/imageinfo/security/advisories/new)
to send security details privately. The public advisories page exposes this route,
and authenticated and unauthenticated status checks return `enabled: true`.

Terry is the sole responder on a **best-effort** basis. There is no staffed team,
human backup, response deadline, fix guarantee or bounty. End-to-end external
submission and notification delivery remain **unverified**: the authorized harmless
API test was rejected because the available account administers this repository.
No test report was created, and an administrator-created draft was not substituted.

If you cannot use the private route, open a minimal
[contact request](https://github.com/imageinfo/imageinfo/issues/new) titled
“Private security contact requested.” Include only a way to continue safely if you
are comfortable sharing it publicly. **Do not include exploit details, credentials,
private photographs, sensitive metadata or reproduction attachments.** Wait for a
maintainer to establish a mutually agreed private channel before sending details.

Do not assume that posting an issue makes it private. The enabled route and its
remaining verification limits are distinct from a staffed or guaranteed service.

## What helps a private investigation

Once a private channel is confirmed, describe the affected commit/version, platform,
operation, expected/actual behavior, impact and a minimal reproducible case. State
whether the report concerns unsafe writes/data loss, untrusted-input handling,
privacy leakage, code execution or repository/release access. Keep original media
private unless there is a necessary, agreed and lawful way to share it.

Maintainers should acknowledge and triage privately, preserve evidence, identify
affected capabilities, coordinate a mitigation/fix and agree a disclosure update
with the reporter. A suspected compromised release or unsafe writer should be
quarantined from further publication while facts are established. Never ask a
reporter to publish an exploit merely to obtain a tracking issue.

The operational response and release/access recovery procedure is in
[the runbook](docs/governance/release-and-recovery.md), subject to the accepted solo
scope in [GOVERNANCE.md](GOVERNANCE.md). Shared responder coverage remains a future
goal. Only this repository's private-reporting switch was enabled; account access,
personal notification preferences and unrelated settings were not changed.

The [security-intake readiness proposal](docs/governance/security-intake-readiness.md)
records the actual enablement/readback, failed synthetic attempt and remaining
unverified delivery, separately from the historical two-responder proposal.

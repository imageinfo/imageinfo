# Security reporting

imageinfo has a bounded native RAW metadata reader and stored-preview extractor,
alongside requirements and research code. There are **no published executable
releases or supported software version ranges** yet. Security concerns about the
repository, future parser/write behavior, workflows or exposed sensitive material
are still relevant.

## Contact the project

As checked on **2026-10-15**, GitHub private vulnerability reporting is **disabled**
for this repository. No dedicated private security inbox has been established by
the current governance work. Do not assume that posting an issue makes it private.

Until a private route is published, open a minimal
[contact request](https://github.com/imageinfo/imageinfo/issues/new) titled
“Private security contact requested.” Include only a way to continue safely if you
are comfortable sharing it publicly. **Do not include exploit details, credentials,
private photographs, sensitive metadata or reproduction attachments.** Wait for a
maintainer to establish a mutually agreed private channel before sending details.

If the [security advisories page](https://github.com/imageinfo/imageinfo/security/advisories)
later shows **Report a vulnerability**, use that private reporting route instead.
The project must verify its intake and responder notifications before claiming the
route is staffed. This document is not a promise of a response deadline or a bounty.

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
[the runbook](docs/governance/release-and-recovery.md). Named primary/backup responders,
working private intake and response expectations remain explicit readiness actions
in [GOVERNANCE.md](GOVERNANCE.md). No repository settings were changed by this card.

The [security-intake readiness proposal](docs/governance/security-intake-readiness.md)
records the current setting observation and a future activation/test procedure.
It does not establish a staffed private reporting route.

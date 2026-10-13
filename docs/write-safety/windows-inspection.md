# Windows interrupted-transaction inspection

**#0036**, observed **2026-10-13**, implements read-only restart classification for
the actual [#0032 Windows marker worker](bound-windows-publication.md). Parsing and
classification are platform independent; file collection reuses the existing
Windows boundary. **No new OS API, encryption, receipt key or production
writer/profile is introduced.**

## Behavior

Inspection reads an explicitly selected root and five fixed leaves. It validates
typed record fields, checksums, phase sequences, current root identity, and actual
candidate/output identity, length, bytes, timestamps, attributes, owner policy,
streams and link count. Unknown/duplicate fields, arbitrary record target paths,
imported commit flags, inconsistent records, reparse/type changes, unexpected entries,
oversized input and incompatible multi-link artifacts refuse.

| Actual observation | Report |
| --- | --- |
| Root/candidate before any valid record | `unattributed-artifacts` |
| Matching candidate retained, output absent | `candidate-retained-output-absent` |
| Matching output plus observed intent | `matching-output-recovery-required` |
| Recorded candidate and output both absent | `candidate-missing-output-absent` |
| Current candidate/output differs from its record | `candidate-conflict` / `output-conflict` |
| Candidate and output both present | `candidate-and-output-conflict` |
| Matching output without intent | `output-without-intent` |
| Invalid/inaccessible/unexpected record or artifact | `uninspectable`, with a bounded reason |

Inspection never reports committed or permits repair/cleanup. Matching files and
records do not establish the missing Windows namespace/receipt persistence evidence.
Several independent opens are observations, not an atomic snapshot. Normal read/
access-time effects remain filesystem semantics; content, ACLs and modification
times are not set by inspection.

The qualifier also changes an output and updates every record to match its checksum
and timestamp. That pair yields a matching-record observation while repair/cleanup
permission remains false. A checksum and object comparison have that limited scope;
they do not require encryption or secret keys. WS-013/015 require integrity-checked
records, validated artifact ownership and safe behavior on uncertainty.

## Evidence and verification

[The 35-case ledger](windows-inspection-observations.json) covers 18 real worker
kills/cancellations, normal exit, ten invalid-record/namespace/multilink cases,
three missing/changed/self-consistent outputs and three refusal modes. All **35
inspection captures**, **32 unchanged before/after inventories** and **502 retained
artifact hashes** were audited.

Five portable tests cover exact wire behavior, untrusted paths/permission flags,
duplicates/checksums, 1,024-position malformed-input smoke and state classification.
They run on Windows, Ubuntu and macOS; unsupported filesystem adapters refuse.
Native observations use local NTFS, the ordinary current token and unchanged DOS
mapping. No account, privilege, service/security setting, source-media or OS-crash
change is made.

Root format/Clippy/**36 Windows tests**/release and research format/Clippy/five tests/
release passed. The original **78-case publication regression** passed. Python
syntax and public docs/link/JSON checks accompany
[source CI](windows-inspection-ci.json).

[The 27-package/30-notice graph](windows-inspection-dependencies.json) is unchanged
from #0032. Direct serde derive use adds an already admitted graph edge; no package
version, SDK feature, root dependency or production unsafe policy changes. The
[existing SDK review](../../experiments/0032-windows-publication/ffi-review.md) covers
the reused boundary. New inspection code uses safe Rust and ordinary typed serde.

## Remaining work

#0014/#0022 still require a supported complete storage operation, appropriate
source/property/path guards, operational output policy, qualified Windows persistence
and safely implemented finalization/cleanup. Current RAW write admissions remain
refused under #0027. This inspector does not enable #0023, automatic replay, rollback,
deletion or a production writer. Windows observations do not silently qualify other
filesystem/platform adapters; those can be added when their backend exists.

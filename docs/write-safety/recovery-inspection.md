# Publication and read-only recovery qualification

**#0028**, observed **2026-10-11**, first child of **#0022**. Terry's standing
authorization to split work preserves every parent acceptance criterion. This
increment delivers an actual [Rust research worker/inspector](../../experiments/0028-recovery-evidence/README.md)
and executable adversarial observations. **Zero production mutation profiles are
enabled.** #0022 remains open.

## What the evidence establishes

The Linux worker uses a held directory descriptor, no-symlink resolution,
exclusive artifact creation and conditional hard-link publication. Separate
prepared/intent files avoid truncating an old record during a phase update.
File and directory flush calls are made in order, followed by an observation
receipt. These are actual calls, not evidence of OS-crash/power-loss durability.

The inspector rereads bounded records and artifacts, checks directory/device/inode
identity, source/candidate contents, private-owner mode, and receipt consistency.
It uses no imported field as a capability or action permission. It reports current
observations only: **absence**, **candidate object**, **foreign/uninspectable target**,
or **invalid evidence**. All outcomes remain recovery-required; none authorizes
repair or establishes terminal committed/recovered-original status.

The checksum detects record corruption. An attacker who can rewrite a record can
recompute it; it is not a signature or authentication. Fixed names, strict members,
no-follow resolution and filesystem observations limit what can be read, but do
not prove a hostile same-user namespace safe. Device/inode matching is scoped to
retained objects and current observations, not permanent historical identity.

## Actual findings

| Test | Observation and consequence |
| --- | --- |
| Late stage edit after validation | An unrelated same-user write changed the named stage before link. Unwanted bytes became visible; the post-check failed. **This worker fails the strict publication gate.** #0029 must prevent this, not rely on later detection. |
| Parent swap before validation | The current path no longer named the bound directory; publication refused. |
| Parent swap after validation | Descriptor-relative publication stayed in the original directory, avoiding the foreign replacement directory. The installed name moved with its parent; final path binding was uncertain. Mandatory exclusion remains unproved. |
| Racing destination | The namespace operation refused rather than overwrite the unrelated winner. Inspection classified the foreign target and retained all artifacts. |
| Same bytes, different output object | Content equality alone did not attribute the target to the retained candidate. Device/inode comparison rejected that attribution. |
| Process kill before/after link | Output was absent before link and complete after link; receipts could be missing. Current absence or an old phase never proved publication had never occurred. |
| Corrupt/forged/missing records and artifacts | Inspection refused or reported uncertainty without repair. Recomputed checksums did not permit traversal, extra authorization fields, fabricated committed phase or a forged terminal receipt. |
| FIFOs, symlinks and inaccessible records | No-follow/nonblocking regular-file checks avoided following foreign paths or blocking on a pipe. Permissions were not cleared as a shortcut. |
| Actual child file-size limit | A 32 KiB `RLIMIT_FSIZE` stopped the 64 KiB write. A partial private artifact remained; no output was published. This is not a full-disk/device-I/O experiment. |
| Windows directory read handle | Rename was refused (error 32), but child-name creation remained possible. `sync_all` failed with error 5. This ordinary-handle sequence does not qualify namespace persistence. It does not prove that all NTFS strategies are impossible. |
| WSL mounted Windows path | The actual directory mode was 0777, failing the research private-directory policy. Worker refused before creating artifacts. It inherited no native-ext4 admission. |

## Coverage and captures

- **43 native Linux cases** ran on Ubuntu 26.04 under WSL2 kernel 6.18.33.2,
  native ext4 with the observed `data=ordered` configuration.
- Eight exact process-kill barriers and two cooperative cancellations ran against
  the actual worker, alongside namespace, input/stage, ownership/permission,
  record-integrity and resource-failure cases. These are not OS crashes.
- **Three Windows cases** ran on local fixed NTFS, Windows 11 build 26200:
  worker/inspector refusals and directory-handle qualification.
- **One mounted-Windows refusal** ran separately through WSL's observed `v9fs` mount.
- Eight admitted private #0021 CR3 candidates copied through the native WSL worker.
  Output/source/candidate bytes and lengths matched their exact input hashes;
  output and stage shared the observed object identity. Files had mode 0600 in
  caller-private 0700 directories. Received originals and input candidates stayed
  unchanged. There was no new metadata edit or sensor recompression.
- Repeated private inspections retained exact file contents, identities, UID,
  mode, size and modification times. Synthetic cases checked the same properties;
  the deliberately inaccessible case was independently rechecked after the test
  supervisor restored its permission. Normal access-time changes are not excluded.

The narrow initial R5 firmware/ISO/lens stratum and earlier candidate/pixel proof
are inherited only by exact bytes. No new RAW decoder, other variant, signature,
XMP/privacy or full SAF scenario was validated here. Private media, per-image hashes,
object identities, records, detailed captures and evidence archives remain excluded
from public Git and CI. Public CI uses authored marker data exclusively.

See [sanitized totals](recovery-summary.json) and
[scoped dependencies](recovery-dependencies.json). Native images/captures have
private provenance and exact tool/source identities. The Linux ELF was cross-built
from Windows with pinned Rust 1.99.0's musl target and bundled `rust-lld`; no WSL
compiler/system package installation or host privilege change was needed.

Eight scoped copy experiment records and eight derivative admissions/provenance
reviews validate against the existing evidence contracts. A 77-artifact registry
verifies referenced identities. The exact input's earlier reference read is
inherited; it is not a new reference storage mutation. Twenty-six research package
reviews and 29 notice-only reviews validate separately. Root production dependencies
and full writer/profile requirements remain unchanged.

[Actual CI evidence](recovery-ci.json) binds code revision
`d6e201cdd8cb6dc1bf767125c53bc0605576eb8b` to successful Windows x64, Ubuntu x64
and macOS arm64 jobs. All passed record tests/format/lints/release builds and the
production/candidate gates. Ubuntu exercised 43 worker/inspection cases; Windows
three qualification cases; macOS two explicit backend refusals. Expected failing
qualification/refusal cells are not converted into supported mutation profiles.

Records are capped at 64 KiB; regular input/artifact reads at 256 MiB. Private QA
used a 120-second host supervisor timeout. No OS hard memory cap, native interruptible
filesystem deadline or downstream-WSL termination guarantee is established.
The record contract uses explicit null/reason fields for unconfigured generic limits.

## Qualification ledger and next gates

| Cell | Disposition |
| --- | --- |
| Linux research read-only inspection | Exercised under the declared API, owner/mode and retained-object restrictions; observation only |
| Linux research marker/CR3-copy publication | Exercised; **unqualified** because late stage and path/property exclusion are missing |
| Windows/macOS research publication/inspection backend | Explicitly refused, no fallback; common record parsing is tested separately |
| Windows ordinary directory-handle flush | Actual call failed; complete backend/property/persistence proof pending |
| Mounted Windows private-directory admission | Refused for the measured mode; no profile inheritance |
| OS crash, power loss, hardware durability, authenticated recovery and automated repair | Not run / not implemented |
| Production metadata writer and supported mutation profiles | **Disabled / zero enabled** |

#0029 owns live source/stage/namespace guards, including preexisting writable
handles/mappings and aliases. Memory freezing cannot prove a concurrent source-file
read was coherent. #0030 owns reviewed Windows identities, private properties and
namespace acknowledgement. #0031 owns isolated crash/durability, guarded
finalization and identity-based cleanup. It must not crash this host or an existing
WSL distribution. #0022 retains its entire WS/SAF acceptance scope; GAP-004 and
GAP-009 stay open. #0023 still requires #0027's format/authenticity admission.

The experiment supplies neither a transaction framework nor accepted production
record format. Small ordinary records and OS calls establish observations; enabling
an unsafe worker by flipping `profileVerified` would not satisfy the contract.

## Primary-source observations

Viewed **2026-10-11**. Source facts inform the experiments; results above come from
actual imageinfo runs. No upstream implementation or fixtures were imported.

- [rustix 1.1.5 filesystem APIs](https://docs.rs/rustix/1.1.5/rustix/fs/index.html)
  and [openat2](https://docs.rs/rustix/1.1.5/rustix/fs/fn.openat2.html) provide safe
  descriptor-relative/no-symlink calls; the exact source archive is lock-bound.
- [SHA-2 0.11.0](https://docs.rs/sha2/0.11.0/sha2/) provides conventional hashing.
  Hashing bytes does not authenticate their author or grant file-operation authority.
- [Rust 1.99 Windows metadata extensions](https://doc.rust-lang.org/std/os/windows/fs/trait.MetadataExt.html)
  still mark by-handle ID access nightly-only; this prototype does not enable it.
- [Microsoft FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
  distinguishes required access rights and administrative volume flushing.
  [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
  informs the directory share-mode experiment. No elevated volume flush was attempted.
- The [existing platform constraints](platform-constraints.md) and
  [accepted candidate proof](new-output-preservation.md) retain source/format,
  preservation and qualification boundaries.

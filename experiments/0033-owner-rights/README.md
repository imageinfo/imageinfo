# Windows OWNER RIGHTS guard qualification

**#0033**, observed **2026-10-13**, standalone marker research under #0022/#0014.
No RAW input, production writer/profile, automated repair or permissions change to
an existing source. See [the findings](../../docs/write-safety/owner-rights.md) and
[the SDK/actor review](ffi-review.md).

```console
cargo fmt --manifest-path experiments/0033-owner-rights/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0033-owner-rights/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0033-owner-rights/Cargo.toml
cargo build --locked --release --manifest-path experiments/0033-owner-rights/Cargo.toml
python experiments/0033-owner-rights/qualify.py --binary PATH_TO_PROBE --parent OWNED_MARKER_SCRATCH
python experiments/0033-owner-rights/audit.py --root COMPLETE_RUN_ROOT --binary PATH_TO_PROBE --public SANITIZED_LEDGER
```

The worker accepts `MODE ABSOLUTE_NEW_FILE.marker`. Only bounded ordinary local DOS
paths are tested; UNC/device/verbatim, traversal, ADS target names, reserved names,
reparse ancestry and non-NTFS refuse. No existing marker is overwritten. Ancestors
are held against DELETE; publication creates an exclusive private `txn` root through
the same reviewed SDK helper used by #0032. The final `output.marker` is a conditional
held-source rename with file/directory flush calls, never a pathname-copy fallback.

Modes compare the existing `ordinary` descriptor, `fresh-restricted` property/security
deny, `minimal-restricted` creator access, and `fresh-sealed` property/security plus
new data/append deny. `publish-restricted`/`publish-sealed` test held composition.
`seal-after-open`, `retained-security` and `sealed-exit` qualify exposure/handle and
post-exit limits. `sealed-exit` uses the weaker property-only descriptor; the name
does not imply data immutability. `admit` always refuses the complete profile before
effects, naming existing-source, restart-custody and receipt-persistence gaps.

Reply `continue` at `created`, `guarded` and, for publication, `published`. LF and
CRLF are accepted; other/oversized controls stop. The line is capped at 32 bytes.
The supervisor has 30-second message/actor waits and a 90-second worker watchdog;
these are orchestration bounds, not hard native I/O/OS resource quotas. It kills
only its owned worker/actor. Unsupported platforms return a bounded diagnostic
before worker artifacts; their supervisor retains its own scratch directory.

Every result denies committed/publication authority. Exit 0 is a research observation,
not a metadata operation success. Exit 5 is a refusal/error/cancellation diagnostic.
No product CLI result compatibility is asserted. Existing-source guard, ordinary
editable output policy, authenticated recovery and Windows crash/power-loss cells
remain unsupported/unverified. Freshly sealed outputs stay read-only to ordinary
owner opens after exit; do not use this as an unreviewed product permission policy.

Actors run in independent same-user processes with ordinary token rights. They touch
only supplied owned marker names/streams; no privilege/token/owner/system changes.
Preopened time/DACL handles remain effective after a later seal, unlike new opens.
Markers/captures are retained, including intentionally inaccessible DACL cases;
the audit reports denied reads and never repairs their ACLs to obtain a hash.
Readable default/alternate streams, controls/events/source/binary bindings are
retained privately. No SID, object ID, machine path or raw log enters the public ledger.

The shared project-owned ABI boundary is reused by path; #0032's ordinary constructor
and requested access remain unchanged. Added explicit policy constructors/access/
owned-marker DACL helper have a separate review. The original 78-case publication
suite is rerun; root production unsafe policy and dependencies remain unchanged.
See [dependency admission](../../docs/write-safety/owner-rights-dependencies.json),
[#0032 notices](../0032-windows-publication/NOTICES.md) and retained root licenses.
No upstream implementation, camera fixture or executable release is imported/shipped.

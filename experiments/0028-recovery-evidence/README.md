# Recovery evidence qualification

**#0028**, first child of **#0022**, observed **2026-10-11**. This is independently
authored research outside production imageinfo. It tests actual filesystem states
and reads retained evidence; no metadata writer or mutation profile is enabled.

The main result is a **failed enablement gate**: a named stage can change between
validation and linking. Post-publication detection does not prevent unwanted bytes
from appearing. The experiment retains that counterexample rather than counting
a successful flush/link as a safe commit. Read the
[results and remaining gates](../../docs/write-safety/recovery-inspection.md).

## Reproduce public checks

Use pinned Rust 1.99.0 and this package's separate Cargo.lock:

```console
cargo fmt --manifest-path experiments/0028-recovery-evidence/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0028-recovery-evidence/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0028-recovery-evidence/Cargo.toml
cargo build --locked --release --manifest-path experiments/0028-recovery-evidence/Cargo.toml
```

On native Linux, run the owned synthetic suite with a disposable parent directory:

```console
python experiments/0028-recovery-evidence/qualify.py --binary experiments/0028-recovery-evidence/target/release/imageinfo-recovery-probe --parent PRIVATE_SCRATCH_PARENT
```

The script retains its own directories/report and kills only its own worker at
explicit barriers. It never crashes the host, a WSL distribution, or the OS. It
accepts no image paths; the separate private QA driver supplies admitted CR3 inputs.
Windows uses the `.exe` binary and runs unsupported-backend/directory-handle cases.
macOS runs the explicit backend refusals. These refusals create no artifacts.

## Research commands and constraints

```console
imageinfo-recovery-probe inspect PRIVATE_TRANSACTION_DIRECTORY
imageinfo-recovery-probe worker PRIVATE_TRANSACTION_DIRECTORY
imageinfo-recovery-probe worker PRIVATE_TRANSACTION_DIRECTORY --barriers
```

`worker` is deliberately unqualified experimental publication. It defaults to
authored marker bytes. An optional regular input file may be supplied **only under
separate private fixture admission**; reading into memory does not prove coherence
against a live competing writer. It creates separate frozen-input/candidate files,
immutable prepared/intent records and an observation receipt, all with conditional
new names. Partial/error artifacts remain; there is no automated cleanup.

Linux root resolution uses `openat2` with no symlinks, and child operations stay
relative to the held directory descriptor. The directory must belong to the
effective UID with mode 0700; artifact files must be regular, same-owner mode 0600.
This is a tested research policy, not a complete ACL/storage/security profile.
Kernels lacking the required API refuse; there is no weaker path-based fallback.

Records are strict, bounded JSON with a SHA-256 checksum of their exact body bytes.
The fixed leaf names prevent arbitrary path/stream/callback import. Device/inode,
size, hash, ownership and mode observations bind the current artifacts. SHA-256
is **integrity, not authentication**; imported phase/receipt fields cannot permit
an action. Identity reuse and same-user tampering remain qualification concerns.

`inspect` opens files only for reading. It reports observed absence, a current
candidate-object match, a foreign/uninspectable target, or invalid evidence. Every
result remains observation-only, recovery-required and unauthenticated, with an
empty `authorizedActions` list. It never returns terminal committed/recovered
state, retries, repairs, changes permissions, restores, or deletes. Normal read
access-time effects are outside the no-content/property-change assertion.

The inspector limits records to 64 KiB and artifact reads to 256 MiB; record
parse errors retain bounded diagnostic text. The worker caps regular inputs at
256 MiB. No OS memory cap, native I/O deadline, crash durability, authenticated
journal or mandatory source/stage exclusion is claimed.

`hold-directory` on Windows observes an ordinary read directory handle's rename
and flush behavior. It uses neither an elevated volume flush nor nightly file-ID
APIs and changes no host privileges. The result cannot qualify a Windows backend.

## Dependencies and promotion

Serde/Serde JSON retain the accepted versions. SHA-256 uses `sha2`; Linux-only
descriptor operations use safe `rustix` APIs because ordinary std path joins cannot
bind children to a held directory. Application-owned unsafe code remains forbidden.
See [notices](NOTICES.md) and the
[exact scoped admission](../../docs/write-safety/recovery-dependencies.json).
The production root dependency graph is unchanged. This admission covers research
compilation and notices, not vendored implementations or public executable releases.

**#0029** must prove live source/stage/namespace exclusion. **#0030** retains Windows
private properties and persistence. **#0031** retains isolated crash/durability and
guarded finalization/cleanup. #0022 and #0014 remain open; #0023/#0027 still gate a
production output workflow. Do not promote this worker by changing a success flag.

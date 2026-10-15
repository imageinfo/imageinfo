# Explicit fresh-name marker restore (#0108)

This finite native qualifier exercises the safe `restore.rs` mode in the existing
[#0032 research worker](../0032-windows-publication/src/restore.rs). See the
[protocol and limits](../../docs/write-safety/fresh-name-restore.md).

The fixture actually copies a held `OLD108` current marker into a distinct
retained original, then edits the current marker to `LATER108`. A private typed
caller captures the actual identities/properties and ends its synchronous setup
actor. Fresh guards and the explicit `restore-fresh` authorization precede copying
the retained original to the fixed fresh destination. No external #0094 context
or editable saved JSON can create this authority.

The qualifier uses the existing #0093 namespace/security/stream observer and
#0100's reviewed read-only share-delete reader, because a CRT file open cannot
observe the DELETE-capable held candidate. No new SDK, dependency or unsafe
boundary is introduced. Capture files, full security observations and all fresh
marker artifacts remain private under `.local`; no marker artifact is cleaned up.

From the repository root on Windows:

```powershell
cargo build --locked --release --manifest-path experiments/0032-windows-publication/Cargo.toml
python experiments/0108-fresh-name-restore/qualify.py --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --parent .local/fresh-restore --output .local/fresh-restore-summary.json
python experiments/0108-fresh-name-restore/audit.py --scratch .local/fresh-restore/restore108-ACTUAL --output .local/fresh-restore-audit.json
```

Use the actual fresh `restore108-*` directory created by that invocation. Every
output filename must be fresh. The qualifier binds exact source and executable
hashes before/after its run; the independent audit rereads every retained actual
artifact and compares it with completed-run observations. The qualifier drives
only newly owned fixture operations. The independent audit never invokes
restoration, cleanup, replay or a restart action.

The suite covers positive ordinary/CRLF authorization; stale/wrong/corrupt context
and same-byte substituted originals; noncanonical security; current-plan mismatch;
early/late foreign, same-byte and directory destinations; an actual native
no-replace collision after final validation; guarded byte/name attempts and
property/link actors; malformed authorization, cancellation, EOF and owned worker
termination at each declared barrier.

The final [qualification](qualification.json) on 2026-10-15 records 58 marker
cells, including 13 `restored-copy-observed` results and seven actual owned-worker
terminations, plus three admission refusals. The independent [audit](audit.json)
reread all retained actual artifacts without changing any marker. The run used
Windows 10.0.26200 on NTFS and binds 26 exact LF source files and the precise
release executable. Its SHA-256 is
`b621d1180e0b697061b914466fff1698d130fabfe73b8eb778f29756c7135ba7`.

Two earlier provisional runs remain private. The second correctly refused to
emit final evidence when the source manifest changed during its run; the complete
final run and audit use the subsequently frozen source and copied executable.

Successful observations remain `restored-copy-observed` with commitment,
production publication and profile flags false. This does not qualify occupied
name replacement/restoration, generic #0094 import, complete property backup,
durable caller authority, namespace persistence, RAW mutation or a production
storage profile. Non-Windows workers refuse the unverified backend before effects;
the native qualifier requires Windows and does not simulate success.

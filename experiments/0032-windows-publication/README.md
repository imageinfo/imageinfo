# Handle-bound Windows publication experiment

Card **#0032**, observed **2026-10-11**. Standalone research package; `publish=false`.
It creates authored 64 KiB marker data, not CR3s, and accepts no source media. No
production writer/profile or automated repair is enabled. Read the
[findings and unsupported cells](../../docs/write-safety/bound-windows-publication.md)
and [native boundary review](ffi-review.md) before considering reuse.

```powershell
cargo fmt --manifest-path experiments/0032-windows-publication/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0032-windows-publication/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0032-windows-publication/Cargo.toml
cargo build --locked --release --manifest-path experiments/0032-windows-publication/Cargo.toml
python experiments/0032-windows-publication/qualify.py --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --parent .local/bound-publication-qualification
```

On other platforms use the executable without `.exe`. The worker returns an explicit
unsupported diagnostic with no worker artifacts. No Windows SDK call or fallback runs.
The supervisor leaves its own empty scratch directory.

## Protocol and outcomes

The executable accepts **absolute new root** and one mode:

- `absolute`: explicit marker qualification with rename-by-handle into the guarded
  ordinary DOS parent path. Ancestor/parent handles share read/write, never delete;
  candidate/records share read only, with rename authority already in the candidate
  handle. No guard release or mutable source-path reopening.
- `rooted`: separately requested Win32 directory-relative comparison. The measured
  call refuses with error 87; no automatic change to absolute publication occurs.
- `admit`: strict complete-profile query. It reports unsupported/refused **before
  filesystem effects**, naming missing property/persistence/recovery cells. Imported
  profiles/booleans/records cannot grant permission.

Nine control barriers bound the actual root creation, candidate/namespace calls,
prepared/intent file+directory flush calls, final validation, publication, output
flush, directory flush attempt and observation-record flush. Reply `continue`, `fail`
or `cancel`; the control line is bounded to 32 bytes. The supervisor may kill only
its owned worker at a barrier, with 30-second message/actor waits and a 120-second
worker timer. These are host bounds, not an interruptible native I/O deadline/quota.

Exit 0 means the **research observation protocol** finished, including an explicitly
observed API refusal or `recovery-required`. It never means committed metadata work.
Errors/interruption use exit 5/nonzero and retained captures/barriers; no CLI product
exit-code compatibility is asserted. Every result denies production permission.

Records use a small body plus SHA-256, live identity/content observations and fixed
target names. All three record handles stay held through the operation; they are
not indefinitely immutable or authenticated after exit. `observation.record` always
says not committed, namespace not acknowledged and no recovery authority. Records
are not consumed to authorize retry/repair, and no cleanup or rollback is performed.

## Scope and provenance

The 75-case Windows suite uses ordinary fixed local NTFS and an unchanged DOS mapping.
It tests external content/namespace/property actors and failure/kill/cancel at each
barrier. All marker/capture files remain in ignored scratch storage, including files
whose marker-only ACLs/streams/attributes were deliberately changed. Junction targets
are separate owned marker folders; no media/network original is accessed.

Safe coordinator code uses std `File`, lexical ownership and the reviewed safe
`winapi-util` identity getter. Only `native.rs` overrides the research crate's unsafe
denial for the reviewed SDK operations; production root retains `unsafe_code=forbid`.
The supervisor's tiny ADS actor is separately reviewed in `ffi-review.md`.

All 27 registry archives and 30 retained notices match the earlier scoped research
reviews. New direct `windows-sys` feature use is explicitly reviewed; no new registry
package or production dependency changes. See [notices](NOTICES.md) and
[research admission](../../docs/write-safety/bound-publication-dependencies.json).
No dependency implementation, Windows DLL, personal data or assembled executable is
vendored or publicly distributed.

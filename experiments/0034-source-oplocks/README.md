# Existing-source Windows oplock qualification

Research for **#0034** under **#0014/#0022**, observed **2026-10-13**. This executable
does not publish media or enable a storage profile. See the
[measured cells](../../docs/write-safety/source-oplocks.md),
[dependency admission](../../docs/write-safety/source-oplock-dependencies.json) and
[SDK review](ffi-review.md).

The worker prepares exclusively created 64 KiB owned markers, then separately opens
the existing marker read/control only with read sharing and overlapped I/O. It
compares sharing alone with RH (`3`), RW (`5`) and RWH (`7`) requests. Ordinary held
ancestors refuse DELETE/reparse/non-NTFS paths. No existing marker ACL, timestamp,
attribute or content is changed by the holder; normal read/access-time effects are
separate. Independent actors deliberately change disposable marker properties.

`prepare`, `sharing`, `rh`, `rw`, `rwh` and `admit` take an explicit absolute local
DOS `.marker` path. `prepare` requires a new name. Other modes require the authored
bytes, exact current-user private policy, one link and only the default stream;
there is no arbitrary media mode. The path grammar rejects device/UNC/verbatim,
traversal, alternate-stream, reserved/trailing/unsafe names. `admit` refuses a
complete profile before effects. Other platforms refuse the entire worker.

```console
cargo fmt --manifest-path experiments/0034-source-oplocks/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0034-source-oplocks/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0034-source-oplocks/Cargo.toml
cargo build --locked --release --manifest-path experiments/0034-source-oplocks/Cargo.toml
python experiments/0034-source-oplocks/qualify.py --binary experiments/0034-source-oplocks/target/release/imageinfo-source-oplock-probe.exe --parent .local/source-oplock-qualification
```

The qualifier retains a fresh owner-only capture root. Each process has a 60-second
kill watchdog, control/message/completion waits are 15 seconds, and controls are
32 bytes. A one-second actor observation window is recorded, not advertised as a
native I/O deadline or an atomic check. The worker never acknowledges a break as
permission to publish: observations occur while the holder lives, then the holder
closes. Pending actors may succeed after that release or a measured process kill.

The 75 cases comprise 40 new-open actors, 16 late-hard-link alias operations, six
preopened time/security actors, three holder kills, four existing-multilink shape
refusals, five path refusals and one full-admission refusal. Ordinary reads, time,
readonly, DACL/owner-access, ADS, data, link, delete and rename use independent
processes. `actor.py` reuses the project-owned #0033 ABI actor; alias operations add
a link and then operate through that explicit alias. No privilege, owner assignment,
source-media, system or OS-crash operation is performed. No ACL repair or cleanup
is performed to make deliberately inaccessible markers readable.

`audit.py --root <retained-root> --binary <built-worker> --public <sanitized-json>`
checks capture equality, truthful non-commit outcomes and actual held observations,
then hashes readable artifacts and named `:probe` streams. Private source/binary
bindings and inaccessible paths remain local. Private capture directories, SIDs,
paths, object IDs, logs and compiled binaries must not be committed. A passing
qualification establishes these observations, including failures of exclusion;
it does not satisfy the complete parent safety contract.

# Planned staging bytes and exact-length copies

**#0040**, observed **2026-10-14**, implements #0022's logical scratch-byte cell
inside the existing [#0038 worker](../0038-staging-cleanup/README.md). New code is
safe portable Rust with ten tests; there is no new crate, package, OS API or unsafe
boundary. This is research, not an enabled production writer/storage profile.

```console
cargo test --locked --manifest-path experiments/0038-staging-cleanup/Cargo.toml
cargo build --locked --release --manifest-path experiments/0038-staging-cleanup/Cargo.toml
python experiments/0040-staging-limits/qualify.py --binary experiments/0038-staging-cleanup/target/release/imageinfo-staging-cleanup-probe.exe --parent .local/staging-limit-qualification
python experiments/0038-staging-cleanup/qualify.py --binary experiments/0038-staging-cleanup/target/release/imageinfo-staging-cleanup-probe.exe --parent .local/0040-cleanup-regression
python experiments/0040-staging-limits/audit.py --root <private-limit-run> --regression <private-cleanup-run> --binary experiments/0038-staging-cleanup/target/release/imageinfo-staging-cleanup-probe.exe --public docs/write-safety/staging-limits-observations.json
```

Worker arguments are `<mode> <new-absolute-local-root.marker> [logical-byte-limit]`.
Omitting the limit uses **131,072 bytes**; a supplied value is an unsigned decimal
u64. Stage (65,536 bytes) plus fixed record (31 bytes) require **65,567 bytes**.
All lengths are added with overflow checks before root/file creation. Every artifact
then uses `Read::take(planned_length)` plus `io::copy`, followed by a one-byte source
probe that is never written. Short/overlong input and I/O failure never report a
complete stage. The original creating handle and private-property checks stay held.

Modes `short-source` and `long-source` deliberately shorten/extend the marker source
by one byte before copying. They retain respectively 65,535 and 65,536 stage bytes,
no record and no output. They test producer-length errors, not a claim that source
concurrency is solved. Normal cooperative cancellation still removes only the two
verified owned files; a kill retains them. Existing-root collision preserves foreign
bytes. The root itself remains retained. Other platforms refuse the Windows adapter
while running the same portable tests.

Ten tests exercise combined budget/overflow, exact/zero/multi-buffer input, short/
unending input, partial/interrupted I/O, read/probe errors, sink errors/WriteZero and
u64::MAX without a huge allocation. Read/write failures in those tests are labeled
injections, not observed disk-full/device errors. Seventeen native limit cases and
the existing 27 cleanup cases supply actual file/cancellation/refusal observations.

The qualifier's held reads reuse #0033's existing CreateFile/ReadFile declarations
and compatible sharing; no ctypes/API declaration is added. The first attempt's
ordinary Python open conflicted with the held DELETE right. That failed attempt,
corrected captures and generated artifacts remain private. Processes retain the
existing 60-second watchdog and 15-second message waits.

This bounds planned logical bytes for one fresh transaction, not allocation blocks,
NTFS metadata, streams, memory, logs, older transactions, available space or an OS
quota. It makes no disk-space reservation or native-I/O deadline claim. OS/storage
failures can still leave private partial files; no capacity is reused and no path is
reopened for cleanup/repair. See [findings and limits](../../docs/write-safety/staging-limits.md).

# Marker receipt construction and read-only inspection

Card **#0046**, observed **2026-10-14**. Research extends the existing
[#0032 Rust worker](../0032-windows-publication/README.md) using its existing
dependencies and reviewed Windows boundary. Read the
[implemented contract and remaining gates](../../docs/write-safety/namespace-receipt-marker.md)
and [#0045 proposal](../../docs/write-safety/namespace-receipt-protocol.md).
No production writer, qualified storage profile or committed result is enabled.

`ordinary-prepare` exclusively creates an owned root and the authored 64 KiB
source. `ordinary-receipt` accepts only this marker fixture; it runs the guarded
write-through publication sequence, exclusively writes a fourth `receipt.record`,
flushes its held file and parent, and checks the actual installed namespace again.
All source/root/output artifacts remain. No real media or external original is
accepted, and source ACLs are not changed.

The additional live barriers are `receipt-written`, `receipt-file-flushed`,
`receipt-parent-flushed` and `final-checked`. The supervisor answers control
barriers with `continue`, `cancel` or `fail`, using bounded control lines. Captures
and partially completed marker runs must remain in ignored private scratch.

`ordinary-receipt-inspect` consumes one explicit compact `receiptContext` JSON
line on stdin before any control lines. The authorized supervisor must have
retained that actual context outside the editable transaction. Its fresh guards
and checks reach `receipt-inspect-guarded`; inspection never creates/removes files
or repairs permissions. Arbitrary JSON is not authenticated caller history.

Every result keeps `committed`, `namespaceAcknowledged`, `repairAllowed` and
`productionPublicationAllowed` false. Successful flush calls and a matching receipt
do not qualify their own persistence. Inspection cannot authorize finalization,
prune, replay or rollback. The old three-record modes remain separate.

Build and check with the pinned toolchain and unchanged research lockfile:

```console
cargo fmt --manifest-path experiments/0032-windows-publication/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0032-windows-publication/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0032-windows-publication/Cargo.toml
cargo build --locked --release --manifest-path experiments/0032-windows-publication/Cargo.toml
```

Run and independently audit the finite native matrix using the exact built worker:

```console
python experiments/0046-namespace-receipt/qualify.py --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --parent .local/namespace-receipt-qualification
python experiments/0046-namespace-receipt/audit.py --root <retained-private-run> --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --public docs/write-safety/namespace-receipt-native.json
```

The qualifier retains the source/binary binding, supervised release-fence history,
control/actor captures and before/after inspection inventories. It also uses
`ordinary-receipt-short-record` as an explicitly labeled malformed producer input;
that case and injected `fail` controls do not simulate native full-disk/device or
failed-flush errors. Other operating systems use the binary without `.exe` and
retain an explicit unsupported Windows adapter; portable typed parsing and model
tests do not supply filesystem qualification.

The **327,680-byte** logical staging bound covers one candidate and four bounded
records, excluding the retained source and external context. It is not a disk
reservation, allocation quota, cumulative retention limit or hard I/O deadline.
Guest, native storage-error, resource/retention, physical-power and complete
profile admission remain separately scoped work. No personal data, logs,
assembled worker or disposable guest artifacts belong in the public repository.

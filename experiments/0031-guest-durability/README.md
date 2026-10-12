# Disposable guest interruption and recovery research

Card **#0031**, observed **2026-10-12**. Standalone Rust marker probe and Python
QEMU supervisor; no source media, production writer/profile or automated repair.
Read [the measured configuration and unresolved cells](../../docs/write-safety/guest-durability.md).

The Linux worker creates a 64 KiB authored marker and separate recovery copy in
an explicitly supplied private root. It holds an anonymous candidate and links the
held inode with conditional absence. This extends #0029's Linux mechanism; it is
**not #0032's Windows implementation**. Owner/mode, link-count, live identity and
checksum checks are observations, not complete concurrency or custody guards.
Serialized identities, imported records and a matching checksum never authorize
finalization, replay, rollback, prune or production publication.

```console
cargo fmt --manifest-path experiments/0031-guest-durability/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0031-guest-durability/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0031-guest-durability/Cargo.toml
cargo build --locked --release --manifest-path experiments/0031-guest-durability/Cargo.toml
python experiments/0031-guest-durability/qualify.py --binary PATH_TO_PROBE --parent PRIVATE_SCRATCH_PARENT
```

The portable seven-case suite checks refusal/retention only. Linux inspection is
read-only at the application level; Windows/macOS refuse the Linux probe before
worker artifacts. The supervisor's scratch directory and foreign marker remain.
CI never crashes its runner. VM interruption evidence is an explicit local suite.

## Isolated guest reproduction

Use Linux with QEMU 10.2.1, cpio, e2fsprogs, Python 3, an extracted Alpine virt
3.24.2 kernel/initramfs tree, and a static x86_64 Linux-musl probe built with pinned
Rust 1.99.0 and this package's lockfile. Do not run `guest-init.sh` on the host.
It requires PID 1 and the separately supplied disposable-guest kernel marker.
Crash sysctls and NMI injection affect only this independent QEMU kernel.

```console
cargo build --locked --release --target x86_64-unknown-linux-musl --manifest-path experiments/0031-guest-durability/Cargo.toml
python3 experiments/0031-guest-durability/build_guest.py --kernel EXTRACTED_KERNEL --template EXTRACTED_INITRAMFS_TREE --probe STATIC_PROBE --parent PRIVATE_BUILD_PARENT
python3 experiments/0031-guest-durability/guest_suite.py --build NEW_BUILD_DIRECTORY --parent PRIVATE_RUN_PARENT
python3 experiments/0031-guest-durability/audit.py --root COMPLETE_RUN_DIRECTORY --build NEW_BUILD_DIRECTORY --public SANITIZED_LEDGER_PATH
```

On Windows the musl cross-build needs an explicitly selected `rust-lld.exe` linker
from the pinned toolchain (`CARGO_TARGET_X86_64_UNKNOWN_LINUX_MUSL_LINKER`). Run the
assembler and QEMU supervisor in Linux; WSL may host QEMU, but its kernel is never
crashed or reconfigured. Paths containing QEMU block-option separators (comma/colon)
are not supported by this narrowly scoped harness. Use ordinary private Linux paths.

The assembler formats only a newly created regular 64 MiB image inside its owned
temporary directory. It performs no host mount, block-device access, privilege
change or network operation. The supervisor copies that image for every case.
QEMU has no host shares/network, no default devices/user config, one vCPU and 256 MiB
RAM. It boots the supplied kernel/initramfs and sees only its copied virtio disk.
All images/captures remain retained; no broad cleanup is provided.

Worker control reads are bounded to 32 bytes. Each QEMU process has a 180-second
watchdog, guest-message waits are 30/60 seconds, and QMP operations have 20-second
socket waits. These are orchestration bounds, not hard native I/O deadlines or
complete OS memory/output quotas. Do not pass Python `-O`: assertions are the
qualification verdicts. No unrelated process is killed.

## Outcomes and retained evidence

The nine barriers follow actual file/directory flush calls. An observation record
is always observation-only, never a durable committed receipt. Deterministic
`worker-fail-*` modes inject a named protocol error **before** a selected flush;
they do not claim that the kernel returned an fsync error. Separate actual ENOSPC
and QEMU blkdebug device-flush cases exercise native guest failure paths.

Process kill, cooperative cancellation, NMI-induced guest panic and abrupt QEMU
SIGKILL are distinct. QMP `quit` used for ordinary cleanup may add emulator flushes;
the abrupt case uses process kill. Host caches and storage stay powered in all cases.
There are **zero physical power-loss runs**, and no Windows guest crash evidence.

Restart uses ext4's journal replay on mount before application-level inspection.
Inventory snapshots bracket inspect/finalize/prune/admit: identity, mode, owner,
link count, size, fixed-name absence/link state and file hashes must remain unchanged.
Access times and filesystem journal/mount effects are excluded from that comparison.
Every observed state refuses repair and cleanup because custody, complete property/
path exclusion and durable-receipt qualification are missing. This is tested safe
refusal, not implementation of guarded finalization or cleanup.

`audit.py` checks captures, barrier/kill/cancel/panic evidence, refusal counts,
inventory equality, guest configuration and source/build hashes. A private manifest
binds retained disks and captures. Public observations omit paths, object identities,
disk/source/binary hashes and raw logs. Incomplete old attempts remain retained.

See [scoped notices](NOTICES.md) and [dependency admission](../../docs/write-safety/guest-dependencies.json).
No external kernel, QEMU executable, upstream initramfs/module, personal media or
assembled guest is committed or distributed. Reproduction downloads and any later
redistribution require their own provenance/license checks.

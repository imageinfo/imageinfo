# Disposable guest durability and recovery observations

**Current scope, 2026-10-15:** [best-effort power testing](power-test-policy.md)
stops at turning VMs off. Historical guest panic/NMI procedures and results below
do not authorize or require new crash campaigns. Physical power-drop testing is
outside scope and is not a qualification blocker.

**#0031**, observed **2026-10-12**, under #0022. The
[standalone research tools](../../experiments/0031-guest-durability/README.md)
exercise Linux marker publication, independent guest interruptions and restart
inspection. **No complete storage profile, production writer, committed receipt,
automated finalization or cleanup is enabled.** Actual guarded repair remains
unsupported; refusal is not an implementation of the refused operation.

## Crash-resumption audit

The laptop crash left the Rust probe, supervisor and init source uncommitted but
intact. The prior local guest build, compiled probe and disk/capture directories
also survived. One prior 37-case report was complete; its retained guest probe
matched the saved compiled executable. An earlier six-case attempt had no complete
report. Neither had a committed #0031 handoff or complete acceptance/evidence ledger.

The resumed work rebuilt the probe from the pinned sources, assembled a fresh
guest, extended the missing acceptance cases and reran the matrix. An inventory
comparison initially failed because asynchronous guest kernel messages interleaved
with serial inventory lines. Comparison now filters only timestamped kernel lines;
all artifact and shell diagnostic lines remain compared. The initial device-error
rule also prevented guest mount; it was corrected to permit the measured mount
flush before injecting subsequent flush errors. Those attempts remain retained,
not counted as successful worker/restart qualification.

## Actual configuration and assumptions

| Component | Measured local configuration |
| --- | --- |
| Worker | Rust 1.99.0, x86_64-unknown-linux-musl, safe std/rustix APIs, `unsafe_code=forbid`; separate research Cargo.lock. |
| Guest | Alpine virt 3.24.2, kernel 6.18.52-0-virt, extracted initramfs/modules and authored PID-1 init. |
| Emulator | QEMU 10.2.1 (Ubuntu package `1:10.2.1+ds-1ubuntu3.2`), q35/TCG, one vCPU, 256 MiB RAM. |
| Disk | Newly owned 64 MiB regular raw image per case; virtio, cache=writeback, error policy=report. No host shares/network/default devices. |
| Filesystem | ext4 made by e2fsprogs 1.47.2; `data=ordered,errors=remount-ro`; ordinary journal replay on restart mount. |
| Supervisor | Python 3.14.3, cpio 2.15; WSL2 host kernel 6.18.33.2-microsoft-standard-WSL2 stays running and unchanged. |
| Concurrency scope | Authored immutable producer memory, one guest worker; root/file owner-mode-link policy and live observations. Complete external source/path/property exclusion is not proved. |
| Cache survival | Guest/emulator interruption loses guest state; host page caches, Windows, hardware and physical power remain available. No lying-hardware/media-failure guarantee. |

The retained ISO matches Alpine's official SHA-256 file, checked 2026-10-12:
`3ab424762af704b2c2a9e57df1dc37f982af260071504d977f2fb96822e7130b`.
This is download integrity, not a signature verification or redistribution review.
External kernels/modules/initramfs/QEMU binaries stay local and are not distributed.

The assembler formats only its newly created regular-file image. Guest crash
controls require the separate QEMU kernel and PID-1 boot marker. No host device,
volume handle, existing WSL distribution crash, admin/privilege change, private RAW
original or network original is used. Each QEMU instance has a 180-second watchdog;
message and socket waits are bounded. Hard interruptible native I/O deadlines,
complete OS resource quotas and physical storage qualification remain unproved.

## Flush and publication sequence

The Linux worker extends [#0029's anonymous-stage mechanism](object-guards.md).
It does **not** port or qualify [#0032's Windows rename-by-handle sequence](bound-windows-publication.md).
The ordered marker sequence is:

1. Exclusive private recovery-file create/write/flush; anonymous candidate
   create/write/flush; private-directory flush. Barrier `staged`.
2. Prepared file flush and directory flush. Barrier `prepared`.
3. Intent file flush and directory flush. Barrier `intent`.
4. Live root/recovery/candidate identity and content observations. Barrier
   `validated-before-link`; these checks are snapshots, not a complete guard.
5. Conditional link of the held anonymous inode into `output.bin`. Barrier `linked`.
6. Installed identity/content observation and candidate/output flush. Barrier
   `output-flushed`.
7. Private-directory flush. Barrier `namespace-flushed`.
8. Observation file flush. Barrier `observation-file-flushed`.
9. Observation-directory flush. Barrier `observation-namespace-flushed`.

Prepared, intent and observation records have bounded strict JSON and a SHA-256
body checksum. Inspection checks purpose/version/phase, current root/recovery/
candidate observations and cross-record equality. Files must be regular, private
owner/mode and single-link; symlinks/FIFOs are refused through no-follow/nonblocking
opens. This does not authenticate a same-user record or establish exclusive custody.
The observation record never declares committed or authorizes actions.

The directory flush is deliberately separate from file flush. Linux's
[fsync manual](https://man7.org/linux/man-pages/man2/fsync.2.html) explains that file
sync does not necessarily persist its directory entry (man-pages 6.19, page dated
2026-02-08; viewed 2026-10-12). That API rule supports the sequence, not a claim that
this emulated test proves every physical storage configuration.

## Interruption and adversarial cells

The [sanitized ledger](guest-observations.json) records the complete matrix and
capture audit. Actual observed classifications, rather than sent control words or
the last recorded phase alone, determine each assertion.
The final **69 cases** comprise 37 normal/interruption cases, 19 adversarial states,
11 protocol-injected flush refusals, one actual ENOSPC and one emulated device-flush
error. **119 captures and 617 retained files** passed the private manifest audit.

| Cell | Evidence and interpretation |
| --- | --- |
| Normal completion | Complete candidate and observation record visible after reboot; still observation-only and not committed. |
| Cooperative cancellation | Actual `CONTROL_STOP` at each of nine barriers. Before link, no output; after link, visibility may already have changed. No rollback/replay is attempted. |
| Worker kill | Owned child killed with serial acknowledgement at nine barriers, followed by separate boot/inspection. This is not an OS crash. |
| Guest OS crash | QMP NMI causes a captured independent guest kernel panic at nine barriers; emulator cleanup is recorded separately. Host/WSL kernels remain alive. |
| Simulated guest power interruption | Abrupt SIGKILL of the owned emulator at nine barriers. Host caches remain; this is not physical power loss. |
| Physical power loss | Zero runs. Hardware/controller/volatile-cache survival is unverified. |
| Output/receipt namespace persistence | Before directory acknowledgement, absence or a complete candidate is permitted. After acknowledged output namespace flush, candidate is observed; after observation namespace flush, its record is observed. No indefinite/physical survival promise. |
| Missing or damaged evidence | Missing intent/all records/recovery; corrupt/oversized/incompatible-mode/symlink/FIFO intent; corrupt observation/recovery; incompatible root mode. Invalid evidence remains recovery-required. Missing intent may permit an observation using prepared evidence; never repair authority. |
| Foreign/uninspectable output | New foreign inode, changed bytes, incompatible mode, symlink, FIFO and directory target. Target is preserved and classification is foreign/uninspectable. Missing output is reported as current expected-absence observation, not proof that a previously linked output never existed. |
| Alias topology | Added recovery hard link violates the single-link observation policy; neither link is removed. |
| Full disk | Actual guest ENOSPC on a filled copied data disk; no publication/commit and restart remains uninspectable/recovery-required. Host storage is not filled. |
| Native flush failure | QEMU blkdebug rejects device flushes after mount. Worker reports native I/O failure; QMP counts failed device flushes. Restart inspection retains uncertainty. This is an emulated device-error test, not physical drive-failure qualification. |
| Every ordered flush refusal | Eleven explicitly labeled protocol injections before recovery/candidate/prepared/intent/output/observation file or directory sync points. They test stop/retention ordering; they are not eleven observed native syscall failures. |
| Guarded finalization/cleanup | At every restart/adversarial state, `finalize`, `prune` and `admit` refuse before mutation. Before/after inventories retain current foreign/owned identity, bytes, mode, ownership, link topology and artifacts. No deletion by filename, stale rollback, replay or false commit. |

The guest worker runs as guest root. The incompatible-mode cases measure the
probe's strict policy rejection, **not actual access denial for another user's
token**. Inspection may cause access-time effects; journal replay/mount may change
the filesystem. Inventory equality covers fixed artifact identities/content/policy,
not byte-for-byte immutability of the mounted raw filesystem.

## Qualification disposition and remaining gates

| Requested capability | Disposition |
| --- | --- |
| Authored Linux marker visibility/restart observations in this guest configuration | Measured research subset; no RAW/source integration. |
| Linux complete source/path/property exclusion and authenticated restart custody | Unsupported. Private modes, root identity and checksums are insufficient. |
| Actual guarded finalization/prune | Refused before mutation. No supported recovery profile exists to authorize it. |
| Windows namespace/receipt persistence across OS crash | Unverified. No isolated Windows guest crash configuration or evidence is supplied; Linux results do not transfer to Windows/NTFS. |
| Windows/macOS use of this Linux probe | Explicit unsupported refusal before worker artifacts; portable CI tests refusal and foreign-marker retention. |
| Physical power-loss, network/cloud/removable/alternate filesystem or hardware guarantees | Unverified; no profile inherited from these tests. |
| Production CR3 writes, durable committed receipts, source integration | Disabled. #0022/#0014, #0027 admission/authenticity and #0023 integration remain open. |

WS-009/010/011/013/014/015/016/019/023/024, SAF criteria and GAP-004/GAP-009 stay in
force. In particular, successful namespace/record observations cannot supply the
missing property/custody guard. #0032's same-user link/time/ACL/stream windows remain
unsupported. A future actual Windows crash/recovery qualification must use its real
held-object sequence and separately scoped disposable Windows storage; a Linux
analogue or passing process-kill test cannot close that cell.

No weaker concurrency/property promise or automatic repair is introduced. #0031's
handoff supplies reproducible bounded research observations, adversarial refusal
evidence and an explicit unsupported-profile ledger; it does not claim the complete
#0022 backend or the unimplemented finalization/cleanup operations are qualified.
The missing enablement cells remain on the parent rather than being hidden by
moving a research card to review.

## Verification and provenance

Source/build hashes, raw serial/QMP/argv/control/event captures, copied disks and a
verified private artifact manifest remain local. Public observations omit object
identities, personal paths and raw logs. Failed/incomplete attempts remain named and
retained. The root package/lockfile, reader and production unsafe policy are unchanged.

The [26-package/29-notice admission](guest-dependencies.json) matches previously
reviewed exact registry archive identities and retained notices. New source is
project-authored; no upstream implementation/tag table/fixture is copied. Guest
assembly uses external local tooling only; no compiled guest release is published.
Portable platform CI builds/lints this research package and tests safe refusal;
it does not execute VM crashes on a shared runner.
Local root formatting, Clippy, 25 tests and release build passed, as did research
formatting/Windows and Linux-target Clippy, Windows release build, musl cross-build
and seven portable refusal/retention cases on each of Windows and Linux. Python
syntax and documentation/link/JSON checks passed. Platform CI source binding is
recorded separately in [the CI ledger](guest-ci.json).

Primary sources, viewed **2026-10-12**:

- [QEMU blkdebug documentation](https://www.qemu.org/docs/master/devel/testing/blkdebug.html)
  (online master documents 11.1.50; the exercised implementation is local 10.2.1).
  Supports error-rule reasoning; native guest/QMP captures are the actual verdict.
- [Linux ext4 documentation](https://www.kernel.org/doc/html/latest/admin-guide/ext4.html)
  and [journal description](https://www.kernel.org/doc/html/latest/filesystems/ext4/journal.html).
  Explain ordered-data/journal behavior; they do not qualify the host hardware.
- [Alpine releases](https://www.alpinelinux.org/releases/),
  [downloads](https://www.alpinelinux.org/downloads/) and
  [the 3.24.2 virt checksum](https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/x86_64/alpine-virt-3.24.2-x86_64.iso.sha256).
  Binary assets are excluded from the public repository.

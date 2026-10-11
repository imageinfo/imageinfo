# Live object and namespace guard qualification

**#0029**, observed **2026-10-11**, under #0022. The
[actual Rust probes](../../experiments/0029-object-guards/README.md) qualify separate
guard mechanisms against real filesystem actors. **No full production mutation
profile is enabled.** This result neither accepts #0028 on Terry's behalf nor
promotes either research worker into the CLI.

## Findings by guard

| Mechanism | Actual evidence | Limit / disposition |
| --- | --- | --- |
| Windows held source, read sharing only | New writes, truncation, deletion and rename refused. Existing hard-link and case-fold aliases shared the same content exclusion. Preexisting writable handles/maps prevented guard acquisition; a readonly map remained compatible. | Qualified observation for the measured ordinary local NTFS object/handle scope. Source ACL/attributes/timestamps and alternate providers are separate gates. |
| Windows new stage, held read/write handle with read sharing only | Same content/delete exclusions through the stage lifetime. New hard-link alias creation was itself refused by the measured named-path API. Existing stage creation refused without overwriting its bytes. | Closes the observed ordinary named-writer access route while the handle remains held. An actual Windows publication method/private property policy is still #0030. |
| Held Windows ancestors and no-follow flags | Parent rename and reparse/junction traversal refused. UNC/device/verbatim/relative operands were not silently normalized into supported input. | Ordinary fixed local-volume paths only; no privileged DOS-device/mount/provider or full security-property guarantee. Ancestor sharing is not a lock on all child names. |
| Linux anonymous stage | With no candidate pathname, poisoning a named `candidate.cr3` did not change the held stage. Descriptor-sourced conditional link published that inode and retained a racing unrelated target. Cancellation/kill before link left no named stage/output. | Prevents #0028's tested named-stage poisoning route. Proc-fd/privileged access, post-link output writes, path spelling and full durability are not excluded. |
| Linux source read lease | Existing writable handles/maps caused refusal. A new writer, including a hard-link alias, blocked and notified the holder; `F_GETLEASE` exposed the pending break. Publication must refuse that state. | Read-object coherence during the tested held interval. Leases can expire/break; no unbounded I/O/publication guarantee. Rust production integration is not selected by the Python qualifier. |
| Linux lease plus rename/mtime mutation | Source rename and timestamp mutation succeeded while the leased object remained readable. | Lease is not a pathname/property guard. Strict live-file-source publication remains unverified/refused, not downgraded to advisory locking or a late hash check. |

## Actual scope and data

Windows NTFS qualification contains **25 marker-data cases**: source/stage writers,
truncate/delete/rename, case aliases, existing aliases/new alias refusal, ancestor
rename, metadata drift, prior handles/maps, existing stage and explicit path/reparse
refusals. The environment is Windows 11 build 26200 x64, local fixed NTFS with an
unchanged ordinary drive mapping. This is not automatic admission of an arbitrary
drive, remote path, synchronized directory or filesystem provider.

WSL2 qualification contains **12 cases**, five anonymous-stage and seven lease
observations. Ubuntu 26.04, kernel 6.18.33.2, native ext4 uses the separately measured
configuration. The kernel's lease-break setting was **45 seconds**; bounded contender
checks took at most two seconds and released the lease explicitly. No forced-expiry,
OS-crash, power-loss, lease-configuration or existing-distro interruption occurred.
These timing bounds are harness controls, not native latency/performance guarantees.

Eight separately named private EOS R5 RAW clones and their existing aliases were
tested with the actual Windows held-source implementation. All **16 write attempts
were refused**. Held object identity, full file contents and measured properties
remained unchanged; received/network originals were neither written nor metadata-
modified. The raw files remain the initial narrow firmware/ISO/lens stratum.
No sensor decoding/recompression, new metadata edit, signature/privacy test or
broader format/variant claim follows.

Per-image identities/hashes, exact captures, private clones, original paths and
recipes stay out of Git/CI. Public CI uses authored marker bytes exclusively.
[Sanitized results](object-guard-summary.json) distinguish mechanism observations
from the zero enabled production profiles.

Eight scoped guard experiment records, eight clone admissions/provenance reviews,
27 package reviews and 30 notice-only reviews validate. A 72-artifact registry
verifies the retained private source/binary/driver/capture/recipe identities,
including the exact control stdin. Existing reference reads bind identical input
bytes; they are not independent replications of these OS guard tests or a new
metadata parity claim. Host supervision is bounded at 120 seconds; no OS memory
cap or interruptible native I/O deadline is asserted.

[Actual CI evidence](object-guard-ci.json) binds code revision
`96a64b72f546ebacbd3b09b3e2b1dd34a474d35a` to successful Windows x64, Ubuntu x64
and macOS arm64 jobs, including production, prior research and guard gates.
Windows ran 25 guard cases; Ubuntu 12; macOS explicitly refused the unsupported
mechanism without artifacts. This enables no complete mutation profile.

## Interpretation and remaining gates

Source/stage **content exclusion**, **object identity**, **path binding**, **property
protection** and **persistence** are independent cells. In particular metadata drift
cannot be described as prevented merely because content writes were blocked. A
coherent held-object read does not establish that its originally reviewed pathname
still names that object. `O_TMPFILE` does not make data permanently immutable after
it acquires a name.

The strict guard refuses any whole workflow whose required cells are unverified.
This research has no production `--apply` path; every probe result explicitly denies
production publication. Neither imported profiles, checksums nor observed success
can grant permission. No advisory-lock, hash-then-rename or silently weakened mode
replaces WS-009/010. The post-check race retained on #0028 remains a failed backend
gate until an integrated sequence covers all applicable windows.

#0030 owns the Windows publication/property/persistence implementation; #0031 owns
isolated durability and guarded recovery. They must combine the tested mechanisms
with remaining source/path/property conditions rather than inherit complete support.
#0022/#0014 remain open; #0027 supplies exact format/authenticity admission and
#0023 supplies production integration. GAP-004/GAP-009 remain open. All physical
originals are preserved; no replacement/source deletion or secure-erasure claim.

## Engineering and provenance

The Windows probe uses ordinary lexical handle lifetimes and native sharing modes.
A narrowly scoped safe handle-information wrapper avoids application-owned unsafe
FFI and unstable std file-ID APIs. Linux uses the already reviewed safe descriptor
APIs; its lease qualification uses Python's standard `fcntl` and signal facilities.
No runtime framework, arbitrary callbacks or external metadata engine is adopted.

The separate lockfile adds `winapi-util` 0.1.11 under its MIT option. Existing
research packages retain their exact versions; root production Cargo.lock is unchanged.
See the [27-package research admission](guard-dependencies.json) and complete
copyright/license notices. Compilation/testing and notice publication are scoped;
no vendored dependency implementations or public assembled executable is admitted.

Primary sources viewed **2026-10-11**:

- [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
  supplies sharing/access semantics. Actual handle/mapping results above remain
  specific observations; the API reference alone does not prove a storage profile.
- [winapi-util 0.1.11](https://docs.rs/winapi-util/0.1.11/winapi_util/file/index.html)
  provides safe handle information. Exact archive identity and retained source
  declarations are recorded, without copying implementation into imageinfo.
- [Linux manual source: fcntl](https://raw.githubusercontent.com/mkerrisk/man-pages/ae6b221882ce71ba82fcdbe02419a225111502f0/man2/fcntl.2),
  [open](https://raw.githubusercontent.com/mkerrisk/man-pages/ae6b221882ce71ba82fcdbe02419a225111502f0/man2/open.2),
  [link](https://raw.githubusercontent.com/mkerrisk/man-pages/ae6b221882ce71ba82fcdbe02419a225111502f0/man2/link.2):
  historical maintainer snapshot, not a claim about the newest manual/kernel.
  Lease-break and anonymous-stage interpretations are corroborated by the actual
  native runs. No manual text or syscall implementation is imported.

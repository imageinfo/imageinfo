# Held-candidate Windows publication and strict admission

**#0032**, observed **2026-10-11**, under #0022. The
[standalone Rust implementation](../../experiments/0032-windows-publication/README.md)
now publishes the actual held marker candidate with stable held-parent/candidate
identity and retained content/name guards. **The complete production profile remains
unsupported and refuses before effects.** No CR3 writer, committed receipt or repair
is enabled; no private RAW/network original is read or changed by these experiments.

## What changed after #0030

#0030 held directory handles with read sharing only. That excludes entry operations
needed by a pathname/native move. This implementation shares read/write on directory
handles while excluding DELETE, so ordinary parent rename/deletion remains refused.
The candidate's separate read-share-only handle excludes ordinary data writers and
source-name removal/movement. Its already-granted DELETE access lets the holder issue
rename-by-handle. No guard is released or weakened after a refused call.

The Win32 absolute destination succeeds within the guarded ordinary DOS ancestry.
The separately requested directory-relative Win32 form refuses with error 87 in the
measured environment. It never falls back. Privileged drive/mount remapping and remote,
cloud, removable or alternate-provider paths are not admitted by these observations.

Private root creation uses documented user-mode `NtCreateFile` against a checked live
parent handle. Exclusive creation supplies the protected owner-only descriptor and
returns the new directory handle atomically. This closes the create-directory/open-
pathname gap; an existing root/junction or racing candidate is retained and refused.
The [small reviewed ABI boundary](../../experiments/0032-windows-publication/ffi-review.md)
explains this deliberate departure from std/managed creation. Root production unsafe
policy is unchanged.

## Measured capability cells

| Cell | Actual evidence | Disposition |
| --- | --- | --- |
| Private security at creation | Protected current-process-user owner/DACL supplied during root and artifact creation. Canonical owner/DACL checked from actual handles; no inheritance exposure window. | Scoped creation and observation policy. Group/SACL/mandatory labels, another user's token and privileged threats are not proved. |
| Source candidate and root binding | Native exclusive create returns root handle; held ancestor/root directory handles exclude DELETE. Live identity getter and an attribute-only installed handle bind target to held candidate. | Measured content/name identity guard for the ordinary local path scope. No authorization from serialized IDs or checksum. |
| New output visibility | Held candidate is renamed without replacement; existing/case-fold/directory winners retained. Compatible reader sees all 65,536 authored bytes. | Single-file marker visibility and no-clobber observations, not all RAW operations or power-loss durability. |
| Late named-stage substitution | Competing source-name rename/data replacement after last validation refused; actual installed identity/content remain the held candidate. | Closes #0030's measured late default-stream substitution route without a pathname source reopen. |
| Parent movement and child entries | Parent movement/removal refused from root-created through later tested barriers; unrelated child creation remains possible. | Guards parent identity, not every child name. The final target has conditional absence. |
| Aliases | A new link can be created/deleted; default-stream writes through it refused. Retained new alias changes link count and causes property rejection. | Link/property topology is not frozen by the content/name guard. It is not safe cleanup authority. |
| Time, readonly, DACL, alternate stream actors | Mutations succeed. Before last validation they stop publication; after visibility they leave recovery uncertainty. Streams are inspected through the held handle, with bounded inventory. | Mandatory whole-property protection remains unsupported. Checks are snapshots. |
| Prepared/intent/observation records | CREATE_NEW, private descriptor, checksum body, actual identity/content observations and retained read-share-only handles. Tested ordinary record writes/deletion refused while held. | Integrity observation and in-process content guard, not authenticated custody, indefinite immutability or restart repair. |
| Candidate/record/directory flush order | Candidate flush and root flush; prepared file/root flush; intent file/root flush precede publication. Output flush and writable-private-directory flush call return; observation file flush follows. | Actual API-call ordering. Directory flush success differs from #0028's read-only-handle failure; it does not alone qualify namespace persistence or a durable receipt. |
| Complete-profile admission | `admit` reports unsupported before filesystem calls/artifacts, including on an otherwise valid new root. | No production permission inferred from primitive successes. Missing property/persistence/recovery cells refuse. |

All statements concern the tested held interval. After closing the handles, the
user may edit the files. Ordinary readers with incompatible sharing can be refused
while the candidate holder has DELETE access; the compatible reader explicitly
shares read/write/delete. No long-term output immutability is claimed.

Directory/file policy permits and preserves `NOT_CONTENT_INDEXED` in addition to
ordinary directory/archive/normal attributes. Windows CI inherited that bit from
its workspace, which exposed an initially too-narrow attribute mask before publication.
Local cases now reproduce inheritance and reject a later change of the directory's
captured indexing preference. Other unsupported attributes still refuse; ACL/name/
content guards and complete-profile refusal were not loosened. The bit's meaning is
defined in [Microsoft's attribute reference](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants)
(viewed 2026-10-11); it is not permission to skip privacy or storage qualification.

## Verification and retained evidence

**78 actual Windows cases** cover the cells above, root/candidate creation races,
existing-root/parent junctions, before/after property changes, strict admission,
ordinary-path/namespace grammar exclusions, Unicode paths, bounded controls, and
failure/process kill/cooperative cancellation at each of nine barriers. All case
assertions pass; this means the observed **successes and unsupported cells** match
the evidence, not that the complete profile passed.

[Sanitized observations](bound-publication-observations.json) contain no account SID,
filesystem object ID, personal-media path or per-image hash. Exact source/binary hashes,
argument/control/parsed-event captures and **523 marker artifacts** are retained in
ignored local storage and checked. Native pipe byte-exactness is not claimed. Older
failed hypotheses/captures remain retained rather than relabeled as successful runs.

Local worker: Rust 1.99.0, Windows 11 x64 build 26200, ordinary local fixed NTFS and
unchanged DOS mapping. SDK uses exact windows-sys 0.61.2. Hardware/controller/cache
survival configuration is not established. Directory synchronization targets only
the owned private directory handle; no host-volume handle, privilege change, admin
shortcut, host/WSL crash, power cut or original media operation occurs.

Host limits are 30 seconds per control/actor wait and 120 seconds per owned worker.
Control input is 32 bytes; marker reads 65,537 bytes; security/stream query buffers
are bounded. No OS memory quota, interruptible native I/O deadline or qualified async
path is asserted. On a native constructor's unexpected pending response the process
aborts rather than release still-pending stack outputs. The expected synchronous
path is tested; that exceptional response is not claimed as a passed case.

The [27-package admission](bound-publication-dependencies.json) reuses exact archive
identities and 30 retained notices; direct SDK features/new native operations have
the separate boundary review. No root Cargo/dependency/source changes and no public
compiled executable distribution occur. Linux/macOS explicitly refuse this Windows
worker before worker artifacts; there is no platform fallback.

## Handoff and remaining gates

#0032 implements the held-candidate/parent mechanism, atomic private creation, live
property/identity checks, retained records and actual ordered flush calls. It resolves
missing complete-profile cells by **explicit unsupported admission**, as the card
allows; it does not reinterpret API success as complete backend verification.

#0031 owns isolated crash/durability and guarded recovery evidence against this
actual sequence, including receipt namespace persistence and actual observed state
after interruptions. Its disposable storage must be scoped before any OS crash.
Same-user property/link mutation constraints remain explicit on the open #0022/#0014
gates. Do not bypass them with late hashes, broader inherited ACLs, imported profile
booleans, unguarded cleanup or a release-guards/rename fallback. A weaker product
concurrency/property promise requires Terry's separate decision.

WS-009/010/011/013/014/015/023/024, SAF criteria and GAP-004/GAP-009 remain in force.
#0027 admission/authenticity and #0023 production integration are separate. The prior
[#0021 CR3 preservation proof](new-output-preservation.md) is not rerun or expanded
by these image-independent marker observations.

Primary references, observed **2026-10-11**, exact dependency version and safety
conditions are listed in the [boundary review](../../experiments/0032-windows-publication/ffi-review.md).
They support API reasoning; current storage/hardware persistence is not established
by a manual page or successful file/directory flush alone.

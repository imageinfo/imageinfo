# Existing-target Windows replacement boundary (#0193)

**Static review, 2026-10-16: unsupported under the current strict contract.**
The reviewed local-NTFS boundary supplies no qualified sequence that replaces
exactly the expected old target while continuously preserving its required
properties and excluding unrelated/preopened or alias edits. This completes the
bounded boundary investigation; it does not implement or qualify replacement.
No API wrapper, experiment, source ACL change, media operation or VM run is added.

The missing guarantees are independent:

- **ET-193-identity:** a replacement must select the expected current target
  object, with effective exclusion throughout the operation or an atomic
  expected-object condition. The reviewed replacement interfaces take a target
  name, not the held expected target or its file ID.
- **ET-193-properties:** the actual old object, its required property/stream
  content and recovery material must remain protected across capture and
  replacement. Read sharing, the measured oplocks and a later DACL seal do not
  establish that protection for an already exposed object.
- **ET-193-path:** all required source/destination parent and ancestor bindings
  must remain effective. A held leaf file or one fresh-root directory is not
  the complete path guard.

These are missing guarantees of this reviewed boundary, not a theorem that every
Windows mechanism must fail. Neither a successful rename nor a post-effect
conflict report satisfies them. [WS-009–012](README.md) remain strict for existing
targets. [OD-11 option A](practical-output-policy.md) applies to new outputs only;
its property checkpoints cannot be imported here without a separate explicit
Terry product decision.

## Reviewed revisions and evidence

Project source was read at commit
`9dcbf2729bd99d0b0e6477e61bc34abde5b3f9dd`, with the reviewed files unchanged.
The native boundary uses pinned **windows-sys 0.61.2** and the existing reviewed
SDK features; the [#0032 ownership review](../../experiments/0032-windows-publication/ffi-review.md)
remains the authority for its original scope. The reference Rust implementation
is **1.99.0**, revision
`b940084d7eb6a299eb4bfeb8e34901bc051e7ac4`; this review reread its
[Windows rename body, lines 1248–1311](https://raw.githubusercontent.com/rust-lang/rust/b940084d7eb6a299eb4bfeb8e34901bc051e7ac4/library/std/src/sys/fs/windows.rs).

Existing native observations are [#0093's 29-case result](conditional-replacement.md),
[#0033's fresh-seal/preopened-handle result](owner-rights.md) and
[#0034's existing-source oplock result](source-oplocks.md). They are finite
ordinary-token Windows 11 build 26200/local-NTFS observations, not new runs or
cross-platform qualifications. The static traces below distinguish those measured
results from deductions about proposed sequences.

Microsoft pages were reread on **2026-10-16**. They are living documentation, not
revision-pinned OS guarantees. Their displayed update dates are recorded below.
The SDK/compiler pins do not freeze filesystem-driver behavior.

## Exact existing handle and ownership boundary

Line references in this section are to the linked project source at the revision
above. Numeric share modes are `READ=1`, `WRITE=2`, `DELETE=4`.

| Object/call | Exact existing boundary | Consequence for replacement |
| --- | --- | --- |
| Fresh candidate, [native.rs](../../experiments/0032-windows-publication/src/native.rs), lines 279–327 | `CreateFileW`, `CREATE_NEW`, `GENERIC_READ | GENERIC_WRITE | DELETE | READ_CONTROL`, `FILE_SHARE_READ`, `FILE_FLAG_OPEN_REPARSE_POINT`, fixed private descriptor, noninherited handle; optional fixed write-through flag | Creation returns the actual owned candidate. Its own DELETE right permits a held-source rename; a pathname reopen requesting DELETE conflicts with this hold. This constructor does not open an existing target. |
| Fresh private root, same file, lines 222–277 | `NtCreateFile` relative to retained parent; single checked leaf; `FILE_CREATE`; directory, synchronous-nonalert and open-reparse-point options; `GENERIC_READ | GENERIC_WRITE | READ_CONTROL | SYNCHRONIZE`; sharing READ/WRITE, no DELETE | Returns the exclusively created directory handle. Entry creation remains possible. It does not freeze every property of that directory or establish an old-target guard. |
| Ancestors, [windows.rs](../../experiments/0032-windows-publication/src/windows.rs), lines 46–98 | Restricted ordinary absolute disk path, read opens from root through parent, share READ/WRITE, backup/open-reparse flags `0x02200000`; each must be a non-reparse directory; vector retains all handles | Excludes the measured ordinary ancestor rename/deletion while permitting entry changes. No arbitrary device/network/provider/mount namespace is admitted. A local-NTFS label alone cannot fill these assumptions. |
| Publication, native.rs, lines 417–452 | Borrowed candidate `File`, borrowed parent `File`, bounded destination, `SetFileInformationByHandle(FileRenameInfo)`, union flags zero; absolute destination uses null `RootDirectory`; separately tested rooted form supplies the parent handle | Acts on the actual held source, refuses an occupied target, and contains no replacement/expected-target operand. The tested directory-relative form refused; it cannot silently become a supported shortcut. |
| Existing old target in #0093, [windows.rs](../../experiments/0093-conditional-replacement/src/windows.rs), lines 84–96, 154–169, 268–294 | Baseline read observation handles share all; strong target guard is a separate read open sharing READ only; weak target shares READ/DELETE; strong fresh-root guard requests access zero, share READ/WRITE, backup semantics | Strong and weak target modes have materially different name protection. #0093 holds only its fresh root, not the full ancestor chain. None of these opens captures a complete immutable security/stream/property snapshot. |

The native helper owns no borrowed file handles: the caller retains `File`
ownership through the synchronous call and checks. Successful create handles
transfer once to `File`; failed security checks drop that owned handle. Descriptor
copies use lexical `LocalFree` ownership. The rename's aligned, zero-initialized
buffer uses the pinned SDK layout, a UTF-16 name limited to 240 code units before
the terminator, and a byte length excluding that terminator. An OS failure is
captured immediately; there is no reopen, weaker-sharing retry, copy/delete
fallback or ownership transfer in that helper. Unexpected pending directory
creation aborts; it is not a successful asynchronous path.

The wrapper checks private owner/DACL, not arbitrary original group/SACL/mandatory
labels (native.rs, lines 197–220). Its stream inspector accepts only `::$DATA`
(lines 364–390); it neither preserves named stream content nor supplies a stream
write guard. A positive existing-target property profile cannot infer that these
fresh-artifact helpers copy or protect the original's complete required properties.

## One concrete replacement sequence, and why it is not admitted

The selected candidate for static review is the smallest apparent extension of
the held-source sequence: retain all ancestors and destination parent, retain a
read-share-only old-target guard, retain the fresh candidate's creator handle,
capture and validate the expected original/recovery material, then rename the
held candidate over the target name without releasing any hold.

This names the desired objects and interval precisely, but its final step has no
admitted implementation:

1. **Existing `Flags=0` helper:** an occupied target is a collision. A successful
   absent-name publication is a different operation. No change of its input
   filename can make it an expected-target replacement.
2. **Ordinary replace flag:** changing `FileRenameInfo` to replace-if-exists is
   a different OS boundary. It supplies no expected target identity and does not
   establish replacement of the strongly held old target. #0093's target-only
   pinned-Rust baseline returned error 5; candidate-only/both returned 32. Those
   observations do not identify which internal call ran or qualify this new
   held-source variant. Releasing the target or candidate guard is forbidden.
3. **POSIX extended replacement:** `FileRenameInfoEx` plus replace/POSIX flags
   deserves separate consideration because Microsoft documents replacement despite
   existing handles; the old handles can continue to access the old object.
   Consequently ordinary sharing refusal is not a universal impossibility proof.
   The extended structure still has no expected-old-object condition, does not
   exclude old-object property actors and does not establish complete recovery
   preservation. Its open-target behavior is not permission to discard the strict
   contract. It is a new helper/class/flag boundary, unimplemented and unqualified
   here. No POSIX or readonly-override fallback is adopted.

The structure's fields and ordinary collision behavior are specified by
[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
(updated 2026-05-15). The open-target POSIX distinction is documented separately in
[FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)
(updated 2022-09-01). This review uses those interfaces to identify absent operands
and guarantees; it does not infer a working user-mode implementation from the
driver documentation or its broader general rename rules.

Two nearby alternatives do not repair the selected sequence:

- **`std::fs::rename`:** the pinned implementation first calls replacement
  `MoveFileExW`. On access denied it reopens the source by pathname for DELETE and
  attempts extended POSIX replacement. It does not consume the retained candidate
  or expected target. Its final error can preserve the original failure rather
  than the fallback's error. #0093 is a measurement of that entire operation,
  not a trace of one syscall. Its weak late-target and late-candidate substitutions
  actually overwrite a foreign winner/publish foreign staging bytes.
- **`ReplaceFileW`:** the documented function reopens target and candidate by
  name; its target open requests READ/DELETE/SYNCHRONIZE with all sharing, and its
  candidate open requests additional rights without sharing. These opens cannot
  simply reuse the strong handles above. There is no expected-target-ID operand.
  Its named-stream merge covers streams absent from the replacement, not a proof
  that every existing stream's content is preserved under concurrent edits. Some
  documented errors leave names or properties changed. Merge/ACL-ignore flags
  would violate the strict property policy; its write-through flag is unsupported.
  See [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
  (updated 2023-06-01). No claim about retaining the old target's file ID is used.

Moving the held old object to a fresh backup name and then publishing without
replacement is also two namespace operations, with a missing-target interval and
a possible foreign winner. It is not an atomic expected-target replacement. A
safe refusal after a winner is useful, but cannot be relabeled completion of
#0194. #0195 must separately assess its own held-existing-object move contract.

## Strict property and preopened-actor audit

[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
documents that attribute/extended-attribute access is outside ordinary sharing
restrictions. Its sharing compatibility also applies to existing opens; a
conflicting open must refuse, not wait for the worker to weaken its guard.
The following conclusions use that API boundary and the separately linked native
#0033/#0034 observations. They are not new actor measurements.

| Actor/property | What the current evidence establishes | Required existing-target disposition |
| --- | --- | --- |
| Preopened default-stream writer or write mapping | Incompatible existing content-write access prevents acquisition of a read-share-only guard; a successful guard is not permission to close it later | Refuse incompatible acquisition. Keep effective byte/name exclusion through replacement; advisory coordination/hash equality cannot substitute. Unqualified mapping cases refuse. |
| Time/attributes, including preopened `FILE_WRITE_ATTRIBUTES` | Ordinary sharing and tested oplocks permit measured time/readonly changes. #0033's preopened time handle still acts after later sealing | No continuous exclusion. A stale timestamp/attribute recovery snapshot can lose an edit; even edit/reversion between equal checks remains outside the strict guarantee. Refuse before publication. |
| Security, including preopened `WRITE_DAC`/owner access | New security behavior varies across measured guards/oplocks; #0033's preopened DACL handle acts after later sealing. Those observations do not establish revocation or complete owner/security exclusion | Neither exact security comparison nor a fresh-artifact descriptor authenticates an immutable original descriptor. Refuse unsupported security/property combinations. Do not seal the original or rebaseline actor changes. |
| Existing or newly created named stream, including preopened stream writer | Default-stream holds are not complete all-stream-content guards. #0033/#0034 have measured ADS bypasses; #0093's observer records stream names/lengths, not content hashes | Equal inventory/length can miss a same-length stream edit. Preopened ADS writers are not proved excluded. No preservation claim for stream content, creation or deletion without an effective complete mechanism. |
| Hard links and physical aliases, including preopened link-capable actors | #0034 creates late aliases and changes time/ADS through them without an oplock break. #0032's ordinary guard permits measured link creation. No reviewed mechanism revokes preexisting link-capable rights or freezes all aliases | Initial one-link count is not continuous exclusion. Existing multilink targets refuse; preopened link actors are unqualified, not claimed tested/denied. Late creation and alias properties remain a missing strict guard, not a safe post-effect warning. |
| Original retention | #0094 retains finite default bytes/basic properties with identity holds; [its stated limits](original-retention.md) exclude complete filesystem-property backup | A hard link is mutable aliasing, not an immutable recovery copy. A byte copy with properties sampled separately cannot establish a consistent original under these actors. Required original properties remain unqualified. |

The handle access requirements for explicit time/security setters are documented
by [SetFileTime](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfiletime)
and [SetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo),
viewed on the review date. No owner, SACL, privilege or source ACL operation is
authorized by citing them. Fresh sealing does not retroactively revoke the
measured preopened rights; adding checks cannot close that interval.

## Finite static path and outcome traces

These are ordered audit traces, not runnable tests. They cover one success and
the source/target/ancestor counterexamples without simulating OS qualification.

| Trace | Ordered events | Evidence and result |
| --- | --- | --- |
| ET-193-T01: successful control | #0093 captures original target/candidate, validates, unguarded control replaces; separate protected input remains held | Actual native success. It establishes API functionality, not guarded identity/property preservation. The worker reports unsupported and never committed. |
| ET-193-T02: held-source success boundary | #0032 exclusively creates and holds candidate; retains ancestry/root; existing no-replace helper targets an absent name; installed identity is checked | Existing bounded successful publication mechanism, conditional on absence. Changing the destination to an occupied old target produces the no-replace collision case, not replacement. |
| ET-193-T03: source substitution | Last check observes candidate C; weak actor moves C aside and supplies F at candidate name; pathname replacement reopens that name | Actual #0093 weak control publishes F. The existing held-source helper avoids this particular reopen, but still has no old-target replacement guarantee. |
| ET-193-T04: target substitution | Last check observes old O; weak actor moves O aside and supplies F at target name; unconditional replacement acts on that name | Actual #0093 weak control overwrites F. Another final comparison merely moves the actor window; keeping an observation handle to O does not make the name conditional. |
| ET-193-T05: ancestor substitution obligation | Only child root R is held; if the profile permits an unheld higher ancestor A to move or redirect, another A/R/name can be resolved after the final absolute-path check | Conditional static counterexample, not a claimed successful #0093 ancestor actor or proof that this move is possible under every Windows child hold. The profile must demonstrate effective ancestor binding or refuse; a child-root observation alone supplies no such qualification. A post-effect mismatch cannot undo a foreign-object replacement. |
| ET-193-T06: ordinary strong holds | Old-target and candidate read-share-only guards are retained; #0093 invokes the pinned Rust pathname operation | Actual guarded baseline refusals, retained artifacts. Dropping either guard would change the tested contract; returned error 5/32 alone is not an internal call trace. |
| ET-193-T07: property after capture | Required original properties/recovery material are captured; permitted time/security/ADS/alias actor changes the old object before replacement | Static consequence of the documented/measured bypass cells: a replacement can discard an actor edit or install stale required properties. Post-check refusal or equality after edit/reversion does not satisfy strict preservation. |
| ET-193-T08: extended replacement temptation | Keep O open; consider replace/POSIX to make the namespace step possible; old handle still designates O | The documented open-target behavior supplies neither a target-ID compare nor exclusive property control. No native success or failure of this proposed helper is asserted. ET-193-properties alone already prevents admission. |

For an admitted prepublication refusal, no replacement call may be issued and no
target/property reset or speculative restore may follow. If a future reviewed
operation is issued and the result is ambiguous, retain the old/candidate/recovery
handles and artifacts, inspect actual bindings under effective guards, and report
recovery-required rather than unchanged or committed. A native error is not a
general atomic-no-effects receipt. The current boundary therefore refuses the
unsupported profile before publication instead of exercising these alternatives.

## Handoff and dependent implications

| Scope | Consequence of this review |
| --- | --- |
| #0193 | Bounded negative boundary result supplied. Static source/API/ownership/error audit and finite traces are reviewable; no positive replacement permission follows. |
| #0194 expected-target marker replacement | Its positive implementation finish line is unmet. There is no approved implementable replacement boundary to consume; do not turn an unconditional/POSIX/checkpoint sequence or refusal-only implementation into completion. |
| #0195 held-existing-object no-replace move | Not completed here. Its expected-source DELETE/access/guard compatibility, name visibility and strict property contract still need their own result; fresh candidate creation is not existing-file admission. |
| #0196 property preservation | Strict preopened-handle, owner/ACL, supported-stream-content, timestamp/attribute and link policies remain unmet. Checkpoints and finite basic-property backups cannot be substituted for effective exclusion and complete required recovery material. |
| #0026 replacement/group/file-operation tracking | Positive replacement, removal, occupied-name restore and grouped-operation acceptance remain open. This investigation does not discharge them. |

No new research queue or further platform experiment is prescribed. The current
answer is to keep positive existing-target replacement unsupported under the
retained contract. A weaker ordinary-owner property-check policy would be a
different product guarantee requiring Terry's explicit decision before positive
implementation/profile claims; no such decision is inferred here. Format/RAW
admission, persistence and restart custody remain independent and are not causes
of this concurrency refusal. The VM-off-only power policy is unchanged.

Verification for this documentation-only handoff comprises exact source line and
ownership/error review, primary-source attribution, finite-trace/requirement
consistency and internal-link checks. Independent peer review and repository
documentation checks are recorded with the integrated handoff; no Rust runtime,
dependency or unsafe-policy change needs qualification from this document.

# Strict existing-target property refusal

Status: #0196 bounded unsupported disposition, 2026-10-16. The
[production-owned refusal boundary](../../crates/imageinfo-windows-storage/src/existing_properties.rs)
consumes an owned replacement request and returns
`EXISTING_TARGET_STRICT_PROPERTIES_UNSUPPORTED`. It cannot produce a prepared
operation or execute replacement. It opens no path, creates no staging/recovery
artifact, changes no privilege or source security, and issues no publication,
setter, cleanup or speculative restore call. This is an actual pre-effect
unsupported refusal, not a positive property-preservation capability.

The request records either ordinary modification-time behavior for a real content
edit or explicit preservation of original modification time. Both refuse. Neither
choice accepts an actor change as a replacement baseline. Missing files, unusual
paths and apparently ordinary files take the same no-I/O refusal; the error does
not claim those inputs were inspected or validated.

## Strict predicate and required inventory

WS-009/010/011/012 require the expected actual original, effective byte/name and
applicable property/alias exclusion through replacement, and complete required
original recovery material before replacement. The typed refusal names three
independent unqualified premises: expected-original replacement, continuous
property/alias exclusion, and complete required original recovery. There is no
caller-supplied boolean or editable evidence that enables these premises.

The [#0193 boundary result](existing-target-boundary.md) supplies no valid
expected-old replacement mechanism. The [#0195 same-object move](held-existing-move.md)
keeps properties on the same object; it cannot preserve them by cloning onto a
different candidate or supply immutable replacement recovery material.
[OD-11 option A](practical-output-policy.md) remains specific to new outputs.

| Required property or identity | Exact disposition |
| --- | --- |
| Default stream, object identity and expected occupied name | No replacement operation qualifies expected-old identity. A path, equal bytes or retained observation handle supplies no target-ID conditional replacement. |
| Owner, group and access control | Preserve actual owner/security and ACL semantics/order where required; do not rewrite the original ACL, take ownership, enable privilege or copy a separately sampled descriptor as complete recovery. Noncanonical ACLs also refuse. |
| Named streams | Stream names and lengths are insufficient: exact supported stream content, creation/deletion and preopened stream writers require applicable exclusion and complete recovery. All stream combinations currently refuse. |
| Creation and last-write time | Original creation time and requested last-write policy require strict preservation/recovery. Neither explicit preserve-mtime nor a genuine-edit mtime policy relaxes actor exclusion. |
| Attributes, including readonly | Do not clear readonly, reset attributes or override a failed operation. Required attributes and changes by preopened attribute handles remain outside qualification. |
| Hard links and physical aliases | A one-link snapshot does not continuously freeze topology. Initial extra links and already-open link-capable actors refuse; no mutable alias is represented as immutable recovery. |
| Reparse points and ancestors | No traversal, target normalization or redirection is attempted by refusal. Reparse paths are unsupported, including an authored junction at the selected target. |
| SACL and mandatory label | No complete auditing-SACL observation/recovery is qualified. Access failures remain explicit and no privilege is enabled to conceal them. Actual mandatory-label fixtures also refuse. |
| Access/change times and object IDs | Native evidence records access/change times but makes no preservation promise for platform-managed values or read-induced access-time behavior. File IDs/volume IDs identify observed objects; replacement would install a different object, not preserve the old object's identity or namespace history. |

Property checkpoints can supplement an effective mechanism. They cannot exclude
edit/reversion, authenticate an immutable original or make a lost edit safe after
publication. This boundary has no checkpoint comparison or rebaseline branch.
It leaves all original/candidate/recovery authority with the caller and grants no
restart or cleanup authority.

## Finite authored native evidence

The [native harness](../../crates/imageinfo-windows-storage/tests/existing_properties_native.py)
invokes the [actual compiled boundary](../../crates/imageinfo-windows-storage/examples/existing_properties_probe.rs)
in a separate process while retaining any preopened actor handles. Setup and
actor operations affect only fresh authored fixtures before the invocation.
Creator handles are closed; this does not rely on fresh-file creation custody.
Each actual request must return the exact typed refusal.

| Case | Authored setup and observation |
| --- | --- |
| Ordinary changed mtime | Preopened `FILE_WRITE_ATTRIBUTES` handle actually sets last-write time; ordinary content-edit time request refuses. |
| Explicit preserve mtime | Same actual actor/time setter with explicit original-time request; refuses. |
| Noncanonical ACL and owner | Actual initial owner is captured before DACL-only setup and verified unchanged through setup and refusal, with an explicit allow ACE before a deny ACE. Binary owner SID identity is compared independently of SDDL aliases and the process user; exact descriptor bytes and SDDL order are also inventoried. No ownership reassignment or privilege capability is claimed. |
| Stream content | An authored named stream contains exact nontext bytes; default and all enumerated stream content are compared, not lengths alone. |
| Readonly | Actual readonly target refuses without an attribute reset. |
| Extra hardlink | Actual second name/identity/link count remains retained. |
| Reparse | Ordinary-token directory junction at the target name refuses; its referent remains. |
| Mandatory label | Actual low-integrity mandatory label is installed on the authored target without privilege adjustment. |
| Unsupported SACL | Actual query availability/error is recorded; unsupported refusal supplies no complete SACL preservation or recovery assertion. No audit ACE is installed. |
| Preopened security actor | Retained `WRITE_DAC` handle actually changes the authored DACL through `SetKernelObjectSecurity` before refusal. |
| Preopened stream writer | Retained named-stream write handle actually performs an equal-length content edit before refusal. |
| Preopened link actor | DELETE/attribute-capable handle remains open while `CreateHardLinkW` actually creates an alias by name before refusal; the name-based setter does not consume that retained handle. |

The private evidence retains before/after directory entries, volume/file IDs,
link counts, attributes, creation/write times, exact owner/group/DACL descriptor
bytes and SDDL, observed label and SACL availability, reparse tags, and every
enumerated stream's exact content and SHA-256. Access/change times remain visible
but are excluded from the preservation assertion. The independent audit can
recompute equality directly from these retained records and fixtures.

Windows may assign the creator's default group as owner and render well-known
SIDs using SDDL aliases. The harness therefore observes the descriptor's actual
owner SID; it does not assume that owner equals the current process user. Pure
authored descriptor controls verify that `BA`/`S-1-5-32-544` and
`SY`/`S-1-5-18` identify the same respective owners while distinct owner SIDs
remain distinct. No owner setter or privilege change is used to make fixtures
match the process account.

Passing this finite matrix establishes that this refusal performs no observed
target/candidate/property/namespace mutation for those authored schedules. It
does not demonstrate exclusion of the actors, complete property backup, positive
replacement or recovery. No existing-target production storage profile, #0194
replacement, #0198 retention, occupied-name restoration, RAW/format admission,
durable commitment or grouped-operation permission follows. The strict original
scope remains intact; no narrower property policy is selected here.

Build and run the reproducible driver with a new private output directory:

```text
cargo test --manifest-path crates/imageinfo-windows-storage/Cargo.toml
cargo build --manifest-path crates/imageinfo-windows-storage/Cargo.toml --example existing_properties_probe
python crates/imageinfo-windows-storage/tests/existing_properties_native.py --probe crates/imageinfo-windows-storage/target/debug/examples/existing_properties_probe.exe --output .local/196-new-native-run
```

The integration handoff records the exact run and independent contract/API/actor
review. No VM, power, NMI, raw-device, real-media or privileged experiment is part
of this qualification.

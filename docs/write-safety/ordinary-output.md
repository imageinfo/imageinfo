# Option A live ordinary-owner output protocol

Implemented as research directly under **#0022**, observed **2026-10-14**. Terry's
[OD-11 option A](practical-output-policy.md) is accepted. This increment implements
its live byte/name/property/output-policy cells without enabling a writer/profile.

## Actual behavior

The [existing #0032 binary](../../experiments/0032-windows-publication/README.md)
now has separate `ordinary*` modes. It prepares a fresh private marker root, opens
the existing 64 KiB authored source read-only, creates an ordinary private-owner
candidate, and copies exactly the planned bytes. Source/candidate/name/ancestor
holds continue across the conditional held-object rename and installed checks.
No stronger sealed DACL, release setter, source policy rewrite or privileged helper
is part of the worker. This is a marker copy/publication protocol, not a CR3 edit.

| Cell | Actual observation |
| --- | --- |
| New source/candidate data write, delete or rename | Refused while held; validated byte/name bindings remain. |
| Preexisting writable handle or writable mapping | Source guard acquisition refuses before staging; read-only mapping is compatible. |
| Late hard-link alias data write | Alias creation is allowed by the owner policy, but default-data write refuses; observed link change refuses publication. |
| Root rename | Held ancestry/root sharing refuses the move. |
| Time/readonly/ADS/link/DACL change before property check | Observation detects the relevant mismatch; no publication. |
| Time change between pre-check and call / after publication | Complete output may exist; installed check fails and recovery-required is reported. This does not claim continuous property exclusion. |
| Foreign winner | No overwrite; owned candidate/records retained and call uncertainty reported. |
| Cooperative cancellation before namespace attempt | Only checked live owned files are marked/closed; source and root remain. |
| Kill or injected failure / cancellation after attempt | Actual artifacts retained; no fabricated terminal kill report, rollback or committed result. |
| Normal owner after exit | Read/data/time editing succeeds under ordinary private-owner policy. Later changes become restart conflicts. |
| Restart inspection | Fixed bounded records and actual source/candidate/output bindings are compared read-only; matching output remains recovery-required. |

`publicationCallSucceeded` records the API return. `installedCheckPassed` records
the distinct installed verification checkpoint. Neither means a durable committed
operation; `namespaceAcknowledged`, `committed`, `repairAllowed` and production
publication permission remain false. Checksums establish integrity observations,
not automatic repair authority or secrecy/key-management requirements.

## Evidence

The [64-case ledger](ordinary-output-observations.json) audits 64 worker captures,
56 unchanged before/after inspection inventories and **1,324 readable artifact paths**.
Two intentionally inaccessible marker paths remain without ACL repair. Paths include
hard-link/alternate-stream aliases; they are not unique object counts. Identifying
captures, object IDs, private paths and binaries remain local.

Two malformed producer-stream injections leave actual bounded partial candidates
and truthful pending-work reports before an owned-artifact constructor can return.
These are not native disk-full/device-error observations.

Three new portable record tests cover exact scope, path/permission claims, unknown/
duplicate fields, checksum/identity/link/size rejection. With five existing inspector
and ten reused staging tests, the research crate has **18 portable tests**. The
original **78 publication** and **35 restart-inspection** regressions pass. Root
format/Clippy/44 Windows tests/release and research format/Clippy/tests/release pass.
Python syntax, public docs/link/JSON and diff checks accompany [source CI](ordinary-output-ci.json).

Local native profile: Windows 11 Pro x64 **10.0.26200**, local NTFS, existing DOS
namespace/current token. One Windows profile is not a universal Windows or Unix
claim. Shared SDK and disposition source, Cargo manifests/locks and root unsafe
policy are unchanged. [#0036's 27-package/30-notice admission](windows-inspection-dependencies.json)
is reused; no new package, feature or native API is added. The existing
[#0032](../../experiments/0032-windows-publication/ffi-review.md) and
[#0038](../../experiments/0038-staging-cleanup/ffi-review.md) reviews cover the reused
boundary. New protocol/records use safe Rust and ordinary standard/serde types.

## Remaining qualification

[Windows guest work](windows-guest.md) now records eight NMI bugchecks followed by
controlled emulator restarts and eight separate SIGKILL/restart cases. The output
name is absent after the NMI at the successful-publication checkpoint, while other
late cells retain a matching output; all remain recovery-required. These measured
restart methods are distinct from the preliminary stalled warm reset and from
physical power loss. Linux guest evidence cannot stand in for this sequence. Physical power loss is
unverified. Qualified namespace/receipt persistence and safe restart finalization/
prune remain gated. Current RAW admission still refuses under #0027; #0023 is not
enabled. #0022's full scope is retained, rather than marked complete from the live
marker observations alone. Source/candidate properties are observed at declared
boundaries under OD-11; no continuous same-owner property exclusion is advertised.

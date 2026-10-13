# Windows OWNER RIGHTS property and alias guard observations

**#0033**, observed **2026-10-13**, resumed from #0014 through #0022 under Terry's
existing split authorization. [The marker experiment](../../experiments/0033-owner-rights/README.md)
qualifies a concrete fresh-artifact guard improvement. **No complete storage profile,
production writer, ordinary output-policy change or automated recovery is enabled.**
No RAW input or original/source ACL is changed.

## What the new mechanism establishes

The prior [#0032 owner-only policy](bound-windows-publication.md) leaves time, security,
link and alternate-stream changes possible. OWNER RIGHTS restrictions supplied at
fresh creation deny ordinary new attribute/security/owner opens and hard-link creation.
The property-only version still permits a new alternate data stream. A stronger
descriptor also denies new data/append opens, closing that measured ADS route while
the creating holder still writes its marker and publishes the actual held object.

The stronger policy's guarded cases retain all observed content, identity, exact
owner/DACL policy, last-write time, attributes, default-stream-only inventory and
one-link topology. Compatible readers remain allowed. The marker candidate is
renamed under held ordinary ancestry into an exclusively created private root with
no replacement; file and directory flush calls return. Winning external names are
retained, and before/after kill/cancel cases record actual presence rather than a
false committed receipt.

These observations apply to **newly created owned artifacts** during the tested
held interval. An unrelated time or security handle acquired **before** a later seal
still acts after the seal; a newly opened counterpart refuses. The original source
cannot inherit this guard without changing its existing property policy, which this
experiment does not do. After-open descriptor comparison also records a mismatch
against the exact fresh-creation policy; it is not silently normalized away.

## Measured capability cells

| Cell | Actual result | Limit |
| --- | --- | --- |
| Ordinary owner-only creation | Reads allowed; time/readonly/DACL/owner-access/ADS/link actors succeed; data write/delete/rename denied by held sharing. | Reproduces the older property gap. First narrower DACL actor was corrected to request control/read rights; final actual mutation succeeds. |
| Fresh property/security restriction | Time, readonly, DACL/owner access and hard link refuse with access denied. Compatible read succeeds. | ADS creation still succeeds and stream inventory/mtime change; not a full property guard. |
| Fresh sealed data/property restriction | New time/attribute/security/owner/data/ADS/link actors refuse; compatible read and creator write/flush succeed. | One ordinary-token/local-NTFS mechanism, not a complete RAW backend or hostile privileged-user proof. |
| Held sealed publication | Source/candidate identity and bytes remain held; restricted installed policy matches; compatible reader succeeds; late ADS/link/time actor refuses. | API/ordinary namespace observations only. Source guards, receipt custody and physical persistence remain separate. |
| Existing actor handles | Preopened time and DACL actors succeed after later sealing; new counterparts refuse. | Sealing an already exposed source/stage cannot retroactively revoke those handles. No source ACL is altered here. |
| Post-exit property-only policy | Data and ADS become writable after the holder exits; time/owner/link still refuse. | Sharing lifetime is not persistent content protection. |
| Post-exit sealed policy | Read succeeds; data/ADS/time/owner/link opens refuse. | Ordinary owner editing/permission restoration is constrained. This is not silently adopted as the product's output or restore policy. |
| Holder security restoration | Explicit retained-security attempt does not restore the ordinary descriptor in the measured fresh-restricted case. | No supported unseal/restart finalization protocol; no elevation or broad ACL repair is used. |
| Collision and interruption | Existing winner retained; kill/cancel before publication leaves no output, after visibility retains full authored candidate. | Process-only evidence, not OS crash/power loss or committed metadata work. |
| Complete-profile query | Refuses before artifact effects with explicit existing-source, authenticated restart-custody and qualified namespace/receipt cells. | No support inferred from accepted research tickets or a passing ACL/share/flush test. |

Private-owner protection, write-sharing, OWNER RIGHTS deny, link protection, namespace
publication, source exclusion and restart authority are separate cells. The new
mechanism improves the fresh-artifact cell; it does not close all of WS-009/010/011/
013/014/015/023/024, SAF criteria or GAP-004/GAP-009.

## Evidence, resources and provenance

The [sanitized 66-case ledger](owner-rights-observations.json) includes ordinary,
property-restricted, minimal-access and sealed actors; preexisting handles; post-exit
effects; held publication; collisions; kill/cancel; strict admission and namespace
grammar exclusions. The final audit checks **60 worker captures**, **442 readable
artifact hashes**, **six alternate streams**, and retains/reports **two deliberately
inaccessible marker artifacts** without changing their ACLs to obtain a hash.
No SID, object ID, machine path, camera bytes or raw capture is published.

The local worker is Rust 1.99.0, Windows 11 x64 build 26200, ordinary local NTFS and
an unchanged DOS namespace. Same-user actors use ordinary existing tokens; no
privilege/owner/mount/system changes occur. Each worker has a 90-second watchdog;
control/actor waits are 30 seconds and controls are 32 bytes. Marker contents are
64 KiB; SDK stream/security buffers retain their existing bounds. Hard interruptible
native I/O/complete OS quotas and other providers/hardware are unverified.

The [native/actor review](../../experiments/0033-owner-rights/ffi-review.md) covers fixed
OWNER RIGHTS policies, desired-access parameterization and protected DACL application
to newly owned marker handles. It reuses the project-owned #0032 boundary and
preserves its ordinary constructor/access mask. Its original **78-case Windows
publication regression passes**, including the existing explicit unsupported cells.
Root formatting/Clippy/36 tests/release and both research crates' format/lint/test/
release gates passed locally. [Platform CI](owner-rights-ci.json) separately binds
the source; other platforms refuse this Windows probe before worker artifacts.

The [14-package/15-notice admission](owner-rights-dependencies.json) reuses exact
previously reviewed registry archives and retained SDK/serde notices. Root production
dependencies/lockfile and unsafe policy are unchanged. No upstream implementation,
personal fixture or assembled executable is imported/distributed. All marker/capture
attempts remain local, including corrected hypotheses and inaccessible artifacts.

## Remaining enablement work

#0014/#0022 remain open. Existing immutable source/path/property handling,
authenticated restart custody, actual guarded finalization/cleanup, Windows OS-crash/
namespace/receipt and hardware-survival evidence are not supplied by this increment.
The sealed artifact's post-exit read-only/security behavior requires an evidenced
operational/output policy before adoption; no weaker product promise is assumed.
Actual date mutations also remain refused by [#0027](write-admission.md)'s opaque/
checksum dependency gate. #0023 cannot start an enabled operation from these
mechanism observations alone. Broader XMP/privacy/replacement gates remain intact.

This scoped handoff qualifies fresh-marker property/link exclusion and records the
remaining counterexamples/unsupported cells. It does not claim the parent backend
is complete. Primary OWNER RIGHTS/API references, observation date and exact SDK
version are in the linked boundary review.

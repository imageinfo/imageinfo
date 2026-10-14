# OD-11: practical new-output concurrency and property boundary

**Option A accepted by Terry in chat, 2026-10-14, #0041 under #0022.**
This accepts the product-policy boundary, not an implementation or enabled profile.
The existing [WS requirements](README.md), [SAF scenarios](acceptance-scenarios.md)
now record this scoped refinement; all other requirements and production mutation
refusals remain in force. Terry explicitly selected the recommended A answer.

## Decision

**Selected option A:** for new outputs, require proven protection of the file's
default-stream bytes, object/path bindings and conditional no-clobber publication;
use ordinary private-owner editable outputs, with filesystem properties checked at
declared boundaries. Treat the account owner as trusted to change those properties.
Do not promise continuous exclusion of same-owner timestamp, ACL, alternate-stream
or link-topology changes between observations.

This is a narrower property-concurrency promise than #0022's previous continuous
exclusion acceptance. It is not permission to replace a source, publish corrupted
bytes, skip format admission, trust a record blindly or omit required persistence.

| Choice | User-visible result | Work authorized by that choice |
| --- | --- | --- |
| **A — ordinary editable output, selected** | Owner can edit the new file normally. Default-stream integrity and no-clobber names remain mandatory. Same-owner property changes are checked at boundaries, not continuously excluded. | Update the affected requirements/scenarios, then implement and qualify one bounded new-output marker protocol under this promise. |
| **B — continuous property exclusion, not selected** | Would keep refusing profiles until byte, name and relevant property exclusion plus ordinary editable-output behavior were demonstrated together. | Would retain the previous property-exclusion acceptance. Existing research does not supply a working strategy or a delivery estimate. |

The decision selects no encryption, receipt keys, source ACL mutation, privileged
helper or new runtime framework. It authorizes no additional privileges or security
setting changes.

## Why the decision is now concrete

Primary project observations, all retained separately from production support:

- [#0033, 2026-10-13](owner-rights.md): a fresh strong descriptor blocks measured
  property/stream actors, but files remain editing-restricted after creator exit.
  Handles opened before a later seal can still act. The policy cannot simply be
  applied to an already exposed source without changing its properties.
- [#0034, 2026-10-13](source-oplocks.md): time/readonly/ADS/new-link actors bypass
  each tested sharing/oplock request without a break, while other operations have
  different sharing/break behavior. An unbroken oplock does not prove all properties
  stayed unchanged. This is a bounded result, not an impossibility theorem.
- [#0039, 2026-10-13](output-release.md): creator-held sealed release returns actual
  access denied with requested WRITE_DAC or full control. The unsealed control's
  setter succeeds but fails the exact descriptor check. Neither result qualifies
  ordinary editable output; no check was weakened to make it pass.
- [#0040, 2026-10-14](staging-limits.md): portable logical-byte preflight/copy bounds
  and existing live cancellation now have evidence. Those cells do not resolve
  the property/output-policy conflict or complete the storage backend.

These failures justify choosing a product boundary before further implementation.
They do not prove that every other API, filesystem or platform strategy must fail.
The ordinary owner's property edits are distinct from imageinfo preserving the
requested media bytes, which remains mandatory.

## Accepted option A, precisely

1. **New output only.** Never replace/delete the original or silently choose a
   sidecar. Existing-file replacement, source removal and rollback remain separate
   unsupported operations until independently qualified.
2. **Guard bytes and names.** Bind sources, candidate and destination parents to
   actual objects. Required default-stream content/name exclusion must hold across
   the publication interval. A hash/check followed by rename cannot substitute for
   that guarantee. Refuse a platform/profile that cannot provide it. Immutable input
   copies do not automatically solve obtaining a consistent source snapshot.
3. **Check relevant properties.** Declare planned property values and check them
   at preflight, immediately before publication and at installed-output verification.
   Detected changes cause conflict before publication or recovery-required afterward.
   This does not promise detection of an edit/reversion between checks, prevent a
   later property edit or make several observations an atomic snapshot.
4. **Ordinary private-owner output.** Create an owner-editable output with a
   documented private policy. Do not adopt the sealed research descriptor. Do not
   silently inherit broad permissions or copy source ACLs, ownership or filesystem
   streams. Explicit requests to carry unsupported properties/streams refuse.
   Other same-owner processes can alter properties; protection against that is
   outside option A's promise. Readers/different accounts remain subject to the
   declared ordinary filesystem permissions.
5. **Preserve the hard publication boundary.** Publish only the validated held
   candidate, conditionally on destination absence. A foreign winner remains intact.
   No path-based copy/delete fallback may claim atomic visibility or no-clobber.
6. **Keep persistence and outcomes unchanged.** Candidate/current-phase record,
   namespace and final receipt acknowledgements still need a supported protocol.
   API success alone never means committed. Missing/failed acknowledgements or
   uncertain publication remain recovery-required with artifacts retained. This
   decision does not relax OS-crash/power-loss evidence or invent a weaker success code.
7. **Keep recovery conservative.** Validate record integrity, actual identities
   and ownership. Read-only inspection stays available; uncertainty grants no
   replay, rollback, pruning or pathname/pattern deletion authority. No secret key
   is inferred from an integrity check.
8. **Enable only evidenced formats/profiles.** RAW preservation and opaque/checksum/
   authenticity admission remain independent. #0027 still refuses current real-camera
   mutations. One Windows result never qualifies Linux/macOS, mounted/network/cloud
   locations, existing-target replacement or other RAW variants.

The intended product explanation is plain: imageinfo protects the planned file
contents and avoids overwriting another file; normal account-owner property edits
are checked at defined points, not prevented as a security boundary. Exact wording
would accompany a qualified profile before any user could select or rely on it.
No new CLI switch or settings scheme is selected here.

## Requirement and scenario impact

| Contract | Accepted scope, reflected in the linked WS/SAF text |
| --- | --- |
| WS-002/009 | Name the relevant property read set and check boundaries; retain continuous default-stream/object/path guards. Explicitly exclude continuous same-owner property exclusion for this new-output policy. |
| WS-010 | Retain path/reparse checks, alias handling and conditional no-clobber names. Observed unexpected link topology refuses; do not claim topology cannot change between checks. |
| WS-011 | State the ordinary owner-editable private new-output policy and supported property set. Source properties stay untouched; requested unsupported preservation still refuses. |
| WS-013/014/015/019 | No relaxation of phase-specific persistence, verified installed bytes, owned recovery/cleanup or refusal on uncertainty. |
| WS-006–008/020/021 | No relaxation of format admission, sensor/opaque preservation, privacy or authenticity gates. |
| WS-016/022/023/024 | Keep cancellation, truthful partial/uncertain reports, resource bounds and per-profile qualification. Logical-byte evidence does not reserve disk space or enable a backend. |
| SAF-005/006/007 | Separate default-data/name substitution from property-only actors, with explicit new-output applicability. Boundary comparisons cannot be reported as continuous property exclusion. Runtime qualification remains pending. |
| SAF-008/009/015/016 | Keep disk/flush/interruption/recovery/unsupported-profile outcomes and evidence gates. |

Terry's explicit A answer supplies the policy decision required by WS-009. Acceptance
of earlier research alone did not supply it. Neither the answer nor this requirement
update establishes backend implementation or passing runtime qualification.

## Bounded implementation handoff

The affected requirements and concrete acceptance cases now record A. Next qualify
a disposable marker protocol using ordinary output permissions and
existing held-object publication where supported. Its minimum evidence cells are:

| ID | Evidence required before a profile could be admitted |
| --- | --- |
| OD-11-T01 | Byte/name substitution, alias and foreign-destination actors cannot publish an unvalidated object or overwrite a winner. |
| OD-11-T02 | Actual output retains the private owner-editable policy and is ordinarily editable after exit; no original/source property is changed. |
| OD-11-T03 | Relevant property changes at each observation boundary give the stated conflict/uncertainty outcome; between-check effects are explicitly outside the continuous-exclusion claim. |
| OD-11-T04 | Short/overlong/erroring staging, full disk and failed prepublication flushes do not publish; distinguish injected protocol errors from native OS errors. |
| OD-11-T05 | Every publication/namespace/receipt interruption has actual restart evidence; no fabricated committed result, automatic replay or deletion. |
| OD-11-T06 | Same bytes/ownership checks precede any safe finalization/cleanup; foreign, missing, corrupt or inaccessible artifacts remain retained/refused. |
| OD-11-T07 | Exact OS/build/filesystem/storage assumptions and persistence qualification are recorded separately for each claimed adapter. Passing source/unit tests is insufficient. |
| OD-11-T08 | Required RAW admission remains refused until its independent format gates pass. A passing marker protocol alone cannot enable #0023. |

Any new experimental mechanism must have a concrete hypothesis and scope; the existing
failed setter/oplock tests do not need repeating to reconfirm the same results.

## Verification of this decision package

The evidence-to-requirement mapping and follow-up cases were checked against the
linked primary project reports, WS-001–024 and SAF-005–009/015/016. Internal links,
status/command consistency, public JSON and `git diff --check` pass. There is no
runtime/dependency change, imported artifact or new platform experiment. WS-009/010/
011 and SAF-005/006/007 now reflect the explicit decision; other normative WS text
and the model/JSON cases are unchanged. No storage or format support claim is added.

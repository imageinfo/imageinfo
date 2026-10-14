# RAW mutation acceptance scenarios

Status: baseline acceptance criteria **2026-10-10**, refined by Terry's accepted
[OD-11 option A](practical-output-policy.md) on **2026-10-14**. These scenarios require a
future writer, lawful media and tested storage profiles. **None has run on RAW
media or a filesystem backend.** The separate [JSON cases](scenarios.v1.json)
exercise the abstract state/value rules only.

The [#0021 candidate experiment](new-output-preservation.md), observed 2026-10-11,
adds real private fixed-width preservation/RAW-unpack evidence and disposable
storage boundary probes. It completes none of the full SAF scenarios below;
publication, recovery, properties, signatures and broader operations remain separate
gates. The statement above describes the original #0006 baseline, not absence of
all subsequent experimentation.

Every successful mutation below must satisfy WS-001 through WS-024 as applicable.
Retain before/after identities, planned effects, preservation maps, diagnostics,
recovery artifacts and independent evidence using the [fixture plan](../fixture-plan/README.md).
Refusal cases assert no imageinfo publication, not that another process could not
have changed a file.

| ID | Setup and action | Required outcome | Rules | Fixture families |
| --- | --- | --- | --- | --- |
| SAF-001 | Preview an EOS R5 full RAW caption change; save a plan if requested. Try an imported plan with fabricated capability/authorization fields. | No target mutation. The requested plan is the only new artifact. Application recomputes trust/capability checks; imported fields do not authorize a write. | WS-001, WS-002, WS-003, WS-006 | FXP-018, FXP-023 |
| SAF-002 | Edit/create a paired XMP label, including an absent value and an already equal value. | RAW bytes remain identical. Existing XMP retains unselected data; creation uses an explicit path and property policy. A valid no-op creates no backup and does not rewrite XMP. | WS-004, WS-005, WS-011 | FXP-016 |
| SAF-003 | Change eligible CR3 EXIF/GPS/XMP with growth and shrinkage around maker notes, padding, previews and opaque blocks. | Sensor samples, additional required planes, calibration/CFA interpretation and unselected previews remain intact. All moved references remain valid. Unprovable opaque relocation refuses before publication. | WS-006, WS-007, WS-008 | FXP-018, FXP-019, FXP-020, FXP-021, FXP-022 |
| SAF-004 | Request a direct read-only CTMD edit, unsupported preview replacement, or an unverified C-RAW/DPRAW layout. | Specific unsupported outcome, no embedded change, and no silent sidecar fallback. Full RAW evidence does not enable secondary variants. | WS-006, WS-007 | FXP-021, FXP-022, FXP-027, FXP-028 |
| SAF-005 | Replace an input/copy source, stage or destination parent between planning, validation and publication; run an unrelated competing editor. Also change a relevant new-output filesystem property at each OD-11 check boundary. | Byte/object/path substitution must not publish an unvalidated object or overwrite a winner; refuse/conflict before publication or report recovery-required when publication may have occurred. Detected OD-11 property changes follow the same before/after outcome boundary; undetected same-owner property edits between observations are outside its continuous-exclusion promise. No stale overwrite or automatic recovery over an external version. | WS-002, WS-009, WS-014, WS-015 | FXP-023 |
| SAF-006 | Use a symlink/reparse target, multi-link file, case-folding collision or destination created after preview. For OD-11 new outputs, observe unexpected link topology at each required check. | Default link-policy refusal or evidenced explicit policy; conditional new-name collision refusal. No existence-check-only overwrite. Observed unexpected topology refuses/becomes uncertain at the publication boundary; continuous same-owner link exclusion is not inferred. Required byte/object/path guards remain effective. | WS-009, WS-010 | FXP-013, FXP-023, FXP-025 |
| SAF-007 | Edit read-only media or a file whose ACL/owner/streams cannot be preserved; compare ordinary and explicit preserve-mtime requests. Verify an OD-11 new output's declared private policy and ordinary owner editing after exit. | Required property failure refuses. Real edits update mtime by default; capture dates remain unaltered unless planned. Source properties stay unchanged; do not silently clone ACL/owner/streams. Unsupported explicit carry-through refuses. New output must be private and ordinarily owner-editable, with declared boundary checks rather than continuous same-owner property exclusion. | WS-009, WS-011, WS-023 | FXP-013, FXP-023 |
| SAF-008 | Exhaust space, corrupt a candidate, fail a recovery copy or fail each prepublication flush. Repeat with no-backup selected. | No target publication; retain required recovery artifacts. No-backup never skips temporary original recovery or scratch-space checks. | WS-008, WS-012, WS-013, WS-023 | FXP-022, FXP-023 |
| SAF-009 | Kill/cancel before, during and after publication; fail installed checks, namespace persistence and receipt persistence separately. | Earlier cancellation does not publish. Ambiguous later states need recovery. Recovery inspects actual identities and can establish original or finish a proven commit; it never guesses a rollback. | WS-013, WS-014, WS-015, WS-016, WS-024 | FXP-023 |
| SAF-010 | Commit the RAW member, then fail the paired XMP member; resume an append after an interrupted batch. | Report partial pairing and each member's actual outcome. Do not continue broken dependencies. Skip a matching committed receipt; never append twice or reuse a receipt after an external edit. | WS-004, WS-017, WS-022 | FXP-016, FXP-017, FXP-023 |
| SAF-011 | Rename a RAW/XMP pair, a case-only name, a rename cycle, and a cross-volume move; fail destination publication or source removal. | Explicit collision-safe plan. Cross-volume workflow is not advertised as atomic. Unsafe source removal leaves verified destination plus source and reports partial work. | WS-010, WS-017, WS-018, WS-022 | FXP-025 |
| SAF-012 | Restore over a later edited target; prune a backup still needed for recovery or a path injected into an untrusted record. | Restore needs a fresh plan and preserves the current version by default. Refuse in-use/unowned prune targets and arbitrary recovery paths. | WS-012, WS-015, WS-019 | FXP-023, FXP-025 |
| SAF-013 | Scrub sidecar location while RAW duplicates, embedded previews or opaque blocks may retain it; keep an original backup. | Report exact checked/removed/residual/unknown coverage and retained copies. Never certify whole-photo anonymization or secure erasure. | WS-007, WS-020, WS-022 | FXP-024 |
| SAF-014 | Encounter a known signature/provenance structure affected by the proposed change. | Refuse until a verified preservation or explicit invalidation workflow exists. Do not silently strip the structure or claim signature validity. | WS-006, WS-021 | FXP-022, FXP-024 |
| SAF-015 | Fail cleanup after a fully verified commit; restart with incomplete, foreign or inaccessible recovery records. | Report committed plus pending cleanup when justified; otherwise preserve uncertainty. Do not repeat the edit or delete artifacts by filename pattern. | WS-015, WS-022, WS-023 | FXP-023 |
| SAF-016 | Attempt replacement on an unverified storage profile, including a network/cloud/removable location. | Refuse before publication or offer an explicit independently supported output workflow. Simulation or one successful write never enables a profile. | WS-006, WS-009, WS-024 | FXP-013, FXP-023 |

Mutation success and a correct refusal are different capability claims. Likewise,
passing these criteria for one tag/layout is not blanket CR3 write support. Exact
tag/location coverage, each privacy profile's field catalog, and independent
runtime proofs remain implementation/evidence work.

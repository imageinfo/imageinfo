# Retained-original resource admission

The disabled internal resource seam now charges a complete one-member or two-member retained-original plan through the same explicit caller ledger as new-output work. No replacement, restore, stream-copy implementation or storage profile is admitted by this accounting change.

## Fixed table

Each member uses this finite precommit table. All numbers are logical bytes; the selected bounded caller supplies known extents before construction.

| Row | Charge |
| --- | --- |
| Candidate default stream | Exact known candidate length |
| Candidate supported streams | Sum of all extents in the complete supported inventory, at most 16 |
| Original private recovery default and supported streams | Exact complete original sum, for both keep and no-backup |
| Current-version preservation on restore | Exact complete current default/stream sum, in addition to recovery and restored candidate |
| Member records and caller captures | Eight slots of 65,536 bytes per member |
| Two-member manifest | One additional 65,536-byte slot |
| Shared caller-ledger entry | One additional 65,536-byte slot per attempt |

The eight member slots retain the existing four protocol-record and four caller-construction ceilings. A future retained-original protocol must fit its complete record/capture construction in those declared slots. A larger construction set requires a revised complete table and full precharge before starting; later extra charges cannot retroactively repair an incomplete plan. No serializer or retained-original protocol is admitted by this allowance. A two-member request charges both complete member rows atomically. The plan's record allowance is conservative and does not depend on the actual small records in a test.

Keep and no-backup have identical precommit peak charges. No-backup cannot omit the private original recovery copy before commitment. Restore adds current-version preservation; it does not overwrite that row with the historical original size. Retained preexisting recovery material must remain charged in the complete caller history as well; selecting it again never refunds earlier charges.

Unknown default sizes, incomplete stream inventories, unreadable stream extents, more than sixteen streams, unsupported member counts and checked arithmetic overflow refuse before availability queries or construction. The same selected private staging volume must have an advisory available-byte result covering all precommit rows. Missing or insufficient required private recovery space refuses. Separate-volume layouts require separately bound availability checks and are outside this seam.

## Shared cumulative owner

The new plan uses `RetainedSession::attempt`; it does not create another allocator. The ledger charges the entire plan and its entry before copying ledger identities, checking availability or invoking the constructor. Failed copies, storage refusals, cancelled attempts and successful attempts retain their complete charges. There is no refund, including after cleanup. Later requests see these charges, and exact complete move-only adoption preserves them.

The ledger retains terminal accounting state while actual runtime results remain caller-owned. A panic or uncertain construction leaves a nonterminal entry and refuses later work and adoption. This accounting state supplies no publication result or caller-custody authority. Imported records, directory listings and free-space observations cannot recreate the complete owner.

The callback is trusted crate implementation and has no replacement/publication authority of its own. Its future implementation must enforce exact copy extents, record ceilings, live object guards and the independent operation/profile gates. This change adds no public apply path.

## Verification

Six deterministic test groups cover the fixed replacement/restore/two-member table, equal backup choices, complete supported-stream sums, unknown/unreadable extents, stream/member bounds, overflow, exact limit and one byte over, availability failure, real partial copying to an authored failing writer, cancellation with retained partial material, shared extra constructions, repeated attempts, move-only adoption and panic refusal. The existing nine shared-ledger tests also pass, including actual native repeated-work and selected-parent availability checks.

One explicit ignored helper is reserved for a fresh authored 128 MiB NTFS secondary volume in the retained standard-user Windows evaluation guest. It performs ordinary bounded filling until the guest reports native error 112, then invokes the actual selected-parent native availability query through the shared resource admission. The one full-volume cell and its two successive admissions are recorded separately from injected backend errors. The [frozen-worker observations](retained-original-resources.json) record native Windows error 112 after 118,358,016 complete filler bytes. The native query then reported 16,384 available bytes against the 67,637,312-byte precommit availability threshold. Adding the 65,536-byte caller-ledger entry gives a 67,702,848-byte complete logical charge per attempt. No positive resource admission was executed before filling; the initial query is only an availability observation. Both admissions refused before the constructor and retained 135,405,696 bytes cumulatively. Exact authored source and current-original bytes survived; no operation directory or publication was created.

The retained capture audit passed. A separate read-only stopped-image audit verifies both authored byte strings, the absent operation directory and unchanged immutable original/previous-guest backing files. The guest was normally shut down and its helpers stopped. Guest launch/HTTP-parser startup failures remain explicit history; they were not worker attempts. The frozen worker has earlier documentation-comment spellings in the resource files; executable resource/helper behavior is identical to the current source.

## Limits

Logical accounting and advisory availability are neither free-space reservation nor a physical allocation quota. Other writers can consume space after the query; constructors must preserve truthful partial outcomes. The ledger is process-local, not a durable cross-process budget or automatic restart custody. The bounded guest volume does not qualify production storage, replacement, full filesystem-property copying, persistence, recovery or RAW mutation. No host or guest crash, VM-off or physical device test is part of this cell.

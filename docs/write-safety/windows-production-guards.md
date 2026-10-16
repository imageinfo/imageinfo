# Owned Windows storage primitive boundary

**#0166, 2026-10-16.**
[imageinfo-windows-storage](../../crates/imageinfo-windows-storage/src/lib.rs)
now supplies the safe owned-handle boundary required by the
[selected new-output contract](new-output-contract.md). It acquires a read-only
existing source and full ordinary DOS ancestry, exclusively creates a private
ordinary-owner root and bounded artifacts, observes exact bytes and properties,
flushes actual held objects, and publishes a held candidate once without replacing
an occupied name. The root library's unsafe prohibition remains; reviewed SDK
calls are isolated inside the separate crate. No storage profile, metadata writer,
restart action or committed result is admitted by these primitives.

Source byte/name guards exclude incompatible writer and delete access while held.
Directory guards share entry writes while excluding directory deletion/movement.
Source ACLs are observed, never rewritten. Private descriptor creation and returned
root handle are atomic. Complete source/artifact bytes and original property
snapshots are retained without rebasing; observed conflicts latch terminally.
Owner/DACL, attributes, creation/write times, streams and link topology are checked
at declared boundaries. Same-owner property exclusion between checks remains
outside option A. After all handles close, an ordinary owner can edit the output.
Dropping guards retains all artifacts, including failed/partial objects and roots.

Finite grammar and physical-object checks refuse wrong case/8.3 aliases, reparse
traversal, extra links/streams, case-sensitive directories, unsupported file types,
remote/removable-class/non-NTFS volumes, oversized bytes and compressed/encrypted/
offline containing-parent inheritance. Fixed-drive classification does not
establish an actual controller/bus/filter profile. Unsupported platforms/policy
conditions return typed refusal; native I/O errors keep their OS provenance.
The [SDK and ownership review](../../crates/imageinfo-windows-storage/SDK-REVIEW.md)
lists every native operation, exact package/features/notices and exceptional limits.

Actual Windows tests exercise competing data/name writers, a preopened writable
handle and writable mapping, no-clobber case winner, held identity, source
preservation, parent/ancestor rename refusal, alias/ADS/junction refusal, timestamp
edit/reversion, readonly and owner/DACL conflicts, failed-call retention, handle
release and ordinary owner editing. A test-only POSIX replacement actor refuses
with sharing violation under both read-only and delete-capable source access.
The mapping actor closes its original file handle before acquisition; both access
modes still refuse. A source ADS actor succeeds and its next checkpoint refuses,
while complete default bytes remain unchanged. Source ACLs are untouched.

The crate's four library and five native integration test functions pass locally;
the separate twelve [existing-object move](held-existing-move.md) functions also
pass against their owned module. Independent pathname reads audit retained actual
artifacts after release, and the external Python mapping/ADS actor retains its own
exact observation and byte checks. Formatting, Clippy with warnings denied and an
optimized build pass. Parent integration owns root checks and cross-platform CI;
no result is fabricated for an unrun platform/configuration.

These are finite native-host primitive observations, separate from the selected
evaluation guest and later actual protocol/profile evidence. No VM, crash, power,
media, privilege or production recovery operation runs. They supply neither
universal persistence nor independent RAW/XMP mutation admission.

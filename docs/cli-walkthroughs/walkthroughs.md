# User walkthroughs

All sessions below are **synthetic design walkthroughs**, revision `2026-10-10.1`.
Commands do not exist yet. File names and values are invented. Hypothetical success
assumes the exact reader/writer/storage/mapping capability has later been enabled
by evidence; the repository currently has no such implementation.

Text responses are intentionally concise mock output. JSON field meanings and exit
precedence are specified in [results](results.md). `status N` labels are annotations,
not output that would contaminate stdout. See [the recommendation](README.md) for
selection, pairing, grammar and menu rules.

## WALK-001 — Find out what is in a photo

```text
imageinfo

imageinfo — Inspect and manage camera RAW metadata.
Start: imageinfo metadata read photo.cr3
Explore: imageinfo metadata help
Guided mode: imageinfo interactive
Changes preview first; application must be explicit.
Groups: metadata, tags, formats, binary, sidecar, time, geo,
        files, privacy, validate, plan, recovery, backup, batch,
        compat, config, completion
```

Root help returns 0 without reading media. Its implemented command list must match
the installed release; the full list above illustrates the proposed eventual RAW
surface. Unavailable capabilities are marked planned, never offered as working edits.

```text
imageinfo metadata help

Read:   imageinfo metadata read photo.cr3
Review: imageinfo metadata diff before.cr3 after.cr3
Change: write, delete, copy, import, sync (preview first)
Report: export
More:   imageinfo metadata read help
```

```text
imageinfo metadata read help

Read metadata with original source and occurrence identity.
Usage: imageinfo metadata read [options] [--] <inputs...>
       imageinfo metadata read --files-from <manifest> [options]
--tag <name>                 Repeat to select registered names; default all.
--values raw|normalized|display|all  Default display; JSON retains identity/types.
--output text|table|json|jsonl       Default text.
--with-sidecars              Include uniquely paired XMP; default RAW only.
--recursive                 Recurse selected directories; default off.
--max-bytes <integer>        Cumulative input bytes; effective limit in config show.
--timeout <duration>         Total work time; units ms, s, m; effective default in config show.
--jobs <positive-integer>    Bound workers; effective default in config show.
--no-progress --no-pager     Plain output controls.
Effects: reads files; filesystem access times may change. No metadata edits.
Outputs: source-aware values; partial/unknown coverage is explicit.
Status: 0 success, 1 failed, 2 invalid request, 3 mixed results, 130 cancelled.
Examples: imageinfo metadata read --values all --output json photo.cr3
          imageinfo metadata read --with-sidecars photo.cr3
Topics: imageinfo tags help; imageinfo formats show CR3
```

This is a focused help mockup; a released leaf must also list every applicable
shared option, its effective default/units, and output-field descriptions. Root,
group and leaf have equivalent `help`/`--help` spellings under CW-002.

```text
imageinfo metadata read --tag EXIF:ISO --with-sidecars photo.cr3

photo.cr3 — Canon EOS R5 / full RAW (example)
EXIF:ISO = 100   [RAW / CMT EXIF / occurrence A]
EXIF:ISO = 100   [RAW / CTMD observation / occurrence B]
2 matches; no preferred occurrence selected.
Sidecar: photo.xmp
```

Status 0. The locations/values illustrate duplicate handling, not a claim about a
real R5 file. `tags show EXIF:ISO` explains the alias, native identities, value type
and location-specific restrictions. `formats show CR3` distinguishes read/write/
create/delete/preserve support and full RAW/C-RAW/DPRAW coverage.

A write to ambiguous `EXIF:ISO` returns `TAG_AMBIGUOUS`, status 1, and no publication.
The user can inspect occurrence paths and build an exact snapshot-bound intent
using CW-004. Absent under complete coverage, empty string and unavailable under
partial coverage appear as different results, never as the same blank cell.

## WALK-002 — Use cascading help without accidentally editing

```text
imageinfo interactive metadata write

Metadata > Write > Inputs
1. Choose an associated XMP
2. Choose supported embedded RAW metadata
Actions: help | back | cancel
```

Select 1, then the uniquely paired `photo.xmp`. At the tag screen, search Label and
open Help: it explains the canonical alias, XMP namespace/key, string type, existing
occurrence requirement and that only the sidecar is targeted. Back returns to the
same input/tag choices. Enter the literal value `Reviewed`, then choose Preview.

```text
Metadata > Write > Review
photo.xmp: XMP-xmp:Label
  Before: Draft
  After:  Reviewed
photo.cr3: unchanged
Original: retained after success

Command: imageinfo metadata write --set XMP-xmp:Label=Reviewed photo.xmp
Actions: Preview [default] | Apply | Save plan | Back | Cancel
```

This assumes one existing eligible label and a supported storage profile. The
exported command previews too; application is shown separately with `--apply`.
Applying is disabled until a current valid preview exists. Back, Help and Cancel
do not write metadata. Saving a plan writes only that explicitly requested artifact.
Changing the input invalidates the old preview and selected tag occurrence.

Test the same flow at 40 columns, without color, through arrows/Tab/Enter and
`--menu-style line`. Line mode uses numbered choices and a separate action prompt,
so a metadata value literally equal to `cancel` is still usable. Ctrl+C before Apply
returns 130 and changes no target. Menus keep drafts only in memory unless saved.

```text
imageinfo interactive metadata write --output json
```

With redirected stdout, this returns status 2 and `INTERACTION_REQUIRES_TTY`, with a
valid JSON error envelope if JSON output was selected. No file is inspected. A normal
noninteractive write preview works in the same environment without asking questions.

## WALK-003 — Export a batch for scripts

The UTF-8 manifest is relative to its own directory, not the process working directory:

```json
{"schemaVersion":1,"paths":["photo.cr3","bad.cr3","later.cr3"]}
```

```text
imageinfo metadata read --files-from collection.files.json --values all --output jsonl --on-error continue --no-interactive --no-progress
```

Assume `photo.cr3` and `later.cr3` are supported, while `bad.cr3` is unreadable.
The stream is request, read file, failed file, read file, summary, in manifest order.
The successful file records embed the metadata snapshot in `snapshot`; the failed
file has null there unless partial data was recovered. Counts are discovered 3,
read 2, failed 1; final status is 3. Errors also have bounded human stderr diagnostics.
No ANSI or progress text appears on stdout. Continue does not alter the request's
per-file identity or permit state to leak between inputs.

Use `--output-file inventory.jsonl` to request a new no-clobber report artifact.
For the mixed result above, report failure and retain any incomplete staging artifact
under its reported private name; do not publish a complete-looking final filename.
A fully successful run publishes the new output and returns 0. An existing final
path returns `DESTINATION_EXISTS`, status 1, without truncating it.

If stdout breaks or a resource budget expires, the stream may lack a final summary.
The consumer rejects it as incomplete. Budget failure can leave an earlier good
read record; that does not make the whole collection successful. Read-only retry is
possible, but mutation retry first consults durable batch/recovery records.

## WALK-004 — Safely edit a label and resolve a stale plan

Assume `photo.xmp` already contains exactly one string label and pairs uniquely
with `photo.cr3`. These single-quoted simple strings work as literal arguments in
PowerShell and ordinary POSIX shells:

```text
imageinfo metadata write --set 'XMP-xmp:Label=Ready for review' --save-plan label.plan.json photo.xmp
imageinfo plan show label.plan.json
imageinfo validate plan label.plan.json
```

Each returns 0 under these assumptions. The first saves a new plan without editing
media; an existing plan path is a collision. `plan show` includes exact destination,
old/new value, preserved original, property policy, applicable storage profile,
paired RAW unchanged and current plan revisions. Validate checks current applicability.

```text
imageinfo plan apply label.plan.json

photo.xmp: committed
photo.cr3: unchanged by this operation
Original retained: backup ID example-backup-1
1 destination committed; 0 failed
```

Status 0 after all WS checks. If the current label already equals the requested
text, the result is unchanged, with no rewrite or new backup. If another editor
changed `photo.xmp` after planning, application returns `PLAN_STALE`, status 4.
No imageinfo publication occurs; inspect the newer version and generate a fresh
plan instead of automatically overwriting it.

If embedded CR3 editing is unsupported, preview returns `CAPABILITY_UNSUPPORTED`,
status 1, with no applicable plan. If strict publication guards are unavailable,
return `STORAGE_PROFILE_UNVERIFIED`. Help may offer an explicitly supported sidecar
or new-output workflow; it must not silently choose one. These refusals currently
describe requirements, not tested capabilities.

For literal quoting differences, PowerShell can express `Terry's photo` as
`'XMP-xmp:Label=Terry''s photo'`; use a UTF-8 intent file when quoting is complex.
Both shells can use `--set 'XMP-xmp:Label='` for an empty string. Null and deletion
are different typed operations, not special strings. Literal filenames `help` or
`-photo.cr3` follow `--` and still undergo format/scope checks.

## WALK-005 — Remove sidecar GPS without claiming anonymity

```text
imageinfo privacy inspect --profile location --with-sidecars public-photo.cr3
imageinfo privacy scrub --profile location --target sidecar --save-plan privacy.plan.json public-photo.cr3
imageinfo plan apply privacy.plan.json
imageinfo privacy verify --profile location --with-sidecars public-photo.cr3 --output json
```

Assume a future versioned location profile and deletion-capable sidecar writer.
Inspection reports exact checked fields/occurrences, scope, residuals and unknown
regions; status 0 means inspection finished, not that the photo is private. Preview
lists deletion of supported sidecar GPS fields and preserves decoding-critical data.
It explicitly leaves RAW and embedded preview metadata unchanged, and retains an
original backup containing old location data. Apply can succeed with status 0 for
that scoped edit, alongside residual-information warnings.

Verification still finds RAW GPS or an uninspectable relevant region. It returns
status 1 for this input with `PRIVACY_RESIDUAL` or `PRIVACY_UNINSPECTABLE`, and states
that the requested verification did not pass. Retained originals are disclosed too.
Never offer a green “anonymous” summary, unconditional metadata wipe, or secure-erasure
promise. A missing paired XMP is reported; it is not treated as proof of deletion.
Actual profile field catalogs and media evidence remain #0014 work.

## WALK-006 — Reconcile RAW copyright into XMP

```text
imageinfo sidecar diff photo.cr3
imageinfo metadata sync --from photo.cr3 --tag EXIF:Copyright --mapping exif-copyright-to-xmp-rights-v1 photo.xmp
```

Diff reports RAW Copyright `Example Studio` and XMP dc:rights/x-default `Old credit`
as two values, without flattening them. Status 0 means comparison completed, not
that values match. Sync defaults to conflict error and returns `SYNC_CONFLICT`,
status 1, with no publication. The mapping and source selector are defined in CW-007.

```text
imageinfo metadata sync --from photo.cr3 --tag EXIF:Copyright --mapping exif-copyright-to-xmp-rights-v1 --conflict source --save-plan rights.plan.json photo.xmp
imageinfo plan apply rights.plan.json
```

Preview explicitly changes only the destination's x-default entry, retains any
other languages and preserves RAW bytes. Apply returns 0 only when this mapping's
requested effect and storage checks succeed. `--conflict destination` instead
reports skipped-policy; it may return 0 for that policy but must not claim the
unequal files are synchronized. Absent source text never deletes destination text.

If two RAW files claim one sidecar, return `PAIRING_AMBIGUOUS` before mutation.
An explicit association can be provided through `--pairing-file pairing.json`:

```json
{"schemaVersion":1,"pairs":[{"raw":"photo.cr3","sidecar":"photo.cr3.xmp"}]}
```

Missing sidecars require a separate `sidecar create --format xmp --to photo.xmp
photo.cr3` preview and explicit apply. Creation does not copy every RAW field unless
an explicit mapping was requested. Broad reverse or bidirectional synchronization
does not follow automatically from this one-way example.

## WALK-007 — Recover an interrupted write

Assume a hypothetical two-destination batch. The first commits; the second publishes
a candidate but its required persistence acknowledgement fails. The batch returns
5, even if cancellation was also requested. Durable records name both outcomes:

```text
photo.xmp: committed
other.xmp: recovery-required (example-txn-2)
Publication may have occurred. Original recovery material retained.
Next: imageinfo recovery show example-txn-2
```

```text
imageinfo recovery list
imageinfo recovery show example-txn-2
imageinfo recovery resolve example-txn-2
imageinfo recovery resolve --apply example-txn-2
```

List returns 0 when enumeration succeeds; it does not classify or repair records.
Show returns 5 if the inspected transaction remains uncertain. Resolve preview
returns 0 only if an eligible guarded resolution is established; it does not alter
the target or finalize the record. Applying may finish a proven installed candidate
without republishing, or record recovered-original when that state is established.
An external later edit remains untouched and returns 5 with unresolved evidence.

```text
imageinfo batch resume example-batch-1
imageinfo batch resume --apply example-batch-1
```

Resume previews eligible remaining units and verifies committed receipts. It must
not append twice. Unresolved transactions block the dependent group; changed completed
targets produce conflict, not skip-success. A recovered-original unit requires a
fresh applicable plan before retry, never implicit replay of the old mutation.

For a known backup, `backup restore example-backup-1 photo.xmp` previews a separate
restore, preserving the current version by default. `--apply` is explicit. Prune
requires selected backup IDs and refuses unresolved recovery material.

## WALK-008 — Ordinary mistakes and safe discovery

| Input/situation | Expected behavior |
| --- | --- |
| `imageinfo metadata wriet` | Status 2, `INVALID_COMMAND`, nearest `imageinfo metadata help`; suggest `write` without running it. |
| `imageinfo metadata write` | Status 2, `MISSING_ARGUMENT`, leaf help path; no prompt. |
| `imageinfo metadata write --apply --help` | Status 0, write help only; no media I/O. |
| `imageinfo metadata write --made-up --help` | Status 2, invalid-option diagnostic; no media I/O. |
| `imageinfo metadata read -- help` | Treat `help` as an input filename; perform ordinary file validation, not help dispatch. |
| `--dry-run` plus `--apply` | Whole-request status 2; no output artifact or media mutation. |
| No selected inputs | Status 1 with an empty-selection diagnostic, or 0 with explicit `--allow-empty`. |
| Duplicate scalar `--output` | Status 2; no last-option-wins surprise. |
| Settings profile plus privacy policy | Use `--config-profile work privacy inspect --profile location photo.cr3`; each name has one meaning. |
| Tab completion at a tag/operation | Show registered candidates; no mutation or mandatory network; unsupported candidates visibly unavailable. |
| Supported preview extraction with two matching assets | Require exact selection before binary bytes are emitted; no first-match guess. |
| Cancellation after one committed file | Status 130 and committed count retained; status 5 takes precedence if another unit needs recovery. |

These walkthroughs are ready for review as specifications. Keyboard/screen-reader
usability, actual shell invocation, format coverage, output schemas and platform
failure behavior still require implementation evidence before release.

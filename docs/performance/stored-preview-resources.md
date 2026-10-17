# Private stored-preview resource method

The #0145 method extends the [authored preview collector](preview-baseline.md)
with the existing [Windows direct-process telemetry](read-telemetry.md). Its
camera-derived protocols, captures, extracted bytes, reports, values, counts and
outcomes stay in ignored `.local` storage. This public document records the
method and authored tool checks only; it reports no camera result.

The [collector](../../scripts/measure_preview_resources_145.py) requires the exact
existing admitted full-RAW fixture, original private grant, restricted privacy
review, current derivative permission and prior extraction correctness. The
private protocol pins those evidence bytes, a frozen executable, its source/build
manifest, interpreter, collector, bounded process runner, telemetry helper and
auditors. Rights and evidence are checked before any media hashing. Three explicit
named resources bind independently retained reference bytes and historical source
ranges; complete stored extents include any padding. No JPEG or RAW decoding runs.

The fixed planned workload is listing, then explicit `ThumbnailImage`,
`PreviewImage` and `JpgFromRaw` extractions. Each operation retains two warmups and
ten measured attempts, using fresh owned output names. The ordinary CLI gets an
8 MiB metadata-read budget and a 64 MiB extraction budget; supervision retains
at most 4 MiB per pipe with a 30-second deadline and requested 10 ms telemetry.
These are experiment bounds, not product defaults. The parent serializes the
campaign against one final frozen executable. No retry, adaptive warming,
outlier removal or overlap with another timed campaign is allowed.

Elapsed time includes process startup, normal reading, complete pipe drains and
exit. Extraction includes its existing sync and publication sequence. Hashing,
extent checks, inventory and capture writes happen outside the timed attempt.
CPU, working set, lifetime peak working set, sampled private commit and logical
I/O retain the shared telemetry definitions and error dispositions. Logical I/O
is not device traffic; direct-child sampling is not containment. File lengths
measure logical bytes. Namespace observations before/after each attempt retain
temporary/final artifacts, including unexpected entries; they do not measure
transient scratch peaks or physical allocation. Those metrics remain unavailable.

The [independent audit](../../scripts/audit_preview_resources_145.py) recomputes
exact stored-range/reference/output equality, complete summary and effect checks,
source identity/hash/stat stability, namespace effects, capture accounting and
all-attempt telemetry arithmetic. Failed and censored attempts remain in the
ledger and cannot become eligible resource samples. Aborted runs retain attempted
cells and the remaining denominator, and invalidate all final eligibility.
Actual process outcomes enter the ledger before capture/namespace finalization;
later observation or storage faults retain available evidence and an explicit
finalization error. The audit also binds each separately retained attempt record,
exact argv/cwd, serialized monotonic starts/ends, UTC start order, complete exited
capture totals and censor dispositions.
Completed evidence must contain exactly the planned capture and per-attempt
record namespaces; missing or extra entries refuse audit. UTC attempt starts
must follow the protocol's fixed preregistration timestamp.
Success-conditional descriptive summaries are private. Original/copy sources are
never mutation targets; extracted outputs are retained separately.

Source hashing warm-exposes OS cache. Device cache and workstation background load
remain uncontrolled. These observations cannot select performance policy, qualify
broad preview layouts, establish directory/device persistence, certify JPEG
validity or enable a storage/mutation profile.

Run authored checks with `python -m unittest discover -s scripts -p
'test_preview_resources_145.py'`, alongside the existing preview, bounded process
and telemetry qualifications. Actual collection and retained-artifact audit use
`--run-root` pointing to a fresh, privately preregistered directory containing
`protocol.private.json`.

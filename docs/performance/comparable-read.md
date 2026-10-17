# One selected native/reference read method

Ticket **#0151** implements one private comparable-subset protocol. The public
deliverable is this method, its collector and permitted authored controls. Camera
values, counts, captures, timings, ratios, outcomes and statistics stay under ignored
`.local` with their existing restricted grants. This method supplies no public
camera result, broad compatibility claim or numerical superiority claim.

The [collector](../../scripts/measure_comparable_read_151.py) reuses the existing
[elapsed collector](read-collector.md), [Windows telemetry](read-telemetry.md) and
native oracle projection from the [resource method](read-resource-characterization.md).
The independently implemented
[correspondence auditor](../../scripts/audit_comparable_read_151.py) consumes the
retained bytes. No additional reference acquisition, importer or decoder is involved.

## Preregistration and selected semantics

Freeze one current native source/build and executable before collection. Keep the
archive manifest, lockfile/toolchain and build receipt private. Bind the collector,
auditor, existing ExifTool **13.59** source tree, installed Ubuntu Perl/runtime,
WSL launcher, configuration suppression evidence and exact historical reference
ledger. Recheck the existing tree/runtime bytes against that ledger; changed or
missing prerequisites refuse. A review of exact selected-field correspondence must
approve the particular source/oracle and reference argument list before collection.

At every prerequisite checkpoint, one fixed existing-Perl
[installed-file verifier](../../scripts/check_comparable_reference_151.pl) receives
the deduplicated historical file list as bounded JSON on stdin and returns indexed
SHA-256 hashes and lengths. It reads installed source/runtime files only. The
collector independently compares every returned row against the original manifest;
it retains the exact request, bounded stdout/stderr and outcome before refusal.
The verifier code and historical runtime inputs are pinned in the protocol. Its
1-MiB request, 4096-row limit, separate 512-KiB output prefixes and 60-second deadline
bound verification. Verification occurs outside measured intervals and its file
reads remain an explicit source of warm-cache exposure. A failed, cancelled or
incomplete verification cannot authorize media access or later attempts.
The campaign uses a fresh verification directory and links each actual checkpoint
record by name and hash in its retained manifest. A completed run has six ordered
successful boundaries: initial admission, initial source check, three round-ending
source checks and final admission. Preparation smoke checks cannot satisfy these
links; failed boundaries remain linked in aborted manifests.

Use exactly the first already admitted full-RAW input from the retained #0063
protocol, with its original grant, current restricted privacy review, revision-2
admission/provenance and passing native correctness oracle. A current task admission
allows private read-only analysis and forbids report publication and source mutation.
Check the rights/evidence bindings before source access. Hash/stat the same input
before the schedule and after every round; identity, size, timestamp or content
changes invalidate the run. These checks do not provide a continuous object guard.

Select the raw numeric `EXIF:ISO` view and require exact singleton occurrence
correspondence, its native CMT2 origin and declared partial coverage. Equal display
strings alone do not establish equivalence. The native consumer also checks the
complete projected native oracle envelope, retaining all unselected structure.
Duplicate/ambiguous reference keys, disagreement, missing fields or unsupported
value/coverage shapes refuse. Authored controls establish only their finite cases.

The fresh native process performs its complete bounded metadata read, including
container/metadata parsing, structural and safety checks, selection, raw and
normalized value construction, coverage, provenance, issues and full native JSON
envelope serialization. It does not stop after a tag lookup:

```text
imageinfo metadata read --values raw --output json --max-bytes 8388608 --tag EXIF:ISO -- INPUT
```

The reference process includes Windows WSL launch, existing Linux Perl/ExifTool
startup, its own metadata parsing/selection and numeric JSON serialization:

```text
wsl.exe --distribution Ubuntu --exec /usr/bin/perl -I EXISTING_LIBRARY EXISTING_EXIFTOOL -config "" -j -n -a -G0:1:4 -EXIF:ISO -- EXISTING_INPUT
```

The selected value is comparable only after the independent semantic audit. Parser,
runtime, startup, safety, coverage and serialized-envelope work differ. This is
neither equal-format JSON work nor full-tag, preview, mutation or decoder parity.
The WSL and Windows storage/runtime paths remain separately declared conditions.

## Fixed schedule and consumers

Preregister **three rounds**, each with **three warmup pairs** followed by **ten
measured pairs**. Every pair runs both tools serially. First-tool order alternates
globally, giving five native-first and five reference-first measured pairs in each
round. Keep every planned attempt, failure, partial capture and censored duration;
do not retry, trim outliers, replace failed pairs or adapt the order. Authorize one
exclusive measurement slot against reviewed frozen artifacts; avoid simultaneous
timing or VM campaigns. Record hardware, OS, power, load, storage, cache state and
unknowns privately. No cold-cache control or cross-runtime aggregate is inferred.

Each attempt has a 30-second deadline and separate 4-MiB bounded stdout/stderr
captures. The existing collector starts `perf_counter_ns` immediately before
`Popen` and ends after direct-process wait and pipe drain. It drains both outputs
concurrently; capture files and semantic parsing occur afterward. All launch,
polling, drains and observer overhead remain included. Every stdout/stderr byte
count, retained-prefix hash, outcome and censoring flag is retained. A process
launch failure, nonzero exit, stderr, deadline, overflow, consumer error or failed
correspondence prevents pair eligibility. Source/prerequisite drift invalidates
every pair. This research collector is not a journal or a resource sandbox.

Cancellation retains the started attempt and its bounded partial captures, then
stops the remaining schedule. A censored reference launch also stops the run:
killing its Windows launcher cannot establish Linux descendant exit. Such an
aborted run retains its fixed planned denominator and supplies no complete-round
ratio. No generic descendant cleanup or termination guarantee is claimed.

Native counters use the existing 10-ms requested Windows direct-process telemetry,
with actual observation brackets, failures and membership limits retained. CPU,
working set, private commit and logical I/O retain their documented separate units.
Physical I/O is unavailable. Reference counters are explicitly **unavailable**:
the Windows launcher has Linux descendants and no separately qualified membership
collector. Launcher PID counters must never stand in for the reference workload.
Native counter failure does not fabricate a zero or invalidate otherwise valid
elapsed/correspondence evidence; resource availability is audited separately.

After retaining the entire fixed schedule, the independent auditor checks exact
semantics for every pair before computing any statistic. Report the median paired
reference/native elapsed ratio separately for each round, with an explicitly named
uncertainty description. Keep failed/censored denominators and prevent a partial
selection from masquerading as the planned paired experiment. A ratio describes
these two complete producer-specific invocations under these recorded conditions;
it does not isolate parser speed or imply a general product policy. All such camera
statistics remain private.

```console
python scripts/measure_comparable_read_151.py --run-root PRIVATE_PREREGISTERED_ROOT
```

The runner prints no camera-derived results. Independent review, retained-output
audit and the original private rights continue to govern the handoff.

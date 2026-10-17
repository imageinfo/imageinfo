# Native reader structural boundaries (#0149)

The authored corpus exercises the current default parser budgets through actual
native reads: 4096 BMFF boxes, depth 16, 4096 TIFF entries per CMT parse, and
4096 timed records. This is finite structural qualification, separate from the
byte-budget cells and from the historical limit proposal.

`tests/structural_bounds_tests.rs` generates below/at/above cases for five scopes.
Each below/at input succeeds. Each above input refuses with the exact named
`LIMIT_EXCEEDED` error, then succeeds when only its relevant limit increases by
one. Those controls keep extents, storage types, source samples and unrelated
budgets valid, so the observations do not depend on error precedence.

| Scope | Below / at / above | Exact first refusal |
| --- | --- | --- |
| BMFF boxes | 4095 / 4096 / 4097 total scanned boxes | Before requesting box header index 4096 (zero based). |
| BMFF traversal depth | 15 / 16 / 17 parent path components | Traversal with parent path length 17, before reading its leaf. |
| TIFF depth | Last IFD at depth 15 / 16 / 17 | Before interpreting IFD depth 17; first IFD has depth zero. |
| TIFF entries per CMT parse | 4095 / 4096 / 4097 entries | The first IFD count 4097 refuses before entry iteration zero. |
| Timed records | 4095 / 4096 / 4097 valid 40-byte records | Before requesting record header index 4096. |

BMFF depth measures a traversal's parent path length. A noncontainer leaf may
therefore have 17 path components under limit 16. TIFF depth independently
measures directory links from depth zero, with a chain of 17 directories accepted
under the same numeric limit. Neither is a generic XML/XMP nesting limit.

TIFF entries accumulate across directories within one CMT parse. A separate
two-directory control accepts 2048+2048 entries and refuses 2048+2049. Another
positive control has 4096 CMT4 entries plus the ordinary entries in other CMTs;
the denominator is not the entire file. TIFF counts/depth are checked after the
bounded whole CMT block is read: these refusals do not prevent that block read.
The reader returns an error, without exposing a partial `Metadata` result.

The independent authored oracle walks encoded box extents, generated CMT4
directory offsets/counts, and the CTMD track's own sample tables and stored record
sizes/types through the exact sample end. Exported record extents independently
identify the first unrequested record header. The retained-resource audit repeats
these encoded walks independently in Python. The recording source retains every actual underlying
read request, offset and returned count. Tests check that a refused box/record
header was never requested, the precise preceding read, and the whole-CMT read
boundary for TIFF. Source byte slices remain unchanged. All inputs are public
authored structures, without camera photos or sensor data.

Hard configuration ceilings are separate tests: counts 65535/65536/65537 and
depth 63/64/65 use the small valid ordinary fixture. Supported configurations
succeed and above-ceiling configurations refuse before source access. These
tests do not saturate the hard counts/depth or qualify a hard-envelope resource
policy.

## Reproduction and resource collection

Export the deterministic corpus and request traces with:

```powershell
$env:IMAGEINFO_STRUCTURE_FIXTURE_DIR = "$PWD/.local/structure149/corpus"
cargo test --test structural_bounds_tests
```

Only after the final executable is frozen and the parent grants the serialized
measurement slot, run:

```powershell
python scripts/structural_boundary_campaign.py --binary ABSOLUTE_IMAGEINFO_EXE --corpus .local/structure149/corpus --output .local/structure149/campaign --repeats 3
python scripts/audit_structural_boundaries.py --record-dir .local/structure149/campaign --output .local/structure149/audit.json
```

The collector reuses the shared bounded process runner and Windows telemetry
observer, starts a fresh direct process for every attempt, selects `Make`, and
retains both output pipes, failure/refusal outcomes, timing and sampled resources.
The capture bound is 4 MiB per pipe with a 10-second direct-process deadline.
Selecting one occurrence still reports opaque resource ranges. The audit checks
exact finite expectations, diagnostics, complete envelopes, unchanged source
hashes/stat metadata and executable hash, explicit no-effects outcomes, and valid
resource observations. Failed, censored and unavailable observations stay in the
record and cannot become successful measurements.

The resource audit checks positive elapsed time, initial/final sample endpoints,
ordered bounded sample timestamps, actual nonnegative CPU/memory/logical-I/O
counters, counter errors, cumulative monotonicity, arithmetic sampled maxima and
observer overhead. Physical I/O alone remains explicitly unavailable. It binds
the process PID to the emitted request ID and validates executable, Python and
collector/observer hashes. Authored negative controls reject absent counters,
empty sample objects, missing final endpoints, errors, inconsistent maxima,
fabricated physical I/O and missing timing. Imported JSON consistency is evidence
checking, without an authenticity or arbitrary-import authorization claim.

Resource collection is prepared but not yet executed in this document's initial
preparation handoff. The parent records the frozen executable and actual audited
campaign before the ticket's final handoff. Preparation test timings are not
resource results.

Process logical-I/O counters include process work and output, while the recorded
source-read request sum is a separate exact parser observation. Neither measures
physical I/O. CPU and memory observations use the shared direct-child observer;
sampled maxima are not an allocation quota or containment. OS/device cache is
uncontrolled and preflight hashing warms source bytes. No generic fuzz
completeness, hard I/O deadline, all-allocation bound, production storage profile,
RAW write permission or performance default follows from these cells.

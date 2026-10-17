# Five current native CLI result profiles

Implemented qualification under **#0127**, observed **2026-10-17**. This package
narrows the existing [result envelope](result.schema.json) for five actual
operations. It changes no CLI, producer, importer or storage capability.

| Operation | Exact emitted-envelope schema | Actual evidence |
| --- | --- | --- |
| `metadata read` | [read v1](result-profiles/read.schema.v1.json) | Successful partial-coverage observation; unsupported-file refusal; mixed status 3; repeated operand deduplication; invalid rational with retained snapshot. |
| `binary list` | [list v1](result-profiles/list.schema.v1.json) | Successful binary-only occurrence selection; unsupported-file refusal; mixed status 3; repeated operand deduplication. |
| `binary extract` | [extract v1](result-profiles/extract.schema.v1.json) | Exact authored preview copy, dry run, unsupported source and occupied destination refusal. |
| `preview date-time-original` | [date-preview v1](result-profiles/date-preview.schema.v1.json) | Actual advisory byte-difference inspection with admission refusal; stale allocation assertion; missing input. |
| `sidecar pair` | [pair v1](result-profiles/pair.schema.v1.json) | Explicit physical-file association; omitted sidecar and same-object refusals. |

The [parsed emitted examples](result-profiles/examples.v1.json), executable
[negative vectors](result-profiles/vectors.v1.json), and
[qualification record](result-profiles/qualification.v1.json) accompany the
[checker](../../scripts/check_result_profiles.py). All source bytes are independently
authored structural controls. No camera media or reference executable is read.
The [native snapshot contract](native-read-json.md) and accepted
[#0124 preview/pair evidence](preview-pair-arguments.md) remain prerequisites.

## Schema boundary and semantics

These Draft 2020-12 schemas compose the closed existing envelope with the exact
operation, modes, emitted state vocabulary, snapshot kind, effect fields and
artifact subset. Metadata snapshots also load the closed native snapshot and
metadata model schemas locally. List snapshots additionally permit only present
binary values. Unknown members, wrong types, generic metadata shapes and added
authority fail validation. Schema URLs are local identifiers; validation never
fetches them or treats them as executable instructions.

The profiles cover requests that reach the operation adapter with one or more
selected inputs, complete JSON output and no cancellation. General grammar and
selector errors with no file records use the existing status-2 envelope outside
this narrowed package; [syntax routing](native-json-errors.md) remains separate.
Partial transport cannot become complete merely because a truncated prefix
contains `outputComplete: true`. The checker requires strict UTF-8, one JSON
document, terminating LF and bounded completed process capture. Duplicate members,
nonfinite numbers, trailing documents and unpaired surrogates refuse.

| Cross-record obligation | Independent check |
| --- | --- |
| Request and input identity | All record request IDs agree; `input-N` matches the original deduplicated operand order. Every returned input label equals its declared case operand. Existing paths must identify that selected physical file. |
| Counters and outcomes | `discovered` equals emitted unique operands; `deduplicated` counts exact repeated path operands; `excluded` is zero; `byState` equals the independent expected states. Status matches the externally declared expected exit code and actual process result. |
| Issues | Each expected code and severity is checked against the authored case, with correct per-file input references and null path/occurrence references. Diagnostic prose is not an identity. Snapshot issues remain distinct from enclosing result issues. |
| Coverage and snapshots | Read/list source labels and lengths bind the selected fixture; native ranges, occurrence references, exact values and partial coverage satisfy #0053. List only selects binary occurrences. Invalid-value failure retains the actual partial snapshot. |
| Preview | Original bytes and unique allocation bind the selected authored source. An independently constructed hypothetical replacement proves every changed and preserved byte, partition completeness and totals. Stale allocation exposes no original bytes or difference partition. Refusal findings match enclosing issue codes. |
| Pair | Both returned paths identify the separately selected RAW and sidecar objects; they must be distinct. Invalid RAW and non-XML sidecar controls demonstrate association does not parse content. |
| Artifacts and effects | Only the successful extraction creates one explicitly named artifact, with exact independently known preview bytes. Dry run and all other cases create none. Source files and preexisting names, bytes and measured properties remain unchanged. |

`selectionComplete: true` means the bounded explicit operand selection finished;
it does **not** mean metadata coverage is complete. A successful read/list returns
status 0 with a `COVERAGE_PARTIAL` warning. Mixed successful/refused inputs return
status 3. A wholly refused request or invalid selected rational returns status 1;
the latter retains useful valid observations beside the invalid value. No
unobserved metadata is certified absent.

Extraction's successful file state is `read`, and its summary artifact state is
`committed`: this names the stored-preview copy only. The source file's effects
remain false. Dry run uses mode `preview`, state `previewed` and no artifact.
The schema retains the implemented status-5/recovery-required extraction-artifact
shape for cleanup failure; this finite run does not induce that failure, certify
its recovery or qualify durability. Single-input extract/preview/pair cannot emit
a mixed multi-file status-3 outcome. No fabricated partial outcome is substituted.

The advisory date preview has a positive source/byte observation but status 1,
state `refused`, and `production_mutation_allowed: false` because the actual opaque
dependency gate refuses. There is no positive mutation admission in these controls.
Pair success is read-only association; it grants no synchronization, sidecar
creation, content or continuing-guard authority.

## Stable fields and observation limits

Schema version, operation/kind/mode names, required members, scalar types,
null-versus-present states, exact metadata decimal strings and explicit effect
fields are the declared current subset. Array order and occurrence multiplicity
matter. Request IDs and derived snapshot IDs vary per run; diagnostic prose,
member order and equivalent JSON escapes are not stable identifiers. Occurrence
IDs retain local references within their snapshot, not durable cross-run identity.

Examples preserve actual parsed envelopes and generated IDs. Only each fresh
working-directory prefix in canonical pair paths is replaced by `{work}` to avoid
publishing private local paths. These are reviewable locator substitutions, not
literal executable paths or authority. A rerun compares examples after ignoring
only request/derived snapshot IDs and that declared prefix substitution. All other
parsed values must match. Negative vectors name their exact replacement and
validation layer, and the checker requires every one to reject. Every emitted
case includes required-member wrong-type controls for the scalar request mode,
integer discovered count and files array. The coverage forgery changes the actual
`coverage[0].state` member to `complete`, rather than adding an unknown member.

Input and pair path labels are locators. The live case independently compares
selected physical objects, measures source byte hashes and checks snapshot source
lengths; the wire itself does not export or establish persistent object identity.
No result can authorize reopening a path, mutation, replay or imported execution.
Native non-Unicode labels retain #0053's documented lossy-display limits and are
not claimed as tested by these Windows Unicode controls.

Before and after each operation, the checker compares every immediate regular
file's name, size, bytes/hash, modification time, mode, device/file identity, link
count and exposed attributes. The successful extraction adds exactly one expected
file; all original entries must still match. These are observation-bound checks,
not continuous exclusion, ACL/ADS/creation-time coverage, allocation accounting,
JPEG entropy validation or a durability guarantee. Captures and fixtures remain
under ignored `.local/work-wave-20261017a/127-run-*`.

## Reproduce

Build the current root executable, make the existing test-only
`jsonschema==4.26.0` available, then run:

```text
cargo build --locked --bin imageinfo
python scripts/check_result_profiles.py --binary target/debug/imageinfo.exe
```

Native filesystem permissions for disposable no-clobber hard-link publication
are required; an environment denial fails the run instead of counting as product
refusal. `--refresh` deliberately replaces the public authored examples, vectors
and qualification record. The default checks the committed examples and vectors.
For CI on another platform, `--check-current` executes the same 19 authored cases,
schema checks, independent semantic/effect assertions and generated negative
vectors, without comparing platform-specific frozen examples or replacing public
evidence. It retains a fresh local qualification record; passing it does not
refresh or establish equivalence to the Windows observation. These two options
are mutually exclusive. On Linux/macOS the default executable path omits `.exe`.
The reused process runner has closed stdin, no shell, a 15-second operation
deadline and one-MiB capture limit per stream; fixture compilation has 60 seconds.
Capture polling can overshoot a bound before detecting and rejecting excess.

The qualification record binds binary, checker, reused helpers, exact schemas,
fixture support and relevant source hashes, with per-case authored input hashes.
Its finite positive/refusal/partial results establish only this current profile
subset. Other grammar combinations, platforms, filesystem failures, reference
parity, report imports, persistent sessions, general writer/storage admission and
privacy certification remain separate work.

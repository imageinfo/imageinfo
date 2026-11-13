# Inert library consumers

The Rust library exposes two explicit, caller-owned boundaries. Both consume
data in memory; neither adds CLI syntax, session operations, file discovery,
code execution, writer integration, or authority to edit an input.

## Pure filter evaluation

Build a `pure_filter::Registry` for the exact supported selector revision, then
pass the explicit v1 request bytes and registry to `pure_filter::compile`. The
compiled value owns its expression and declarations. Preflight resolves names
in every branch before evaluation can short-circuit. See the [grammar and
bounds](pure-data-boundary.md) for comparison, declaration and coverage rules.

Use `CompiledFilter::evaluate` with caller-supplied `Observations`, or
`evaluate_batch` with an explicit unknown policy. Only true selects. Unknown
produces attributable issues; allowing continuation does not turn a partial
batch into success. Numeric comparison does not round through floating point.

Compile with `Registry::native()` to use `CompiledFilter::evaluate_metadata`
with retained native `reader::Metadata`. A caller-supplied registry with the same
revision label cannot substitute for the native catalog. An observed occurrence can
establish presence. The native reader supplies partial coverage: unobserved
scopes and comparisons needing a complete, unique value remain unknown. The
adapter does not reread the source or create output. XMP declarations alone do
not supply a packet parser or a complete observation.

## Inert scalar intents

Call `inert_intents::decode` with bytes, `Format::JsonV1` or `Format::CsvV1`, and
an explicit immutable `SourceObservation` table. The accepted [native scalar
contract](report-import-boundaries.md) defines matching and lexical limits.
Successful decoding yields an owned ordered list of `Intent` values containing
the supplied source and occurrence identity. A refusal exposes no partial batch.
The decoder matches only declared identities; paths and display text never
resolve a target. An intent establishes neither freshness nor apply permission.

The library portions of LG-003-r01/r02 and LG-002-r06 are separate from CLI or
session routing, broader XMP reader coverage, legacy reports/imports, and full
RAW compatibility. Keep those residuals open. Run the authored public-consumer
tests with `cargo test --locked --test pure_filter --test native_pure_filter
--test inert_intents`.

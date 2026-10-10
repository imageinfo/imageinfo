# Metadata contract validation and handoff

Validated on **2026-10-10**, contract revision `2026-10-10.1`, schema version 1.
This is specification validation for card **#0004**, not a parser implementation
or a camera-file compatibility test.

## Delivered examples

| Artifact | Purpose |
| --- | --- |
| [Snapshot](examples/snapshot.synthetic.json) | 15 separate occurrences across synthetic RAW, sidecar, and embedded-preview documents; duplicate ISO, exact exposure, offset-free and UTC times, XMP conflicts, unknown bytes, derived values, and binary provenance. |
| [Value cases](examples/value-cases.synthetic.json) | 18 focused type/state cases, including large integers, exact decimals/rationals, null, empty values, negative zero, NaN bits, nested XMP, and binary address spaces. Each `value` is checked against the schema's `valueState` definition. |
| [Copy intent](examples/copy-intent.synthetic.json) | Explicit RAW-to-XMP mapping plus a separately identified existing-sidecar update. |
| [Delete intent](examples/delete-intent.synthetic.json) | Explicit deletion of one stored occurrence, distinct from setting null or empty text. |
| [Rejection vectors](conformance-cases.json) | 30 isolated mutations of valid examples, with expected schema/semantic layer and rule ID. |

All paths, values, sizes, and offsets in the examples are invented. No valid CR3 or
JPEG image is asserted by a media-type label. No file with the illustrated camera
content exists, and no real media or identifying personal data was imported.
The named transformation/mapping/formatter rules are proposed identifiers, not
installed code or automatically executable expressions.

## Checks performed

- Draft 2020-12 schema self-validation and validation of one snapshot and two intents.
- Schema plus selected semantic checks for all 18 typed value cases.
- Unique IDs, resolved references, document/resource/derivation graph acyclicity,
  bounded byte ranges, range-length sums, and source attribution.
- Ordinal uniqueness, explicit derived provenance, and normalization dependencies.
- Calendar/precision checks and exact consistency of known UTC instants and fractions.
- Duplicate language alternatives and expanded-name property/qualifier checks.
- Selection results checked against the available occurrences and declared coverage.
- Exact copy/target references, explicit cross-tag mappings, and conflicting-target refusal.
- UTF-8 JSON serialization/reload preserves the entire synthetic snapshot, including
  raw rational pairs, repeated bag members, IDs, and unavailable-value states.
- All 30 rejection vectors fail at their declared validation layer; semantic failures
  report their expected MDL rule.
- Four additional lexical checks reject duplicate JSON object keys, bare NaN,
  bare Infinity, and a lone Unicode surrogate.

The checks used `jsonschema 4.26.0` and a small local semantic checker in an isolated
tooling environment. This chooses no language, package manager, or test framework
for the application. The public schema and vectors are language-independent inputs
for the eventual implementation's tests.

## Repeating the checks

1. Validate [the schema](metadata-contract.schema.json) against draft 2020-12.
2. Validate the snapshot and intent examples against it, with format checking enabled.
3. Validate each value-case entry's `value` against `#/$defs/valueState` and resolve
   binary references using its declared snapshot context.
4. Enforce the semantic MDL rules described in [the contract](README.md). Schema
   validation alone cannot detect dangling IDs, mismatched source identity, invalid
   range sums, dependency cycles, or unsupported claims of complete coverage.
5. For each rejection vector, load a fresh copy of its example and apply the listed
   JSON Pointer `replace`/`add` operations in order. An array `-` appends a value.
   Validate without changing the committed positive example. Require rejection at
   the named layer; semantic failures must identify the named rule.
6. Re-serialize and reload the valid snapshot without changing typed values, states,
   identity, source order, or dependency references. Check semantic equality
   separately from byte/raw-representation equality.
7. Check documentation links, schema/example version consistency, and staged whitespace.

The helper exercises the documented cases; it is not a production validator or a
claim that every malformed XML/date/encoding/resource-budget combination has been
exhaustively tested. BCP 47 registry validation, real XMP serialization, per-tag
type conversions, stream truncation and resource-limit behavior require the later
fixture/parser work. No binary source referenced by a synthetic example is read.

## Acceptance trace

| Card requirement | Contract/evidence |
| --- | --- |
| Duplicate occurrences and groups | MDL-001–004 and ISO ambiguity example; native keys and advisory grouping are separate. |
| Binary and rational values | MDL-006–007 and MDL-010–011; resource references, exact pairs, range checks, and numeric cases. |
| Raw, normalized, display views | MDL-007 and MDL-010; normalization rules/dependencies and explicit display context. |
| Missing versus empty | MDL-011 and MDL-014–015; absent query, partial query, typed null, empty string/list/binary. |
| Unknown timezones | MDL-013; no invented instant, explicit offsets, fractional precision, and distinct RFC 3339 unknown-local-offset state. |
| XMP arrays, structures, languages | MDL-012 and nested type cases; expanded names, multiplicity, qualifiers, and language-key uniqueness. |
| Embedded documents, offsets, provenance | MDL-005–009; parent graph, address spaces, decoded/fragmented resources, source identity and derived dependencies. |
| Export, selection, copy and future planning | MDL-014–019; loss-aware serialization, exact targets, explicit mappings, and intent-only examples. |
| Language-independent and unsurprising design | Boundary schema is independent of internal types/code layout; each unusual wire choice has a concrete rationale. |

## Handoff

The proposed model portion of **GAP-005** is now specified. Runtime evidence for
per-tag conversions, encodings, source presence, and real-file round trips remains
open and passes to **#0005, fixture-plan**. No capability row is promoted to
implemented or verified.

The fixture plan is now [specified](../fixture-plan/README.md). Its actual corpus
acquisition and reference observations remain backlog work on #0013; the model's
synthetic examples still provide no camera-runtime evidence.

- **#0005:** build lawful fixture manifests and experiments around the MDL rules,
  starting with EOS R5 full RAW. Preserve the distinction between source observations
  and synthetic examples.
- **#0003:** use occurrence-aware selection and explicit value states in command,
  menu, help, and error examples. ExifTool aliases are mappings into this model.
- **#0006:** turn edit intents into validated plans, including mappings, capability
  checks, stale-source detection, source-byte preservation, and recovery.

The greenfield, conventional-code, least-surprise, and rationale-comment requirements
are recorded in project guidance. Internal types, module boundaries, dependencies,
language, and runtime design remain open for the later architecture decision.

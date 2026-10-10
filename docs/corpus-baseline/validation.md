# Corpus baseline validation

Validated on **2026-10-10**, card **#0013**. Checks distinguish private runtime
evidence, documentation/schema consistency and unverified product behavior.

## Private evidence checks

Using JSON Schema draft 2020-12 with isolated `jsonschema 4.26.0` tooling:

| Check | Result |
| --- | --- |
| 35 fixture manifests, 97 experiment records, two acquired oracle profiles | Valid |
| 39 operational, scoped provenance reviews | Valid |
| 320 unique registered artifact descriptors: rooted path, length and SHA-256 | Match |
| 965 source/runtime/driver manifest entries rehashed at final validation | Match |
| Fixture IDs/hashes, derivative parent/recipe hashes and evidence references | Resolve |
| All media admission limited to restricted reference characterization | Confirmed |
| No public media redistribution permission inferred | Confirmed |
| Input hashes before/after all 97 final invocations | Match |
| Source/received original hashes and source modification times at completion | Unchanged |
| Candidate executable absent and all verdicts reference-observed | Confirmed |

Tool/source manifests were checked against acquired files before/after the main
92-run sequence. Five subsequent XMP operations used the same pinned reference/API
driver and a separately retained exact driver. Configuration/locale/timezone probes,
per-run captures and original-integrity records are retained privately. Metadata
reads and marker checks do not replace an independent RAW/JPEG decoder.

## Schema and documentation regression checks

The existing fixture-plan checks still validate 29 planned families, all 49 CAP
references, both synthetic manifests and their real example hashes, the reproducible
synthetic derivative, 22 comparison examples and 28 invalid-record rejections.
Those checks remain synthetic and are separate from the 97 actual reference runs.

Experiment version 2 was checked against all 97 actual records. Negative cases
reject a null limit without its reason, an empty reason, a reason attached to a
configured limit, an undeclared reason field, and version-1 records using version-2
limits. The old version-1 examples continue to validate unchanged. The extension
changes evidence representation; case-specific enforcement requirements still apply.

The inventory remains 49 specified capabilities, 32 mappings, 12 gaps, 20 sources
and zero implemented/verified imageinfo capabilities. Its revision now acknowledges
bounded upstream runtime evidence. Internal links, JSON, requirement references,
pinned source paths, whitespace and public/private file boundaries were checked.

## Review limits

This is a reviewed aggregate report, not a public evidence bundle. Private records
contain exact identities and argv; photographs and identifying captures cannot be
reconstructed from the public summary. Auxiliary XML assertions are explicitly
limited and do not count as complete independent-validator runs.

No native parsing, safe embedded writing, all-preview coverage, adversarial safety,
privacy clearance, performance target or cross-platform equivalence is established.
The remaining work is listed in the [coverage table](README.md#admission-and-remaining-work).

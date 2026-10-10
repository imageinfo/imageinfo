# Fixture-plan validation and handoff

Validated on **2026-10-10** for plan/policy revision `2026-10-10.1` and schema
version 1. These results concern records, hashes, comparison examples and guards.
They are not CR3 parser tests, oracle executions, or imageinfo parity results.

## Results

| Check | Result |
| --- | --- |
| Draft 2020-12 schema self-validation | Passed |
| Case plan, planned oracle profile, two illustrative manifests, and not-run record | Passed |
| CAP/MDL/case references and case ID uniqueness | Passed |
| Current capability rows mapped to case families | 49 of 49, as plans only |
| Prioritized case families | 29; all marked not-collected |
| Actual example artifact lengths and SHA-256 values | Passed |
| Parent/recipe hashes and deterministic synthetic derivative reproduction | Passed |
| Synthetic comparison-policy cases | 22 passed |
| Evidence-integrity rejection checks | 28 rejected as intended |
| In-memory record-branch checks | Four: completed comparison, reference-only observation, accepted difference, and expected refusal; all are mocks, never saved as run evidence |
| Real camera fixtures acquired | 0 |
| Reference/imageinfo media experiments executed | 0 |

Validation used `jsonschema 4.26.0` plus a small local checker in an isolated tooling
environment. This selects no implementation language, harness framework, or product
dependency. The schemas, cases, and rules are inputs for conventional tests in the
eventual chosen language.

## Synthetic artifact review

The parent example is the project-authored metadata snapshot introduced in commit
`b1697d6a25fc3b144284ca269968aaf55bf065cb`. The parent bytes remain unchanged.
The derivative selects its raw rational value, changes the denominator to zero,
and wraps it as an intentionally invalid model example. The recorded recipe
reproduces the derivative's exact UTF-8 bytes and hash.

These files contain invented metadata, paths, offsets, camera labels, and resource
descriptions. They contain no actual camera pixels, preview bytes, device serials,
or personal media. This review covers only those synthetic documentation artifacts.
Their project MIT terms do not establish permission for future contributor or
third-party photographs. Both manifests remain `example-only`, with no allowed
experiment phases.

The example experiment remains `not-run`: no executable identity, environment,
successful result, or independent report has been fabricated. Real hashes describe
the example input, policy, recipe and profile files only.

## Rejection checks

- Incorrect artifact hash, escaping artifact path, duplicate fixture ID.
- Incorrect parent/recipe hash or a derivative expanding redistribution rights.
- An illustrative fixture admitted as a real corpus fixture.
- Admitted material with unreviewed rights, or restricted material marked public.
- A not-run record labeled successful.
- Fixture/profile identity mismatch.
- A ready reference profile lacking tool identity or reporting the wrong version.
- A reference recipe that would inherit default user configuration.
- A fixture used in an unauthorized phase, or an illustrative fixture used for execution.
- Failed or unrun assertions labeled pass.
- Lost stdout capture, changed read-only input bytes, or dangling evidence references.
- Negative execution duration or an invented hash for a missing working copy.
- An unreviewed/outdated difference accepted, a preservation failure waived, or a
  semantic failure left outside the reviewed difference scope.

Mocks used to exercise completed-record branches exist only in the checker process.
They do not assert that the named tools, observations, environments, or review
decisions exist. Schema/record validation cannot itself prove real execution,
license authority, privacy clearance, or sufficiency of independent validators.
Those require the captured artifacts and review described by the plan.

## Repeating the checks

1. Validate [the schema](evidence.schema.json) and each record's declared kind with
   a draft 2020-12 validator and format checks enabled.
2. Resolve CAP/MDL/case/fixture/profile/check references and require unique IDs.
   Confirm that the plan covers the current capability inventory without promoting
   any cell to implemented or verified.
3. Resolve configured artifact roots safely, recompute lengths and SHA-256 values,
   and verify parent and recipe identities. Reproduce the synthetic derivative
   from [its recipe](examples/derivation.synthetic.json), preserving serialization.
4. Evaluate [comparison examples](comparison-cases.json) by their explicit mode.
   Use exact numeric operations, type-aware comparisons, and multiplicity-preserving
   bags. Unknown interpretations produce indeterminate results.
5. Enforce admission/phase permissions, reference readiness, identity equality,
   capture completeness, and result rules. Exercise the invalid combinations above
   against fresh in-memory copies of valid records, never by altering real evidence.
6. For actual embedded writes, additionally require separately identified structure,
   payload and usability validation, with exact inputs, reports and passing linked
   checks. This documentation exercise did not run such validators.
7. Check local links, JSON validity, source references, and staged whitespace.

## Card #0005 acceptance trace

| Requested outcome | Delivered |
| --- | --- |
| Prioritized EOS R5 full RAW fixture categories | FXP-001 through FXP-029; sidecars/previews included, secondary modes separated |
| Fixture manifest and provenance | Versioned schema plus actual-hash illustrative manifests, rights/privacy/admission fields and lineage |
| Reproducible experiment contract | Versioned records for controlled environment, tool/runtime/driver identity, captures, before/after states, comparison policy and independent validators |
| Reference version/configuration | Planned ExifTool 13.59 source baseline and six controlled recipes; readiness requirements explicit |
| Normalized comparison and outcomes | CMP-001 through CMP-012 and 22 synthetic cases; clear pass/fail/unsupported/difference/not-run/invalid meanings |
| Malformed inputs and multi-OS expectations | Dedicated prioritized families and platform/fault/resource-bound matrix |
| No unlicensed or personal media import | Only existing and derived project-authored synthetic JSON examples |

## Handoff

The planning part of #0005 is complete for review. Camera acquisition, provenance
admission, executable/runtime/driver hashing and actual reference observations
remain future work; GAP-001, GAP-005, GAP-007 and GAP-008 are not closed by this plan.
They are assigned to backlog follow-up **#0013, corpus-baseline**, so completing
this specification card does not hide the unfinished acquisition and experiments.

The next critical-path card is **#0006, write-safety-contract**. It should define
the transaction/refusal/preservation/recovery assertions that the mutation cases
will test. #0003 can consume these cases for CLI walkthroughs. The locked MIT
decision remains unchanged, with third-party provenance work on #0010.

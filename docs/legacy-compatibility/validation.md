# Compatibility validation and handoff

Reviewed **2026-10-10**, proposal revision `2026-10-10.1`, card **#0007**.
This is a surveyed compatibility recommendation, not an implementation or a claim
of exhaustive/drop-in parity. Language and internal architecture remain undecided.

## Results

| Check | Result |
| --- | --- |
| Existing MAP family coverage | All 32 mapped exactly once to equivalent-proposed, difference-proposed or open-gap |
| Pinned API METHODS headings | All 39 named methods accounted for, including static methods |
| Recommendation rules | LEG-001 through LEG-010 |
| Migration acceptance cases | MIG-001 through MIG-012 reviewed; no translation program ran |
| Request/control schema | Draft 2020-12 self-validation and six synthetic input examples passed |
| Native envelope semantics | Four permitted examples passed; command/mode/authority and literal separator behavior checked on the documented subset |
| CLI result schema | Three individual result records and three complete envelopes validated with offline metadata-schema resolution |
| Rejection checks | 24 schema, lexical and cross-record checks rejected invalid data as intended |
| Pure-filter semantic cases | 12 synthetic truth/coverage/ambiguity cases passed; no expression parser implemented |
| Persistent session cases | 12 expected-response scenarios reviewed; no real subprocess/session ran |
| Inventory | Revision 2026-10-10.6 schema/references/dependencies and ten rejection cases passed; all 49 capabilities remain specified |
| Real reference/native media experiments | 0 |

Validation used `jsonschema 4.26.0` and a small local documentation checker. This
is tooling for schema review, not a product-language or dependency selection.
The examples contain only invented paths/IDs and project-authored metadata data.
No camera image, personal data, upstream parser or configuration was imported.

## Reproduction

Self-validate [request](request.schema.json) and [result](result.schema.json) under
JSON Schema Draft 2020-12. Resolve the result schema's metadata references locally
against [the existing schema](../metadata-model/metadata-contract.schema.json),
using its published `$id`; do not fetch a remote schema while parsing untrusted data.
Validate all six request/control records in [examples](examples.v1.json).

Construct an in-memory read envelope with the existing
[authored snapshot](../metadata-model/examples/snapshot.synthetic.json) as its
file `snapshot`. Use the required record fields from the result schema, matching
request IDs, one unique input ID, read state, no publication/change, null transaction,
empty issues/artifacts and a successful complete summary with one read count.
Validate the three records independently and the enclosing JSON envelope.

Validate the complete invalid-request envelope in
[the CLI result document](../cli-walkthroughs/results.md). For the third envelope,
derive a recovery-required file with null snapshot, an invented transaction ID,
publication possible, unknown changed status, an original recovery ID and summary
status 5. These are synthetic records, never saved as successful runtime evidence.

Beyond schema shape, check request IDs agree, input IDs are unique, complete summary
counts equal file states, and read/preview/unchanged/before-publication outcomes do
not claim publication. Recovery-required in either a file or output artifact must
prevent status 0 and require the precedence table's status 5.

Check the filter examples against three-valued logic, observed count, coverage and
value availability as defined in [migration](migration.md). Their results test the
specification's decision table, not parsing, numeric precision or a runtime engine.
The session examples are acceptance expectations for later fault-injection tests;
review them against [integration](integration.md) without pretending that a table
lookup tests concurrency, transport framing or isolation.

## Negative cases

- Request structure: unsupported version, unknown property, string command instead
  of token array and invalid close policy.
- Request semantics: relative working directory, framed output override, apply-mode
  read, missing outer apply authorization, legacy invocation on a native entry and
  nested process request.
- Results: recovery uncertainty labeled successful, flattened snapshot, unknown
  changed flag outside recovery, unknown field/state/status, mismatched request ID,
  duplicate input ID, incorrect count, read claiming publication and zero state count.
- Lexical input: duplicate JSON members, non-finite numbers and unpaired Unicode
  surrogates. Ordinary JSON parsing without these checks is insufficient.

Cross-record checks here exercise important examples, not a full adversarial schema
or parser audit. The remaining executable semantics stay visible in LG-001–006.

## Acceptance and decision status

| Requested outcome | Delivered |
| --- | --- |
| OD-01 workalike/drop-in distinction | LEG-001–005; native workflows plus nonexecuting migration report proposed; exact legacy syntax/output remains separately scoped |
| OD-02 expressions and executable configuration | LEG-006/007; bounded filter grammar and explicit data definitions proposed; arbitrary code/module trust remains an open gap |
| OD-07 API and stay-open use cases | LEG-008/009; all API headings mapped, explicit snapshot/intent lifetimes and bounded JSONL session proposal |
| Every surveyed surface classified | 32-family ledger with explicit unresolved parts; not a claim to have surveyed every option overload |
| Migration examples and trust boundaries | Twelve cases, token-only input, no implicit config/argument-file execution, no automatic apply |
| Follow-up from #0003 | Request/result schemas, request-file modes/authority, pure filtering and session framing; saved-plan and complete session-output schemas explicitly remain open |

OD-01/02/07 now have reviewable recommendations, **not recorded user acceptance**.
The locked MIT decision and full ExifTool functional ambition are unchanged.
Source observation is pinned; runtime behavior remains unverified.

## Sources and remaining work

The [application manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html),
[API reference](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod),
[configuration example](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/config_files/example.config),
[structure documentation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html)
and [conversion documentation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/under.html)
were read at the same pinned revision on 2026-10-10. The latter two support the
existing structure/value-layer constraints; no new wholesale source material is
redistributed. Actual API overload/option behavior still needs experiments.

Backlog **#0015, compatibility-evidence**, owns LG-001–006 and the remaining
inventory GAP-006/GAP-012 work. This includes complete plan/session-output schemas,
exact serializers, advanced executable behavior decisions and actual integration
evidence. The incomplete plan schema is a real gap, not closed by the request schema.

Card #0008 now supplies the [performance protocol](../performance/README.md) for
RAW reads, safe edits, report buffering, filters, queues and sessions. Actual
measurements and finite numeric default decisions remain #0016. The
[governance proposal](../../GOVERNANCE.md) is now recorded; #0010 is next for artifact
provenance. No timing claims
or numerical defaults are supported by this card's synthetic checks.

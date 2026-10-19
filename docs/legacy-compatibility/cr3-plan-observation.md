# Advisory CR3 plan recomputation (#0078 preparation)

This bounded preparation adds [snapshot comparison](../../src/plan_observation.rs)
to the existing saved preview contract. It does not complete #0078. #0119's
missing positive format capability and actual positive storage admission remain
prerequisites for any apply adapter.

`recompute` accepts a caller-supplied stream, explicit current source/output
locators and proposed date. The existing bounded source capture takes one
snapshot, runs the actual reader and admission preview, and reconstructs current
advisory content/occurrence assertions. The result retains the full fresh preview,
including refusal findings and byte ranges, plus a deterministic field comparison
against the unchanged saved intent. A difference is exposed, never accepted as
authorization or silently substituted into the saved plan. Errors remain errors.

The separate pure comparison also accepts two validated preview shapes. Its
equality means assertion equality only; neither input is a trusted capability.
Current locators remain inert strings. No path is resolved or opened here and no
filesystem identity, absence, alias, guard or property observation is invented.
The stream supplier must account for the existing snapshot's concurrency limits.

The typed requested-effect description always retains the require-absent new
output locator. Equal old/new ASCII20 values therefore do not erase the requested
fresh-name copy effect. This description grants no permission to create it.

## Complete WS-002 comparison

The [eleven-duty inventory](operation-plan-map.md) expands the WS-002 fields.
Every duty remains assigned below; an unresolved duty is not encoded as a
successful imported flag.

| Duty | Existing saved preview / fresh capture | This increment and remaining execution gap |
| --- | --- | --- |
| P-READ | Full bounded source length/hash, exact original date bytes and indexed occurrence; no mutable copy sources in this operation. | Fresh snapshot comparison exposes content and original-byte changes. Immutable guarded original view, assumptions and complete dependency read set remain unavailable. |
| P-WRITE | One existing ASCII20 occurrence, allocation, byte order, intended bytes, output locator and require-absent collision policy. | Exact changes are reported separately. Actual resolved destination/parent absence, aliases, conflicts and candidate write binding remain unavailable. |
| P-IDENTITY | Source/output locators and content assertions only. | Object, parent, physical path/link/candidate identity and continuing guard bindings remain unavailable. Equal hashes cannot fill this gap. |
| P-PROPERTY | OD-11 policy label only. | Actual attributes, access/ownership, times, streams, link topology, carry-through rules and check boundaries remain unavailable. |
| P-EFFECT | Valid Gregorian ASCII20 old/new bytes, one selected replacement and complement declaration; no requested conversion or implicit updates. | Typed equality/replacement and explicit fresh-name effect plus fresh byte-range preview. Actual admitted semantic/dependency/reference/checksum map, candidate validation and protected interpretation effects remain unavailable. |
| P-LOSS | Fixed exact-date intent requests no losses, conflict selection or other transforms. | No loss consent is added or inferred; any actual wider effects require another contract and explicit disclosure. |
| P-REVISION | Exact schema/model/reader/admission/registry/capability/conversion/policy labels checked against current code. | Fresh capture uses current rules, field comparison reports all labels. Actual operation/storage revisions and trusted technical admission remain unavailable. |
| P-PUBLICATION | Explicit unavailable-production profile and require-absent intent. | Supported profile, actual candidate/parent/destination checks, guards and persistence acknowledgements remain unavailable. |
| P-RECOVERY | No mutation/recovery authority. | Actual owned artifacts, custody, retention/resource bindings and fresh recovery conditions remain unavailable; no artifact is constructed. |
| P-ORDER | Exactly one source, occurrence and requested new output; no pair, copy-source graph or group is requested. | No executor or partial-outcome behavior is supplied. Eventual single-unit execution still needs explicit cancellation/outcome/recovery bindings. |
| P-AUTHORITY | Strict bounded inert v1 imports and separate-caller-required value. | No authority constructors or apply route. Every successful comparison remains nonauthorizing; independent format/storage/caller checks remain required. |

No wire additions are needed for this increment: v1 already represents all of
these advisory inputs with strict missing/duplicate/unknown-field rejection and
bounded decoding. The new observations have no deserializer and cannot be
imported as execution bindings. The existing schema and CLI remain unchanged.

## Verification

`cargo test --test plan_observation` exercises every variable v1 field, exact
roundtrip, fresh source/request changes, forged assertions, invalid current
intent/source and equal-date fresh-name semantics using public authored fixtures.
Fixed schema/revision/native-tag and single-variant policy fields remain protected
by the existing `plan` contract tests. `cargo test --test source_binding` covers
missing/duplicate occurrences and snapshot read limits. These controls establish
bounded advisory behavior, not actual media admission or positive application.

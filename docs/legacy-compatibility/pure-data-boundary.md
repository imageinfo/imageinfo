# Bounded pure filters and explicit definitions (#0131)

The accepted #0007 direction is bounded pure filters and explicit data definitions.
#0131 refines that direction; it does not request another adoption decision.
The [#0054 EXT survey](executable-extension-boundary.md) remains the historical
alternatives record. This contract supersedes its pending-choice wording for the
pure/data scope only. No production filter, definition importer, code loader or
sandbox is implemented here.

## Exact scope and grammar

The [existing selection grammar](migration.md) is retained unchanged: `exists`,
`absent`, and `value` with raw/normalized views; six typed comparisons; JSON
scalar literals; `not`, `and`, `or`, and parentheses. Whitespace is exactly ASCII
space, tab, CR or LF outside tokens. JSON strings use valid Unicode scalars;
unpaired surrogates refuse. Numbers use JSON number spelling and exact rational
comparison, including exponent notation. Boolean ordering refuses as unknown;
Boolean and null support equality/inequality only. No normalization, locale
folding, implicit coercion, arithmetic, regex or string interpolation exists.

This refinement adds two literal-only operands to that grammar:

```text
selector = json-string | "alias(" json-string ")"
literal = json-string | exact-json-number | "true" | "false" | "null"
        | "param(" json-string ")"
predicate = "exists(" selector ")" | "absent(" selector ")"
          | "value(" selector "," view ")" comparison literal
```

An alias resolves once to a canonical selector from the exact named registry
revision. Alias targets cannot name aliases, parameters or definitions. A parameter
is a typed JSON scalar supplied in the same explicit request, never substituted
into source text. Its declared type must match its value, with no bool/number
coercion. Types are string, number, integer, Boolean and null; integer uses a JSON
number with an exact integral mathematical value. No integer-to-storage mapping
or XMP lexical conversion is inferred. Names are ASCII
`[A-Za-z][A-Za-z0-9_]{0,63}`. All three declaration
lists share one unique-name space; built-in names cannot be shadowed. Lists have
caller order for diagnostics, with no dependency graph or calculated definitions.
Definitions declare an expanded XMP name (absolute namespace URI plus local name),
scalar interpretation, provenance and revision. A URI is an opaque identifier,
never dereferenced. Its exact accepted spelling is an ASCII letter followed by
zero or more ASCII letters/digits/`+.-`, a colon, and a nonempty suffix of ASCII
letters/digits/`._~:/?#[]@!$&'()*+,;=-` or `%` plus two hexadecimal digits.
Two definitions of the same expanded name refuse even when
their spelling or declared types match. An existing built-in expanded name refuses.
Declarations neither establish actual presence nor authorize parsing an unsupported
packet shape, conversion, insertion, deletion or publication.

## Frozen v1 bounds and authority

The [request schema](pure-data/request.schema.v1.json) fixes a future explicit
request envelope. It is specification data, not accepted CLI/session syntax.
Strict UTF-8 input has at most 65,536 bytes, no BOM and no duplicate JSON members.
Expressions have at most 4,096 UTF-8 bytes, 1,024 lexical tokens, nesting 32,
128 predicates, and numeric tokens of at most 128 bytes with exponent magnitude
at most 308. String/selector/URI/provenance fields have at most 1,024 UTF-8 bytes;
revision fields have at most 64 ASCII identifier characters. There are at most
64 aliases, 64 parameters and 64 definitions. Limits are inclusive and validated
before media access; violating any limit refuses the whole request.

Preflight resolves every name and checks all syntax, including branches later
skipped by evaluation. The future evaluator has at most 128 predicate visits and
256 Boolean-node visits per input; budget exhaustion is an attributable unknown,
never selection. Exact decimal-to-rational conversion must respect numeric bounds
before allocation. No hard wall-clock, memory sandbox or native default is claimed.

Evaluation reads only caller-selected immutable observations and checks the exact
registry revision. `exists` needs an observed eligible occurrence for true and
complete scope with none for false. `value` requires complete scope and exactly
one occurrence with an available selected view; duplicates, incomplete coverage,
conversion/type failures yield unknown. Explicit null remains present.
Strong Kleene Boolean logic, left-to-right short circuit and unknown-default
failure follow the existing grammar contract. Only true selects; explicit continue
may process independent true inputs while retaining unknown issues and failure
status. Comparison never changes stored metadata or certifies privacy.

The request is explicit caller-owned data. No discovery from directories, media,
environment, plans or imported legacy config; no file reads from URI/provenance,
network, subprocess, module loading, callbacks, hooks, persistent state or mutation.
Provenance/revision are visible declarations, not authentication or trusted custody.
Unknown keys, unknown versions, conflicting identities or any invalid declaration
reject the entire request without partially installing data for this or later reads.

## All EXT uses and residuals

| Use | Exact scoped outcome | Remaining obligation |
| --- | --- | --- |
| EXT-001 | Future typed ISO comparison using the retained grammar and coverage semantics. | Actual parser/evaluator, native observations, limits and status evidence. |
| EXT-002 | `alias("capture_iso")` and `param("minimum_iso")` are explicit literal bindings. | Future request/schema integration and exact revision/name resolution. |
| EXT-003 | Expanded-name scalar XMP declaration with provenance/revision, no parser code. | Reader support and actual shape/type evidence; no write authority. |
| EXT-004 | Custom exposure arithmetic and rounding refuse. | General calculations/composites, units and exact arithmetic remain unmet. |
| EXT-005 | Existing [native date adapter](../sidecars/native-date-adapter.md) only. | Mapping acceptance and publication gates remain independent. |
| EXT-006 | Perl/regex/interpolation and filename formatting refuse. | PR-013/018, LG-002 template/rename scope remains unmet. |
| EXT-007 | Module/parser/conversion callback loading refuses. | Arbitrary executable equivalence, provenance/trust/failure model remain unmet. |
| EXT-008 | No local/catalog/environment/network lookup; caller may supply literal data. | Caller owns external retrieval; no implicit authority or provenance claim. |
| EXT-009 | Hooks, shell execution and retained module state refuse. | Executable orchestration parity remains unmet; caller orchestration stays external. |

PR-017/018/022/026/027/029, CLI-002/005/009/015/016, LEG-002/003/006/007/008/009,
MAP-015/026, LG-003, CAP-019/040/046 and GAP-006/011 remain intact. These finite
pure/data forms do not satisfy arbitrary expressions, `BuildCompositeTags`,
executable `AddUserDefinedTags`, complete `OrderedKeys` behavior, or full parity.
No WS/SAF storage, RAW mutation, source binding, consent or recovery gate changes.

## Finite evidence and future implementation acceptance

[Vectors](pure-data/vectors.v1.json) cover accepted envelope shapes and refusal
classes. The dependency-free [checker](../../scripts/check_pure_data_boundary.py)
checks this schema's finite keyword subset, duplicate members, byte bounds,
declaration identity rules and complete EXT trace. It does not parse/evaluate
filter expressions, inspect media, validate arbitrary JSON Schemas or execute code.
The records marked `futureEvidence` are required unrun implementation cells,
not passes obtained by this checker:

- Parser: precedence, parentheses, escapes, valid exponent numbers, trailing tokens,
  unknown functions/names/revisions, alias/parameter literal injection and skipped
  branch preflight; every expression/token/depth/predicate/numeric bound at limit
  and one over, including UTF-8 versus character lengths.
- Evaluation: all 3x3 Boolean pairs, exact rational versus decimal equality, type
  mismatch, null presence, unavailable view, duplicate/incomplete coverage, missing
  complete scope, scalar ordering, Unicode equality and left-to-right diagnostics.
- Definitions: all field/count/byte boundaries, whole-set atomic refusal, built-in
  collision, same-expanded-name collision, unsupported packet shapes, explicit
  selection only, and independent request state in native CLI/API/session paths.
- Authority: attempted file/network/process/environment/module/hook access and
  imported config/code are rejected as data/syntax; prove actual implementation
  behavior without claiming a sandbox for arbitrary executable code.

Run `python scripts/check_pure_data_boundary.py`, `python scripts/check_docs.py`
and `git diff --check`. Authored schema/vector checks are specification evidence
only; actual runtime, integration, source-coverage and failure evidence remain unrun.

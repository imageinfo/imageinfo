# Disposable spike findings

Run **2026-10-10**, Windows x64. [Source and reproduction commands](../../experiments/0011-language-selection/README.md)
and [sanitized results](spike-results.json) are public. Exact private arguments,
executable hashes, timestamps, stdout/stderr and input hashes remain local.

| Probe | Actual result | Limits |
| --- | --- | --- |
| Rust 1.99.0 / Cargo 1.99.0, clap 4.6.7 | Final 21 CLI parse/policy cases pass | One small command tree; not all CLI-001–017 behavior |
| Rust help equivalence and operands | Two leaf-help forms render identically; plain text; `-- help` remains a filename | No real TTY accessibility, menu, completion or shell test |
| Rust Serde 1.0.229 / serde_json 1.0.152 | Typed wire round trip retains max-u64 decimal text, a zero-denominator rational pair, a float-bit string and duplicate occurrence labels | Authored wire example only, not native metadata conversion or complete MDL schema validation |
| Rust and Go 1.25.1 | Each passes six synthetic top-level header cases | No recursive BMFF, tag decoding, CTMD/sample-table interpretation, fuzz campaign or streaming cancellation |
| Both readers on eight private CR3 copies | Exit zero and agree on top-level counts; input SHA-256 hashes unchanged | Same tiny algorithm expressed twice; agreement is not independent format correctness |
| C# | Documentation comparison only | No installed .NET SDK; no runtime result claimed |

## Two CLI assumptions disproved

Clap's ordinary help action can return help for `--help --bogus` before validating
the later token. That differs from CW-002. The probe uses a normal Boolean help
argument and finishes parsing before deciding whether to show help. Required
input checking follows that decision; unknown options and bad values still fail.

The first policy probe failed case 14: a scalar option at the root and again at
the leaf was accepted because global propagation hid the earlier value. The
final probe generates the common options at each level, inspects each scope's
matches and rejects multiple scalar values before dispatch. This preserves one
definition of the options without writing another tokenizer. Both departures
have nearby rationale comments in the probe.

The first Rust attempt exited 101 on that assertion; it is a recorded finding,
not silently counted as a passing run. The final 21-case run exited zero. The
probe's bare-command-path `help` normalization intentionally covers only its tiny
grammar. The product adapter still needs full command/option/operand and duplicate
help tests; do not extrapolate three tested help paths into complete compatibility.

## Bounded reading and ownership

Both implementations use an eight-byte header buffer and an additional eight-byte
extended-size read when needed, then seek to the next declared box. Checks reject
a short header, a size smaller than its header, a span beyond the input and an
oversized extended length. A valid minimal box and an exhausted box-count budget
complete the six synthetic cases. The corpus runs use a 4096 top-level-box budget.
That number is a research guard, not a proposed product default.

The probes never decode pixels or read the whole sensor payload into memory.
They do not validate the type or contents of skipped boxes. Their flat header walk
has no ownership/lifetime complexity in either language. The more demanding
question—maintaining exact metadata and nested resources with readable Rust—must
be checked in the first implementation slice.

This was not a benchmark. Builds, cache state, compiler optimization levels and
workloads were not controlled for performance comparison. No elapsed time, memory
or throughput claim is derived from tool execution durations. No C# runtime or
performance comparison was performed.

## Retention

The small original probe sources and research lockfile are retained for review and
reproduction. They are clearly separated from future product code, use assertions
where production needs diagnostics, and must not be shipped as imageinfo. No public
binary or personal fixture is included. Raw local results remain ignored.

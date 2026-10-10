# CLI walkthrough recommendation


Subsequent #0019 implements a [limited CLI foundation](../foundation/README.md).
The broader examples/requirements below retain their proposed status; media parsing
and full result/CLI compatibility are not established by foundation help/version.

Status: **proposal for review**, revision `2026-10-10.1`, card **#0003**.
These original command/response examples are design data, not a menu implementation
or user usability study. The linked foundation above now implements a small subset;
Rust is accepted separately. This contract does not prescribe internal organization.

Read the [walkthroughs](walkthroughs.md) for the user experience, the
[result contract](results.md) for scripts, and the [validation record](validation.md)
for coverage and remaining work. These refine the [CLI requirements](../cli-requirements.md),
[metadata model](../metadata-model/README.md) and [write-safety contract](../write-safety/README.md).

## Recommendations and resolved ambiguities

**CW-001 — Ordinary command grammar.** Use the existing root/group/operation tree.
Add `recovery list`, `recovery show`, and `recovery resolve`. Recovery resolution,
backup restore/prune and batch resume preview by default and require `--apply` for
effects. `plan apply` is itself an explicit application action. Help and discovery
never execute their displayed examples.

Bare root/group invocation returns concise help and status 0. A known leaf with
missing required arguments returns status 2 and its help path. Options use their
full names: no inferred abbreviations, bundled short flags or unknown-flag fallback.
Global options can appear before or after the command path, before `--`.
Operation options follow the leaf. Accept `--name value` and `--name=value`.
Repeat list options such as `--tag`; duplicate scalar options are errors, even
when identical, so configuration precedence cannot mask an ambiguous invocation.

After `--`, every token is an operand, including `help` and `--apply`. A literal
file called `help` uses this separator. Shell expansion happens before imageinfo;
imageinfo treats received paths literally and does not run a second glob expansion.
Paths beginning with a hyphen should also follow `--`.

**CW-002 — Help wins over execution, not malformed syntax.** Root/group/leaf
`help` and `--help` spellings in CLI-001 resolve to the same node and status 0.
A valid help request suppresses operation execution and required-operand checks,
including when `--apply` is present. Unknown command paths/options, contradictory
flags or malformed option values still return status 2 without media I/O. Parse help using built-in
definitions; do not load user configuration, inspect photos or query a network.
Help defaults to plain text; an explicitly configured terminal pager is optional.
Redirected help has no ANSI/pager/prompt even with `--color always`.

**CW-003 — Keep configuration and domain profiles distinct.** Reserve global
`--config-profile <name>` for a named settings profile; `--profile <name>` belongs
to privacy leaves only. This removes the earlier double meaning. Effective
settings follow CLI > environment > named settings profile > user configuration >
built-in defaults, with origin shown by `config show`. Explicit apply, no-backup,
continue-after-errors and interaction opt-in cannot be inherited silently.
Both interactive flags together are invalid; `--no-interactive` suppresses any
inherited preference, which never enables a menu by itself.
Interactive invocation combined with `--apply` is invalid: the menu has its own
explicit Apply action after preview. `--menu-style` is valid only in guided mode.

**CW-004 — Exact selection without an invented query language.** `--tag` accepts
a registered canonical name or documented alias; discovery shows the native
namespace/key and format/location restrictions behind it. An ExifTool-style name
is a convenience mapping, not the native identity. Reads return every match with
source/occurrence identity. A mutation requiring one destination refuses multiple
matches; it never picks the first. Unknown names return an actionable error.

For expert ambiguity resolution, propose
`metadata import --snapshot <snapshot.json> --intent <intent.json> <target>`.
The intent uses MDL-018's exact `(snapshotRef, occurrenceRef)` identity; trusted
sources are reread and rebound before a plan can exist. The target operand bounds
allowed destinations, and extra targets referenced by the intent are rejected.
Snapshot IDs are not reusable selectors against an unrelated later read. Synthetic
snapshots cannot authorize a real write. A
[bounded pure grammar](../legacy-compatibility/migration.md) is now proposed for
`--where`. Advanced typed assignment and executable extensions remain #0015 work;
an unsupported grammar must fail, not be passed to a shell.

`--set NAME=TEXT` splits at the first equals sign and supplies string text to a
registered string-valued field; it does not infer numbers, dates or booleans. Empty
text means empty string. Creating a missing occurrence uses an explicit creation
operation/insertion intent; ordinary `metadata write` updates existing occurrences.
Complex typed edits use intent files; the proposed `--set-json` shorthand remains
deferred until equivalent typed semantics are documented.

The exercised leaves have the following operand and option contracts. Shared
options retain the same meaning; options belonging to another leaf are errors.
These signatures do not imply that every leaf in the eventual tree is specified.

| Leaf | Required operands/options in these workflows |
| --- | --- |
| `metadata read` | One or more inputs, or one manifest; repeated `--tag` is optional. |
| `metadata write` | One or more existing targets and at least one `--set` for the simple-string form; a conflicting assignment to the same occurrence refuses. |
| `metadata import` | One target, `--snapshot` and `--intent`; these files supply typed intent rather than additional inferred operands. |
| `metadata copy`, `metadata sync` | One destination, one `--from`, selected `--tag` values and a named `--mapping`; sync adds `--conflict`. |
| `metadata diff` | Two explicit inputs; a difference is data, not failure. |
| `metadata export` | Input selection plus `--format` and `--output-file`; `--format csv` selects the artifact projection, while `--output` selects the command's result/summary representation. |
| `sidecar diff` | One RAW with an unambiguous existing sidecar; show the two source values. |
| `sidecar create` | One RAW, `--format xmp` and `--to`; destination must be absent and creation previews first. |
| `privacy inspect`, `privacy scrub`, `privacy verify` | Input selection and `--profile`; scrub additionally requires explicit `--target embedded|sidecar`. |
| `tags search`, `tags show`, `formats show` | One search term, canonical tag/alias, or format respectively; list leaves need no operand. |
| `plan show`, `plan apply`, `validate plan` | One saved-plan path; effect-changing overrides are invalid. |
| `recovery list`, `recovery show`, `recovery resolve` | List needs no operand; show/resolve require one owned transaction ID. |
| `backup restore`, `backup prune`, `batch resume` | Restore requires backup ID and target; prune requires explicit backup IDs; resume requires one batch ID. Each defaults to preview. |

`--save-plan` is allowed only on a mutation preview, not alongside application;
`--dry-run` and `--apply` conflict. `plan apply` with `--dry-run` is invalid; use
`validate plan` for applicability checks. No extra operand is silently ignored.

**CW-005 — Predictable input selection.** Explicit operands and one manifest
source are mutually exclusive. `--files-from` accepts UTF-8 JSON
`{"schemaVersion":1,"paths":["photo.cr3","other.cr3"]}`; relative paths are
relative to the manifest directory. `--files-from0` accepts NUL-delimited UTF-8
paths relative to the invocation directory; a trailing NUL is required. Only
these manifest options accept `-` for stdin; do not infer media bytes from stdin.
An empty entry, invalid text, duplicate JSON member or unknown schema fails preflight.
Platform paths that cannot be represented losslessly are diagnosed, never replaced.

Explicit input order is retained. Each directory expands its recognized in-scope
RAW members in ordinal relative-path order; recursion and hidden members are opt-in.
Sort by Unicode scalar values without locale collation or case folding, preserving
actual spelling. Recognize content/variant before processing; extension filtering
alone is insufficient. Explicit unsupported files fail; unrelated directory entries
are counted as excluded. Resolve physical duplicates once, report their aliases,
and reject conflicting mutation instructions for one physical file.

Directory discovery does not follow symlinks by default. `--follow-symlinks` permits
read traversal with identity-based cycle/deduplication checks; it never overrides
WS-010 mutation policy. Empty selection returns 1 unless `--allow-empty` is explicit.
Missing/unreadable explicit paths are per-input failures, not filter exclusions.

**CW-006 — Pair by explicit, reviewable rules.** `--with-sidecars` includes uniquely
associated XMP as a separate source; it does not merge values. Default discovery
uses the RAW stem plus `.xmp` in the same directory, treating XMP extension case
insensitively. Match the stem with the filesystem's name-equivalence rules, but
enumerate all candidates: two candidate sidecars or competing RAW owners are
ambiguous even if only one RAW was selected. Preserve actual path spelling.

Examples: `photo.cr3` can pair with `photo.xmp`; `photo.cr3.xmp` needs explicit
mapping. `photo.CR3` and `photo.cr2` cannot both silently claim `photo.xmp`.
Do not choose by newest timestamp or fall back to an adjacent unrelated XMP.
An explicit XMP operand must have a unique associated RAW or an explicit mapping;
this retains the current associated-sidecar scope.

`--pairing-file <file>` supplies a UTF-8 JSON object with `schemaVersion: 1` and
`pairs`, each containing exactly `raw` and `sidecar` path strings. Paths resolve
relative to that file; duplicate/conflicting owners and destinations are errors.
This is an association declaration, not permission to alter either file. It
overrides heuristic pairing for the named RAW inputs only. Existing media must
still satisfy input/capability checks.

`--target sidecar` selects the paired destination explicitly. Missing sidecars
are reported by reads; write/sync requires an existing sidecar and directs the user
to `sidecar create` if absent. Privacy verify cannot ignore a missing required scope.
`sidecar create --to <path> <raw>` records the association and creates only through
explicit apply. `--sidecar-dir` preserves relative subdirectories under one declared
input directory; multiple roots or duplicate destination names require a pairing
file. No automatic numeric suffixes or overwrites hide collisions.

**CW-007 — One-way synchronization is explicit.** `metadata sync --from <source>`
takes one existing destination operand, selected source tags, a named/versioned
mapping and `--conflict error|source|destination` (default `error`). The plan shows
both values and each destination occurrence. Do not silently synchronize both ways
or select by modification time. Equal values are unchanged; missing source values
never mean deletion. Unavailable/ambiguous source values refuse that mapping.

For the walkthrough only, `exif-copyright-to-xmp-rights-v1` maps one valid EXIF
Copyright string to the selected associated XMP destination's `dc:rights` language
alternative `x-default`.
It retains other languages, creates that property/entry if absent, and rejects
invalid text or multiple candidate source occurrences. That insertion is explicit
in this named mapping and plan. Existing unequal text invokes the conflict policy;
`destination` reports `skipped-policy`, and `source` proposes replacement. A skipped
conflict is never reported as synchronized. This is a proposed mapping, not a
universal tag conversion catalog. Other mappings remain individually specified.

**CW-008 — Menu navigation is reversible.** Enter guided mode only with
`interactive [command-path...]` or `--interactive`; require terminal stdin and
stdout. The menu builds the same request as the ordinary command. Back retains
choices; changing an earlier choice invalidates dependent choices and any plan.
Help returns to the same screen. Preview is the default final action; Apply is a
separate explicitly selected action enabled only after a current valid preview.
Never bind the first Enter after a preview to Apply.

Arrow keys/Enter navigate; Tab reaches Help, Back and Cancel. Provide an equivalent
numbered line mode (`--menu-style line`) with `help`, `back`, `cancel`, and explicit
`apply` at review. In text-entry prompts these words are values; navigation uses a
separate action prompt. Escape backs out; Ctrl+C exits with 130. Before application
no target changed; after application use WS-016. Use visible text labels, wrap at
40 columns without losing content, escape control characters in filenames/values,
and avoid color-only status. Do not require a mouse, function keys or cursor UI.

**CW-009 — Scripts never encounter a menu.** Redirected/unavailable stdin or stdout
suppresses prompts, pagers, cursors and progress. Explicit interaction in that state
returns 2 (`INTERACTION_REQUIRES_TTY`) before media I/O. Normal commands do not
prompt on invalid arguments or collisions. Completion suggests valid syntax and
documented values without mutation, private metadata reads or mandatory network
access. Path completion may enumerate paths only when requested. Completion shell
integrations must be tested later; no supported shell list is claimed now.

**CW-010 — Output intent is explicit.** `--output` selects the result representation;
`--output-file` names a new artifact. Read/export defaults to text unless structured
output is requested. JSON/JSONL retain the metadata model; CSV is a declared
projection with fixed selected columns and reported omissions, never a round-trip
edit format. XML and other reports in the broader command tree remain deferred.
Reject unsupported output/operation combinations before processing.

For a walkthrough of bounded streaming, use JSONL on stdout. A requested artifact
is staged and published no-clobber after successful completion; on failure an
incomplete owned artifact can be retained and reported, but never named as a
successful complete export. Shell redirection can truncate a file before imageinfo
starts; use `--output-file` when imageinfo's collision policy is required.

Binary stdout requires `binary extract --stdout` and exactly one resolved asset.
It cannot combine with structured stdout or `--output-file`. Resolve ambiguity
before emitting bytes; later interruption may leave a truncated stream with nonzero
status. Extraction copies stored bytes and leaves RAW media unchanged.

**CW-011 — Bounded work with honest completeness.** Enforce cumulative input bytes,
nesting, occurrence counts, allocations, output size, temporary storage and time
budgets. `--max-bytes` is the cumulative input-byte budget across the request,
including sidecars/nested reads; `--timeout` is total elapsed work time after parsing.
`--jobs` is positive, capped by the supported runtime policy and never parallelizes
edits to one physical file. Values and units are displayed in help/config; actual
numeric defaults require the [performance protocol](../performance/README.md) and
actual #0016 measurement before release.
Read batches also default to stop on failure; `--on-error continue` is explicit.

Large mutation requests finish whole-request preflight before any publication;
bounded private spill storage may be needed. Hitting its limit fails without media
changes. Streaming reads can emit earlier results, but limit failures downgrade
coverage and return failure. Bound ordered-output buffering; apply backpressure
rather than silently reordering records or allocating unbounded memory. Numeric
performance targets remain #0016 measurement work under the #0008 protocol. [Persistent framing](../legacy-compatibility/integration.md)
is now proposed; runtime validation remains #0015.

**CW-012 — Application binds what was reviewed.** Saved plans name exact sources,
destinations, policy/registry revisions, mapping losses and all effects under WS-002.
`plan show` explains them without treating the plan as trusted instructions.
`validate plan` reports current applicability without mutation; later apply still
revalidates. Plans cannot broaden their effects through command-line overrides.
Changing requested effects requires a new preview/plan.

No-op application reports unchanged with no backup or rewrite. No-backup means
discard recovery copies only after success. An unsupported embedded write reports
the exact restriction and offers explicit sidecar/new-output paths only when
independently supported. Preview must not claim a known unsupported operation is
applicable. A successful preview is not evidence that application will later succeed.

**CW-013 — Recovery explains before acting.** `recovery list` lists owned records;
`recovery show <transaction-id>` inspects identities and explains current uncertainty.
`recovery resolve <transaction-id>` previews WS-015's available finalization or
recovered-original classification. `--apply` authorizes that resolution, not blind
rollback or replay. Foreign/missing/untrusted artifacts remain recovery-required.
`backup restore <backup-id> <target>` is a separate fresh mutation with its own plan.
`batch resume <batch-id>` previews remaining eligible units and verifies receipts;
it never repeats a committed append. Unknown IDs do not become paths to follow.

**CW-014 — Status reflects the strongest unresolved consequence.** Use the
[result and status contract](results.md) for precedence, per-file outcomes and
incomplete streams. Recovery uncertainty has priority over cancellation or partial
success. A summary never replaces the individual file states. Privacy residuals
and uninspectable regions must remain visible even when a sidecar-only edit succeeds.

## Review tradeoffs and source boundaries

This proposes explicit application, conservative pairing, one-way sync and full
option names to make effects predictable. It also retains #0006's strict storage
guard, which may limit replacement support. These are recommendations for Terry's
review, not usability findings or promises of implementation.

Observed **2026-10-10**: AWS documents root/service/operation help and a separate
auto-prompt facility. They motivate discovery at every level; imageinfo's menus
and side-effect policies are original proposals. [AWS help](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-help.html),
[AWS auto-prompt](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-parameters-prompting.html).
These are live unpinned documentation pages, not a locked AWS release baseline.

Shell examples use literal quoting as documented by [PowerShell quoting rules](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules?view=powershell-7.5)
and [Bash single quotes](https://www.gnu.org/software/bash/manual/html_node/Single-Quotes.html),
also observed 2026-10-10 (PowerShell 7.5 documentation view; live Bash manual).
POSIX-shell examples avoid embedded quotes and expansion syntax. Complex values
belong in UTF-8 intent files; shell quoting does not change the metadata type.

# Native JSON syntax errors

**#0037**, implemented **2026-10-13**, closes the concrete syntax-output routing
gap under #0015/LG-006. Full legacy/API/session compatibility remains open.

Both invocations return status **2** and the existing version-1 result envelope:

```console
imageinfo --output json metadata read --bogus
imageinfo metadata read --bogus --output=json
```

The error envelope has a new request ID shared by request/summary, nullable unknown
operation/mode, one request issue, zero discovered inputs, no file/artifact records,
`selectionComplete: false` and a completed report's `outputComplete: true`.
Human diagnostics remain bounded plain stderr. No input discovery/read/extraction
is dispatched after a whole-request syntax failure.

## Selecting the error channel

Exactly one valid explicit `--output json` or `--output=json`, before a literal
`--`, selects JSON even if the command grammar fails. Its position relative to the
invalid option or command does not affect the channel. A distinct invalid option,
value, help/version request or duplicate color setting does not erase that selector.

Unknown/missing/duplicate output selection uses plain stderr and no JSON stdout.
This includes repeated identical JSON selectors: the scalar option is invalid.
Absent selection and explicit `text` keep the ordinary text boundary.

| Arguments | Error channel |
| --- | --- |
| `--bogus --output=json` | JSON stdout plus human stderr |
| `metadata read --values=bad --output=json` | JSON stdout plus human stderr |
| `--output=json version --output=text` | Plain stderr; ambiguous output selection |
| `--output=bad --bogus` | Plain stderr; invalid output selection |
| `metadata read --bogus -- --output=json` | Plain stderr; selector spelling is a literal operand |
| `metadata read --tag=--output=json --bogus` | Plain stderr; selector spelling is attached tag data |

Valid help stays plain text with status 0 even alongside JSON selection. Malformed
syntax still wins over help/version. No long-option abbreviations or legacy aliases
are guessed. Native argv remains `OsString`; non-Unicode output values refuse
without lossy decoding, while unrelated path bytes remain untouched.

## Small implementation boundary

Clap 4.6.7 remains the command validator. A private helper examines already separated
argv tokens only to select the error channel; it does not tokenize shell text, parse
media or produce an executable request. Current value-taking arguments reject
separate hyphen-leading values. Therefore `--output` outside `--` is an option, not
another option's data; attached values remain one token. A recursive command-tree
test protects this invariant if the grammar is extended. Existing hierarchical
help and successful request dispatch use the same command tree as before.

There are no new runtime dependencies, unsafe code, OS APIs or result-schema changes.
Output transport failure still returns nonzero; a truncated JSON stream is not a
complete report. This handoff changes error routing, not media read/write admission.

## Verification and remaining scope

Eight new contract tests per declared platform include **35 executable invocations**,
native argv checks, tree invariants, bounded/control-safe output and unchanged
authored-input bytes/mtime with no extracted output. Windows additionally checks
an unpaired UTF-16 selector; Unix checks invalid UTF-8 selectors/path bytes. Seven
tests are shared and one tests the platform's native argv representation.
All **44 local Windows root tests**, formatting, strict Clippy and release build pass.
Seven actual native JSON records validate against published local schemas using
the documented isolated QA validator. [CI](native-json-errors-ci.json) records
Windows, Ubuntu and macOS source verification separately.

Only this CLI error-routing cell closes. LG-001–005, broader LG-006 session/framing/
cancellation/accessibility/reference evidence and GAP-006/GAP-012 remain open under
#0015. Saved plans and metadata writes are not enabled by a JSON error envelope.

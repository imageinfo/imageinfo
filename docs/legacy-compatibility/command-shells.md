# Four-operation shell qualification (#0137)

This finite harness exercises extraction, advisory DateTimeOriginal preview,
explicit RAW/XMP pairing and metadata-read session startup/payload in actual
PowerShell 7 on Windows and Bash on Linux/macOS. Its
[authored ledger](command-shells/cases.json) fixes eight cases per operation.
Newline leaf names are Unix-only: Windows executes 28 cases and each Unix
platform executes 32. Shell version and OS release are recorded per run.

The selected literals contain spaces, Unicode, apostrophes, semicolons, dollar
signs, backticks, ampersands and brackets. Unix also uses an embedded newline.
All shell tokens use the existing [#0059 literal quoting method](native-paths.md).
No path is evaluated as a command, glob or variable expression. These are
explicitly declared PowerShell and Bash profiles, not cmd.exe, sh or arbitrary
shell compatibility.

## Executed boundary and independent bindings

Run from the repository root after building the selected executable:

```text
python scripts/check_command_shells.py --binary <built-imageinfo> --public-results <platform-result.json>
```

Each case runs one fresh shell script. That script first invokes a standalone
[argv/input witness](command-shells/argv_witness.py), then invokes imageinfo
directly with the identical literal token expressions. The witness records the
shell-delivered arguments and complete input bytes; it never launches imageinfo.
The checker independently compares those captures with the ledger-derived
tokens and payload. The direct imageinfo invocation separately checks the
selected input, operation-specific result, status, diagnostic channel and exact
output effects. The witness therefore cannot mask native argument handling by
relaunching or requoting imageinfo.

Authored source, explicit opaque sidecar and wrong-input decoy files are fresh
per case. Before/after inventories compare bytes, names, modification time,
mode, device/file identity, link count and Windows attributes. Extraction must
create exactly its fresh named authored `PreviewImage` bytes. The three preview
resources have distinct bytes and lengths, so selecting ThumbnailImage or
JpgFromRaw cannot satisfy this assertion. All original files
must retain their inventory. Ordinary filesystem access-time accounting is
outside this comparison. Altered-capture controls reject wrong sources,
operations, request/input identities, source effects, summary counts and
completion flags. Additional controls reject wrong Model typed values, tag
identity, view, resource binding, source size, session limits/counters/IDs,
date proposal, pair identity and extraction destination. Substituting each other
authored preview's actual bytes also refuses. These controls add no shell cases.

The session shell pipeline submits exactly one metadata-read frame and one close
frame. The witness checks exact UTF-8 input, including PowerShell's terminal CRLF
or Bash's terminal LF. Output must contain exactly ready/result/completion JSON
frames, canonical LF, matching IDs, the literal selected source and a successful
read. Model raw/normalized values must independently match the authored
`Canon EOS R5` ASCII field, with exact EXIF identity, unavailable display view
and a resource range bound to those source bytes. Summary and session frame/result
counts must match this one-read/one-close workload. These preassembled pipelines
qualify startup and bounded payload transport;
the existing [#0116 pipe tests](read-session-process.md) own incremental
ready/result visibility and process lifecycle.

## Results and limits

Actual reports are emitted only after every applicable case and assertion passes.
Each report binds the executable, checker, witness, ledger, fixture, relevant
source/dependency hashes and recorded shell version. Private captures retain
actual scripts, stdout/stderr, complete argv/input and per-case inventories.
Public reports retain authored argv, status, capture sizes, script hashes and
inventory/effect assertions; native file identities and timestamps stay private.
Use the exact final-source platform reports supplied with the handoff; an older
binary run is development evidence only.

Date preview remains an advisory refusal with its actual original/proposed bytes,
allocation and exact complement checked. Unicode pairing intentionally refuses
with `PAIRING_NAME_UNSUPPORTED`, because the current pairing profile qualifies
ASCII leaf names only. The other pair cases succeed without parsing RAW or XML
content. Neither refusal is counted as positive mutation or Unicode pairing.

The authored JPEG bytes are extraction sentinels, not entropy-valid camera
images. This is no camera/media qualification, exhaustive quoting matrix,
reference-executable parity, writer/storage admission, sidecar publication or
general non-Unicode wire-path claim. The named four-operation scope remains
unchanged by later CLI additions. Actual Linux/macOS evidence requires executing
this checker in those recorded Bash environments; code/schema review alone does
not establish either platform result.

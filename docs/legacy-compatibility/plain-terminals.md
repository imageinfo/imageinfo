# Plain terminal qualification (#0138)

The current CLI completes the 24 authored cases with redirected streams and
fresh Windows ConPTYs at 40 and 80 columns. All 15 current command/help nodes
are reachable through ordinary argument-based help. Help and diagnostics use
plain text, including `--color always`; guided mode explicitly refuses. These
observations qualify the declared plain-terminal behavior, not legacy parity
or a guided interface.

## Reproduce and inspect

Run the checker against a freshly built executable:

```text
python scripts/check_plain_terminals.py --binary target/debug/imageinfo.exe --public-results docs/legacy-compatibility/plain-terminals.results.json
```

Use the corresponding executable path without `.exe` on POSIX. The checker
creates an ignored fresh directory under `.local/plain-terminals/`, prints its
location and retains each redirected stdout/stderr pair, raw PTY bytes, rendered
40/80-column screens and a result record. No actual camera data is used. Earlier
unsuccessful harness attempts remain in their original directories; they are
not product passes. The published result binds the binary, authored ledger,
checker/helper and relevant source hashes. Rebuild and rerun after integration.

The authored ledger is [plain-terminals.cases.json](plain-terminals.cases.json);
the finite local result is
[plain-terminals.results.json](plain-terminals.results.json). The local Windows
run has 39 redirected invocations and 78 PTY observations. POSIX PTY support in
the same checker requires actual hosted execution before a Linux/macOS result
can be claimed; a local Windows result supplies no POSIX observation.

## Fixed case coverage

| Authored cases | Covered surface |
| --- | --- |
| 15 help cases | Root; `version`; `session`, `session read`; `metadata`, `metadata read`; `binary`, `binary list`, `binary extract`; `preview`, `preview date-time-original`; `sidecar`, `sidecar pair`; `compat`, `compat translate` |
| Two guided requests | Text and JSON return status 2 with `INTERACTION_UNAVAILABLE`; no menu or prompt opens |
| Two syntax refusals | Unknown read option; text stderr versus one JSON stdout envelope with plain diagnostic stderr |
| Two control-path requests | Missing literal operand containing ESC, CR, LF and TAB; text diagnostic escapes the operand; JSON carries the structured path as data |
| Forced-color help | Explicit `--color always --output json help` still emits text help with no producer terminal control |
| Extraction refusal | Missing required operands return a complete status-2 diagnostic without asking for input |
| Translation refusal | `compat translate --output json` explicitly refuses its incompatible selector; fixed translation transport is documented separately |

Every help case runs both `COMMAND --help` and `help COMMAND`. The root's
spellings are `--help` and `help`. These are keyboard-accessible argument
spellings; no mouse or raw key-reader is involved. All cases finish without a
response on stdin. Help for an operation does not qualify that operation's
media behavior; read/extraction/session/translation qualifications retain their
separate scopes.

The declared shell baseline remains PowerShell 7 and Bash. The separate
[command-shells.md](command-shells.md) qualification exercises literal shell
expressions and their actual argv/stdin. This checker executes the binary
directly so shell quoting cannot hide terminal behavior; its PTY evidence does
not itself prove shell syntax. No extra shell, completion or optional menu is
required.

## Wrapping and control-safety rubric

The following rubric applies to both widths:

- Help remains a vertical stream with visible command names, `Usage:`, option
  names and explanations. The 40-column screen uses ordinary terminal wrapping;
  it can split words and long option names across rows. The implementation does
  not promise width-adaptive, word-boundary reflow. The reader can follow the
  continuation rows; there is no clipping, horizontal-positioned application
  interface, alternate screen, pager or hidden interactive pane.
- The finite screen renderer must preserve every visible non-whitespace
  character from the redirected result in order. Each screen row is bounded by
  its declared width, with no scroll beyond the 100-row capture surface. The
  only content normalization removes display whitespace and replaces generated
  request identifiers; statuses, JSON structure, labels and other values remain
  checked. Request identifiers differ between actual processes.
- Redirected application output rejects terminal escapes, DEL and C1 controls;
  LF/CR/TAB are permitted stream whitespace. The authored control-bearing path
  must appear as a single escaped diagnostic operand, including literal
  `\u{1b}` and `\r\n\t`, rather than injecting a line or color sequence.
- JSON requests must decode as one versioned stdout envelope whose summary
  agrees with the process status. Error stderr is a plain diagnostic, while
  text refusals have empty stdout. Help explicitly stays plain text even with
  a JSON selector. A PTY merges channels, so machine-channel assertions use the
  separate redirected captures.
- Raw Windows ConPTY captures contain terminal-host initialization, cursor,
  erase, title and reset bytes. They are retained and rendered separately;
  they are not attributed to imageinfo. The renderer accepts only its explicit
  finite host-control set and rejects colors, unsupported cursor operations
  and mouse-tracking modes. Producer plainness is checked before this rendering
  against the redirected bytes. The POSIX branch uses a fresh actual PTY.

Each actual child has a ten-second deadline and a 1 MiB capture threshold;
overshoot of a pipe read or a redirected polling interval is possible before
refusal. Helpers own and reap only their fresh child, with no desktop input,
shell subprocess, existing terminal session, VM or external process control.

## Limits

This is finite authored evidence for current help/diagnostics and channel
behavior. It establishes no exact legacy-output parity, arbitrary Unicode
terminal-cell model, screen reader certification, interactive shell editing,
terminal-emulator portability beyond the observed backends, persistent session
cancellation, operation success or metadata/storage/write admission. Guided
mode remains unavailable; refusal is not a positive interactive capability.

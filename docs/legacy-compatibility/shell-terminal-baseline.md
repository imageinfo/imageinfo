# Declared shell and plain-terminal baseline (#0136)

The declared baseline is PowerShell 7 on Windows and Bash on Linux/macOS,
with argument-based contextual help and plain output. Contextual help remains
mandatory. Cascading menus remain optional; current guided requests explicitly
refuse. This consolidation reuses actual #0059/#0116/#0137/#0138 evidence without
requiring renewed adoption or human approval. Unmet compatibility requirements
remain engineering work under #0015.

The [finite ledger](shell-terminal-baseline/ledger.v1.json) retains nine exact
report bindings and two bounded future qualification manifests. Its checker
validates the recorded authored case IDs, applicability, expected statuses,
report hashes, shell versions and terminal observations. It also pins the exact
retained unrun limits, manifest states/environments/commands/bounds/oracles,
runner identities and historical session source/run/platform scope. Twenty-four
adversarial controls reject erased limits and invented qualification bindings:

```text
python scripts/check_shell_terminal_baseline.py
```

This is a historical evidence check. It executes no shell or product and does
not certify a later executable. Source, command inventory, shell or terminal
changes require the applicable actual qualification slice to be rerun.

## Tested matrix

| Evidence | Windows | Linux | macOS | Exact scope |
| --- | --- | --- | --- | --- |
| [#0059 native paths](native-paths.md) | 70/70 applicable; PowerShell 7.6.6 | 88/88; Bash 5.2.21 | 88/88; Bash 3.2.57 | 94 authored rows across direct native argv and actual shell invocation; metadata read and binary list only |
| [#0116 process/pipe session](read-session-process.md) | Actual hosted tests | Actual hosted tests | Actual hosted tests | Startup/help and actual pipes: incremental ready/result flush, request isolation, close/EOF, fatal/oversized framing, attempt cap and broken stdout |
| [#0137 four operations](command-shells.md) | 28/28 applicable, four Unix-only rows inapplicable; PowerShell 7.6.6 | 32/32; Bash 5.2.21 | 32/32; Bash 3.2.57 | Extraction, advisory date preview, explicit pairing, preassembled session payload; actual argv/stdin witness plus separate native effect checks |
| [#0138 plain terminals](plain-terminals.md) | 24 cases; Windows ConPTY | 24 cases; POSIX PTY | 24 cases; POSIX PTY | Each environment: 39 redirected invocations, 78 PTY observations at 40/80 columns; 15 help nodes, diagnostics, selectors and explicit refusals |

#0059's reports retain their original source/run and observation date: hosted
Linux/macOS source `4af340cdf9336da79f26564319649bbe12dd418c`,
[run 38784815175](https://github.com/imageinfo/imageinfo/actions/runs/38784815175).
Its Windows report is the separate local observation documented there. The 246
passes include expected refusals, with native non-Unicode behavior restricted
to the exact direct/shell rows and platforms in its ledger.

The three newer hosted columns bind source
`622e39c22e7d6f1cca9d761e3597e149f5007afb` and successful
[run 39043877139](https://github.com/imageinfo/imageinfo/actions/runs/39043877139)
on `windows-2025`, `ubuntu-24.04` and `macos-15`. Sanitized #0137/#0138 reports
are retained in [the baseline directory](shell-terminal-baseline/ledger.v1.json),
including actual OS/shell versions, platform-specific executable hashes and
relevant source hashes. Windows Server CI PowerShell 7.6.6 is distinct from the
earlier local Windows 11 PowerShell 7.6.7 run. No result is transferred between
those configurations. #0116's actual integration tests ran in that same green
source CI; #0135's later paused-consumer test in the suite has its separate
[backpressure scope](read-session-process.md).

#0137 uses 70 altered-capture controls per environment in addition to applicable
shell rows. Advisory preview refusals and Unicode pairing refusals retain their
actual expected classifications; they are not positive mutation/Unicode-pairing
capabilities. #0138's no-control producer output and complete visible output are
checked separately from terminal-host control bytes. Ordinary wrapping may
split long words at 40 columns. The finite renderer is not a universal emulator.

## Explicitly unrun coverage

| Surface | Disposition |
| --- | --- |
| Windows PowerShell 5.1, cmd.exe; zsh, fish, sh and arbitrary shells | Unqualified; not advertised by the declared shell baseline |
| Interactive profiles, editing and completion | Unrun; generated noninteractive scripts do not qualify them |
| Guided/cascading menus | Optional and unimplemented; current refusal is checked, not menu usability |
| Non-Unicode session wire paths | Unqualified; UTF-8 JSONL cannot inherit #0059's direct native-unit claims |
| Unicode terminal cell widths, screen readers, other widths/emulators/configurations | Unrun; current ASCII screen rubric and recorded PTY backends only |
| Session cancellation/signals and native failing stdin handles | Separate work; #0116 pipe EOF is not an input transport failure |

No broad shell/platform parity, reference runtime, all-path acceptance, media
qualification, writer/storage admission or RAW mutation follows from this matrix.
Help reachability does not establish the helped operation's positive behavior.

## Bounded next qualification slices

The ledger's `ST-REFRESH` manifest reruns the existing finite path/shell/terminal
checkers and session process tests against one frozen new executable per declared
environment. Retain failed attempts, exact hashes and original reports; record
actual shell/OS/backend versions. Change a tested cell only after all applicable
assertions pass. Existing harness bounds remain: #0059's 15-second/1 MiB capture
thresholds, #0138's ten-second/1 MiB thresholds and the process tests' watchdogs.
These harness limits do not promise product deadlines or resource containment.

`ST-NEW-COMMAND` prepares one newly advertised command at a time: simple, space,
Unicode and literal-metacharacter operands in all three declared shell
environments, both contextual help spellings and both terminal widths. Extend
the independent witness/effect oracle and help inventory before running it.
An expected refusal must stay separately classified. This manifest is unrun;
neither a specification nor a green older CI makes it a positive observation.

These are concrete ordinary engineering slices, not a permanent deferral of
current requirements or a new human approval gate. Future slices must name the
actual new command/profile or observed requirement gap; the baseline grants no
automatic compatibility claim for later additions.

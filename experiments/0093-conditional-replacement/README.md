# Conditional existing-target marker probe (#0093)

This isolated research executable measures one Windows standard-library pathname
replacement sequence. Every result has `productionReplacementAllowed: false`,
`committed: false` and `enabledProfiles: 0`. Even a successful marker rename is
an unqualified control. It is not a production writer or a source-removal command.

The caller must select a fresh absent directory under the repository's private
`.local` tree on the declared local NTFS test volume. The worker exclusively
creates that directory and four authored ordinary files:

| Entry | Bytes | Role |
| --- | --- | --- |
| `input.marker` | `INPUT093` followed by LF | Protected original input; always held against ordinary write/delete opens, never renamed or deleted |
| `candidate.bin` | `NEW093` followed by LF | Separately authored staging candidate; only this entry is supplied as the rename source |
| `target.bin` | `OLD093` followed by LF | Existing disposable target of the replacement trial |
| `unrelated.marker` | `OTHER093` followed by LF | Neighbor retained unchanged |

No existing root is reused, no caller file is imported, and no cleanup is
performed. Partial roots and every marker/control artifact remain for inspection.
Do not point the worker or qualifier at valuable files, original camera media,
guest captures or an existing transaction.

Build and run the finite independent actor suite from the repository root:

```powershell
cargo fmt --manifest-path experiments/0093-conditional-replacement/Cargo.toml --all --check
cargo clippy --locked --manifest-path experiments/0093-conditional-replacement/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0093-conditional-replacement/Cargo.toml
cargo build --locked --release --manifest-path experiments/0093-conditional-replacement/Cargo.toml
python experiments/0093-conditional-replacement/qualify.py --binary experiments/0093-conditional-replacement/target/release/imageinfo-conditional-replacement-probe.exe --parent .local/conditional-replacement --output .local/conditional-replacement-summary.private.json
```

The native test needs ordinary Windows sharing/link operations; the Codex
filesystem sandbox can deny fixture operations and is not a substitute Windows
profile. Keep raw captures, property/security snapshots and process logs private.
Only the curated finite observation summary belongs in source control.

## Worker protocol

The worker accepts `ABSENT_ROOT MODE`. Valid fixed modes are `target-guard`,
`source-guard`, `both-guard`, `unguarded-control` and `weak-target-control`.
Here `source-guard` means the staging candidate used as the rename API's source,
never the protected original input. The original input remains held in every mode.

The worker emits JSON lines with `event` values `ready`, `validated` and `result`.
The caller sends `continue` after each of the first two events and `exit` after
the result. A refusal can go directly from `ready` to `result`. Handles remain
live through the result gate so an independent observer can check the actual
state. Gate input is bounded to 32 bytes and fixed strings. Marker reads are
bounded to 64 bytes. Controls deliberately omit the final renewed check; their
outcomes cannot satisfy admission.

See [the boundary and observations](../../docs/write-safety/conditional-replacement.md).
The final [29-case observation summary](qualification.json) and
[independent standard-library review](stdlib-review.md) retain exact source/tool
bindings and distinguish API controls, native refusals and pre-effect refusals.
The exact dependency versions already have root
[admission and retained notices](../../docs/foundation/dependencies.json);
this package reuses that graph, including safe `same-file` and `winapi-util`
handle-information operations. No third-party implementation or native SDK
wrapper is copied into this experiment; research source forbids unsafe code.

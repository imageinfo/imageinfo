# Native receipt-property observation (#0106)

This marker-only diagnostic keeps the frozen F869 actor unchanged and builds a
separate `ordinary-receipt-properties` observer from the #0032 research crate.
The [bounded method and limits](../../docs/write-safety/receipt-vmoff-properties.md)
describe the experiment. It enables no production writer, repair, profile or RAW
capability.

`qualify.py` uses the existing private guest transport and retained installed
evaluation guest. `console.py` operates only its verified private QMP console,
using the existing standard account and process-local PowerShell invocation.
It never changes the host desktop or persistent execution policy. The frozen
initial verifier is retained as `audit.py`; `audit_final.py` independently reads
the captures with corrections for imported historical line endings and explicit
cross-source inventory disagreements. It does not import the controller or
access a guest disk. `audit_continuation.py` adds independently checked labels
for the two authorized read-only retries and emits the final public summary.
None of these verifiers edits the evidence.

Before collection, freeze the complete observer sources with canonical LF,
build a static executable, run its Rust checks, and preserve its exact source
hashes. The observer freeze deliberately omits the concurrently developed
restore module and its two routing declarations. It contains the exact published
`ordinary.rs` observer. Its executable is distinct from both F869 and the final
integrated research executable.

The retained actor must hash to
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`.
Supply the accepted 93-case native audit, its original source binding and its
complete frozen source tree. The controller verifies all 22 source digests.
Do not substitute an observer build for the actor.

Run the controller under the ordinary WSL operator. `prepare` requires a new
private overlay root and a stopped installed base; it copies only TPM/firmware
state and uses the original disk as a backing file. Use the existing launcher
for that new root, which drops the guest emulator to the ordinary owner.
Serve the two fixed executables with `serve`; sign in/bootstrap through
`console.py` only after checking the guest console. Preserve setup failures
separately from the final nine-cell collection.

The `run` command requires `--root`, `--actor`, `--observer`, `--frozen`,
`--baseline`, `--actor-binding`, `--actor-frozen` and an absent `--output` directory.
It creates nine fresh marker transactions. Four cells call QMP `quit` on the
verified overlay emulator and confirm process exit; no host, NMI, OS-crash or
physical-power command is available. All interruption/restart artifacts remain.

After collection, run:

```text
python audit_continuation.py --root CAPTURES --actor F869_EXE --observer OBSERVER_EXE \
  --frozen OBSERVER_SOURCE --baseline ACCEPTED_NATIVE_AUDIT \
  --public NEW_PUBLIC_SUMMARY
```

The public summary exposes stage/field differences and finite counts; private
identities, paths and timestamps remain in ignored capture storage. A failure is
retained, never converted into a passing observation or an admission claim.

# #0022 option A source/output protocol

Research implementation under the existing In progress **#0022**, after Terry's
explicit OD-11 option A decision on **2026-10-14**. No new card is pulled into work.
Rust lives in the existing [#0032 crate](../0032-windows-publication/README.md), with
the same dependencies and reviewed SDK. Root production code/unsafe policy is unchanged.

```console
cargo test --locked --manifest-path experiments/0032-windows-publication/Cargo.toml
cargo build --locked --release --manifest-path experiments/0032-windows-publication/Cargo.toml
python experiments/0022-ordinary-output/qualify.py --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --parent .local/ordinary-output-qualification
python experiments/0022-ordinary-output/audit.py --root <retained-private-run> --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --public docs/write-safety/ordinary-output-observations.json
```

The probe uses an explicitly selected new private root with fixed `source.marker`,
`candidate.marker`, `output.marker` and three record leaves. `ordinary-prepare`
creates an exclusively owned root and authored 64 KiB source; `ordinary` opens the
existing source read-only and copies its exact bytes while retaining default-stream
byte/name guards. Only this known marker payload is accepted, never camera media.
The ordinary private-owner policy is used at creation throughout; no source sealing,
DACL release call or owner/privilege changes are performed by the worker.

Checkpoints cover source preflight, prepublication properties, and installed output.
The candidate is renamed by its creating handle without replacement. Successful
namespace calls are distinct from passed installed checks and qualified persistence.
All outcomes remain observation/recovery-required; there is no committed receipt or
production profile. Before publication, cooperative cancellation checks and deletes
only live files created by this invocation through retained handles, preserving the
input/root/foreign entries. Once a namespace call is attempted, artifacts remain.

`ordinary-inspect` bounds and validates typed checksummed records and actual fixed
artifacts read-only; it grants no repair. `ordinary-admit`, `ordinary-finalize` and
`ordinary-prune` refuse before effects. Legacy #0032/#0036 commands remain separate.
Other OS filesystem adapters refuse; portable record/staging tests still run there.

Native qualification has 64 cases: byte/name actors and late aliases, property changes
at the observation boundaries, preexisting writers/mappings, foreign collision,
eight kill/cancel/failure boundaries, ordinary owner editing after exit and restart
record/namespace conflicts. Property-only actors intentionally alter newly owned
test markers. No user media/original ACL is touched. Inventories verify 56 read-only
inspection runs leave bytes, identity, modification times, attributes and link counts
unchanged, apart from normal access-time semantics. Inaccessible files stay untouched.

Two labeled malformed producer-stream cases retain partial stages and pending work
even when copying fails before the owned-artifact constructor returns. They do not
simulate or claim native ENOSPC/EIO. The logical staging cap is 262,144 bytes: one candidate plus three bounded records;
source and old retained runs are excluded. Reads/records are bounded to 65,536 bytes,
control lines to 32 bytes, process watchdogs to 60 seconds and message waits to 15.
These are not OS quotas or hard I/O deadlines. Local NTFS observations do not prove
all future interleavings, kernel versions, providers, OS crashes or physical power loss.

`windows_guest.py` prepares a disposable official evaluation guest for the separate
Windows interruption qualification. Generated credentials/ISO/disks/state/captures
must stay private. It exposes no host disks/shared folders; QEMU opens KVM using
the existing root launcher then drops to the ordinary WSL uid/gid before guest code.
The Windows worker runs as a standard local test user; provisioning/crash settings
belong only to this disposable guest. See [the guest notes](../../docs/write-safety/windows-guest.md).

After installation, verify the actual guest build, evaluation state and standard
worker token, then set `installed: true` in its **private guest manifest** before
fault qualification. Installed launches detach both installer media. Start the
loopback controller with the statically linked marker worker, then run inside WSL:

```console
python3 experiments/0022-ordinary-output/guest_qualify.py --root <private-installed-guest>
python3 experiments/0022-ordinary-output/guest_actors.py --root <private-installed-guest>
python3 experiments/0022-ordinary-output/guest_audit.py --root <retained-private-qualification> --binary <exact-static-worker> --actors <retained-private-actors> --public docs/write-safety/windows-guest-observations.json
```

The driver captures eight NMI-induced Windows bugchecks followed by controlled
emulator quit/relaunch, and eight separate emulator SIGKILL/relaunch observations.
It records the reached barrier before injecting a fault, rejects old boot messages,
and requires fresh Windows bugcheck evidence for NMI cases. Guest logon startup can
be delayed; the same mutex-protected agent is started through the private QMP
console after a boot interval. No host console or disk is targeted. The audit checks
the exact case set, fresh distinct bugcheck events, standard tokens, retained marker
bytes and truthful permission flags. Capture manifests, logs and screenshots remain
private. Controlled exit may drain submitted disk work; physical power loss,
Windows warm-reset reliability and durable namespace/receipt success remain separate.

The five guest actor cases check held source/candidate data refusal, the .NET
timestamp setter's distinct write-access refusal, preservation of a competing
output name, and ordinary owner editing after exit. This setter's refusal does not
establish continuous property exclusion; the native 64-case property actors use
minimal native access and can change timestamps. Admission/finalization/prune remain refused with unchanged
artifact byte inventories. These supplement the broader 64 native cases; they do
not expand the supported storage or RAW scope.

The next direct #0022 increment compares buffered publication, an immediate
post-rename held-file flush, and a write-through candidate/record handle. See
[ordering, SDK review and limits](../../docs/write-safety/windows-persistence.md).
All variants remain observation-only. Run the reproducible comparison/audit:

```console
python experiments/0022-ordinary-output/persistence_qualify.py native --binary <native-worker> --parent <private-native-parent>
python experiments/0022-ordinary-output/persistence_audit.py native --root <native-run> --binary <exact-native-worker> --public docs/write-safety/windows-persistence-native.json
python3 experiments/0022-ordinary-output/persistence_qualify.py guest --root <installed-guest>
python3 experiments/0022-ordinary-output/persistence_audit.py guest --root <guest-run> --binary <exact-static-worker> --public docs/write-safety/windows-persistence-guest.json
```

Guest subsets use `--modes`, `--kinds` and `--phases` with comma-separated known
labels. Multiple audited runs use repeated `--root`. A source binding and retained
loaded driver accompany each guest run; host boot continuity is independently
recorded after the run. Do not reuse a historical source/binary label for a changed
worker, or infer a qualified receipt from a passing finite observation matrix.

## Caller-directed restart actions

The direct #0022 restart increment adds `ordinary-restart-prune` and
`ordinary-restart-observe`. Read the [authority, evidence and remaining gates](../../docs/write-safety/windows-restart-actions.md)
before using them. These remain bounded authored-marker research; legacy
`ordinary-prune`, `ordinary-finalize` and `ordinary-admit` still refuse.

The live supervisor retains the emitted `callerContext` outside the editable
transaction. Prune requires its before-publication context and an explicit
`stoppedBeforePublication: true` attestation made only after proving that the
original worker stopped without permitting its namespace call. A saved context
whose worker later attempted publication cannot authorize prune. JSON parsing
does not authenticate the caller or establish that history.

Each restart request begins with one compact context JSON line on standard input,
bounded to 65,536 bytes. Subsequent control lines answer the emitted barriers with
`continue`, `cancel` or `fail`; each control line is bounded to 32 bytes. For a
supervisor-prepared request file containing that context and the appropriate
controls, PowerShell invocation is:

```powershell
$probe = 'experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe'
$root = '<absolute-owned-marker-root>'
Get-Content -LiteralPath '<authorized-prune-request.private.txt>' | & $probe $root ordinary-restart-prune
Get-Content -LiteralPath '<authorized-observe-request.private.txt>' | & $probe $root ordinary-restart-observe
```

These are separate requests for their respective operation states, not a prune
followed by observation on the same root. The qualifier supplies contexts and
controls interactively and captures exact stop/action history:

```console
python experiments/0022-ordinary-output/restart_qualify.py --binary <native-worker> --parent <private-native-parent>
python experiments/0022-ordinary-output/restart_audit.py --root <native-run> --binary <exact-native-worker> --public docs/write-safety/windows-restart-native.json
python3 experiments/0022-ordinary-output/restart_guest.py --root <installed-guest>
python3 experiments/0022-ordinary-output/restart_guest_audit.py --root <guest-restart-run> --binary <exact-static-worker> --public docs/write-safety/windows-restart-guest.json
```

Native evidence has **61 cases**, including fresh guards, foreign/changed artifact
refusals, reader deferral, exact context binding and partial action retention.
The guest audit covers **five faults in three scenario sets** with fresh boots:
unpublished prune, observation creation followed by interruption and renewed
context validation, and interrupted partial prune whose original-context retry
refuses. The renewed three-record context is emitted after observation-file flush
before `restart-record-file-flushed`; an old two-record context refuses the newly
present record. Source and root remain, and all commitment/profile flags stay false.

No caller-context persistence service, replay, rollback, source ACL rewrite,
privileged production helper or cryptographic authentication is introduced.
Durable context custody, complete namespace/receipt and storage-error qualification,
physical power loss and independent RAW admission remain open.

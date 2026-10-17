# Production single-output interruption method

**#0175 prepared method, 2026-10-17.** This is the finite execution and retained-
evidence plan for the actual internal production Windows adapter/runtime. The
[fixed machine ledger](production-vmoff-cells.json) starts with twelve prepared
cells and sixteen NR obligations. Its source/test links identify complementary
software controls; source presence does not establish that a test ran. Nothing in
this method reports an actual guest run, a qualified profile, `Committed`, RAW
permission or a public apply capability.

The implementation under test is [the production runtime](publication-runtime.md),
[phase-bound live acknowledgements](live-acknowledgements.md), and its existing
inspection/finalization/cleanup/resource mechanisms. The actor is the Windows-only
ignored library test in [qualification.rs](../../src/storage/qualification.rs).
It invokes the ordinary unqualified production paths with fixed authored marker
bytes. It does not invoke a test-admitted profile or the research worker.

## Freeze and exact profile

Before the first cell, independently review and freeze the actor, production
source inventory, native facade, Cargo.lock, pinned toolchain, built test executable,
controller, guest observer, auditor, this method ledger and native baseline outputs.
Retain SHA-256 for every file and exact commands/arguments; freeze uncommitted source
by a complete relative-path digest manifest rather than pretending HEAD alone
identifies it. Use the reviewed same executable and same profile for every cell.
Retain the freeze review and preflight before execution. A changed source, executable,
checkpoint or storage/cache configuration requires an explicit new candidate and
review, not replacement of the original evidence.

The ledger's `profile_required_fields` is the exact inventory for the private
profile manifest. Record actual Windows edition/version/build/architecture, account
kind, boot identity, local NTFS volume identity/size/cluster size, controller and
driver, emulator version/executable/arguments, virtual disk format and complete
backing chain, guest/host cache settings and host OS/boot. Record the actual actor
build, toolchain and invocation plus the source/adapter/facade/tool digests. Do not
substitute a host NTFS observation for guest volume facts. Unknown or unsupported
facts are an explicit refusal, not an inferred supported profile. Hash and retain
the profile; bind launch, off target and restart to that exact profile.

The host controller independently verifies the disposable guest process, backing
paths and launch configuration before VM-off. The frozen VM-off operation is the
QMP `quit` command: graceful emulator exit while the guest actor is held at its
requested gate. The emulator may perform cleanup and flush buffered writes during
exit. These cells make no abrupt emulator-termination or SIGKILL claim. Only that
controller operates the guest. Retain the actual QMP request/response, emulator
process exit and fresh guest boot observations. The host stays running and host
caches survive; emulator/storage behavior is bounded by this exact profile. The
three existing VM-off rows use this one declared choice without an added cell,
retry or alternate termination mode. These observations establish no physical-power
survival. The accepted
[power-test policy](power-test-policy.md) requires no NMI/bugcheck, host crash,
hardware, power cuts, new license or evaluation rearm.

## Fixed twelve-cell matrix

Run exactly one attempt per row, preserving failed, timed-out, unsupported and
partially completed attempts. Keep the denominator twelve. There is no adaptive
retry, checkpoint search, arbitrary actor schedule or Cartesian multiplication of
all fault types. Normal shutdown/restart management may be needed between cells;
that lifecycle does not add a qualification cell.

| Cell | Requested operation | Gate and meaning |
| --- | --- | --- |
| normal | Ordinary uninterrupted run | No gate; retain the actual terminal result. |
| kill-candidate-ready | Terminate owned actor | Native candidate check returned, before check acknowledgement/candidate flush. |
| kill-intent-ready | Terminate owned actor | Native intent check returned, before acknowledgement/intent flush. |
| kill-possible-publication | Terminate owned actor | Runtime already marks publication possible, before native publish API entry. |
| kill-installed-ack | Terminate owned actor | Native installed check returned, before runtime acknowledgement. |
| kill-receipt-before-ack | Terminate owned actor | Receipt creation returned, before receipt check/flush/acknowledgement. |
| kill-final-success-response | Terminate owned actor | Actual complete runtime predicate/terminal export returned; unqualified result remains refused. |
| vmoff-possible-publication | QMP `quit` the disposable VM emulator | Same conservative pre-API gate as the process-kill row. |
| vmoff-receipt-before-ack | QMP `quit` the disposable VM emulator | Same receipt-creation gate as the process-kill row. |
| vmoff-completed-predicate | QMP `quit` the disposable VM emulator | Actual complete runtime predicate, separately emitted after final response. |
| kill-restart-finalize | Terminate owned actor | Surviving original caller freshly guards and explicitly finalizes; gate after receipt creation. |
| kill-partial-cleanup | Terminate owned actor | Explicit original-caller cleanup; gate before the next removal after one actual successful removal. |

The selected possible-publication boundary is **pre-API conservative**, frozen in
the ledger. The runtime's possible-publication flag is already true; this is not
a claim of interruption inside a syscall or after publication. A diagnostic
`publication-api-response` event may exist, but is not a replacement/additional
cell. The final response/completed predicate does not become `Committed` merely
because every unqualified runtime call completed.

The actor writes a sequence-numbered JSONL diagnostic through ordinary buffered
guest I/O, with readable framing but no diagnostic `sync_all`/device-cache flush.
The actor emits each canonical event as an `IMAGEINFO175` stdout line, flushes
the private pipe transport and blocks at the requested gate. The controller drains
that owned child stdout, validates the event schema and child PID, and accumulates
the complete canonical LF-framed prefix in `pipeEvents175`. It sends that prefix
over HTTP as `eventFileBase64` to the host journal before fault. The host retains
that prefix and binds its digest, PID and checkpoint before terminating its owned
actor or stopping the verified disposable VM. Checkpoint evidence comes from this
host-retained owned-child stdout/private-pipe prefix. The guest diagnostic file is
separately captured as `guestDiagnosticBase64`; it is not the gate source and its
post-VM-off tail is not guaranteed to survive. Ordinary buffered writes may still
reach storage; their survival supplies no additional protocol acknowledgement.
The actual production protocol file/parent flush schedule remains unchanged; a
diagnostic must not force a volume/device flush before the tested protocol boundary.
An armed gate is not evidence of an actual kill/off. The controller retains
separate fault/exit confirmations. A gate never reached
is a refused/unsupported cell, retaining the actual earlier outcome. Do not invent
the requested boundary from a process exit or missing output.

## Independent before/after and effects

Freeze and use the separate read-only native observer and retained-evidence auditor;
neither may use actor-generated inventory as its sole artifact oracle. Independently
snapshot source, root, namespace and each surviving file before the operation and
after confirmed process exit or fresh guest boot. Read actual retained bytes via
new handles and record identities, hashes, lengths, owner/DACL, attributes, timestamps,
links, streams and read errors. Keep snapshots private because they contain local
account/path facts. Preserve every partial artifact and failed read.

Run a fresh actor `inspect` process with a fresh notice destination between two
independent snapshots. Compare both snapshots so that read-only inspection has
actual effect evidence. Inspect never overwrites the original event file. Bind
requested and observed checkpoints, exact executable/tools, actual guest boot
change and unchanged host boot independently of the actor's claims. Every reader
or operator continuation remains explicit; no silent retry/replay.

For each actual cell, independently assert these exact ledger obligations:

- Source object and bytes are preserved; output and record names, objects and
  bytes are classified against the original observations.
- Relevant properties are compared with original observations; drift is retained
  and never rebased into the expected snapshot.
- No publication replay, unowned deletion or imported authority occurred; actual
  terminal status and pending work match the observed effects.

Record holds/contradicted/unknown and the retained evidence for each assertion.
An absent output after possible publication does not authorize prune. A matching
output, receipt bytes or read-only classification does not restore the lost caller.
The finalize/cleanup cells exercise a surviving live original caller's explicit
authority before termination; after kill/off that authority is lost. Later inspection
has no repair authority. Do not deserialize authority from any manifest/event.

## NR-01 through NR-16 complement

The [NR protocol](namespace-receipt-protocol.md) defines the obligations. The
machine ledger maps all sixteen individually to cells and exact existing test
selectors, retaining `model` versus `native-software` evidence kinds. Candidate
length/failure controls cover NR-01; runtime/native before/after/error/lost-response
controls complement NR-01–14. Collision/property/cancellation controls complement
NR-04–06. Acknowledgement-binding model controls complement NR-08/12/13/14.
Fresh-finalization failures/conflicts complement NR-15, and actual cleanup
partial/stale/foreign-object controls complement NR-16. Record actual baseline
commands/results/digests separately. Test names or a normal run alone do not prove
all failure premises. Unsupported profile/acknowledgement premises remain explicit;
review NR sufficiency alongside software/native evidence without multiplying VM cells.

Historical [receipt timestamp drifts](receipt-vmoff-properties.md) and
[name-survival counterexamples](windows-guest.md) remain unchanged evidence for
their original workers/profiles. This campaign targets the new production
implementation. No original snapshot is rebased, no old contradiction is erased,
and no new cell exists solely to restate research limitations.

## Reference checker and handoff

Run `python scripts/check_production_vmoff_trace.py` and
`python scripts/test_production_vmoff_trace.py`. These validate the prepared ledger,
fixed twelve/sixteen denominators, source selectors and authored negative controls.
They are not actual guest evidence.

An optional private `imageinfo-0175-trace-v1` envelope can be checked with
`--trace FILE --evidence-root DIRECTORY`. It binds `method_sha256`, a `profile`
reference, all twelve ordered `cells` and sixteen ordered `nr_trace` rows. Every
reference is `{path, sha256}`, relative to the evidence root and checked against
actual retained bytes. Cells use `prepared`/`refused`/`actual`, preserving a separate
verdict. Actual cells bind before/after/classification/independent-audit/events (using the
host-retained event transport for checkpoint evidence),
armed-gate/fault confirmation and, for VM-off, guest-restart confirmation, plus all
ledger assertion names. NR rows retain the exact software-control list and typed
evidence kind. The test module contains authored shape examples.

The checker validates reference integrity and bookkeeping only: arbitrary JSON
is not authenticated history, a referenced report may contain errors, and a digest
does not prove its assertions. The independently implemented retained-artifact
auditor establishes reconciliation; the reviewer judges each NR obligation from
that evidence. No checker output admits a profile or authorizes effects.

Preserve `consistent`, `inconclusive` and `counterexample` outcomes distinctly.
A counterexample names the exact contradicted predicate and a concrete correction
scope before any repeat; the trace requires its evidence reference. Parent creates
the correction ticket where required. It blocks only that predicate, and never
justifies deleting/relabeling failed cells or silently running another attempt.
The final handoff records all twelve outcomes, native/software complements,
remaining unproven predicates, independent review and VM-off/cache limits. Actual
qualification and later exact profile admission remain separate decisions.

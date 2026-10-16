# Exact backend admission ledger and refusal model

**#0051 bounded documentation/model handoff, 2026-10-15.** The
[actual-observation ledger](profile-admission-ledger.json) assembles the accepted
child evidence without promoting it into backend qualification. **No actual profile
is supported.** The [read-only model](../../experiments/0051-profile-admission/admission.py)
accepts only the declared candidate configuration for inspection and returns
`refused-before-target-effects`. It exposes no target mutation or worker API.
Production publication, RAW admission, repair and automatic recovery are always false.

The ledger is an evidence inventory and refusal decision, not an executable plan,
authorization token or receipt. Its hashes bind reviewed public evidence bytes;
they establish neither caller authority/freshness nor the truth of a qualification
claim. An imported or edited `qualified` status is rejected by this actual-observation
revision. Future profile enablement requires new implementation evidence and review,
not a JSON status change. #0051 can finish this bounded deliverable while #0022 and
its capability gates remain open.

Binding maintenance, **2026-10-16**: #0118's accepted option-A disposition changed
the public `write-admission.md` document. The ledger's single hash for that input
was refreshed; all cells, findings, statuses, requirements and refusal outcomes
remain identical. All 209 portable model cases were rerun successfully against
the refreshed ledger, with no worker, VM or media operation. The original
versioned model report remains historical at its recorded ledger identity.

Terry's accepted [power-test policy](power-test-policy.md), 2026-10-15, removes
physical-power and dedicated-hardware qualification from admission. This FOSS
project makes a bounded best-effort claim, with future power testing limited to
turning VMs off. There is no physical-power required cell, replacement hardware
gate or missing physical fixture that blocks this ledger. Existing guest OS-crash
observations remain historical evidence; repeating NMI/host-crash tests is not a
prerequisite. The other correctness, format, storage and RAW gates remain intact,
and this policy change enables no writer.

The declared candidate has one authored 65,536-byte marker source, a fresh private
root, one held candidate, expected-absent same-volume output, four bounded records,
explicit external caller context and OD-11 option A. It is the #0047 **system-volume**
fixture: Windows 11 EnterpriseEval build **26300**, x86_64 QEMU, `q35,accel=kvm,smm=on`,
local NTFS, guest SATA with QEMU `if=ide`, QCOW2 image, `cache=writeback`, and the exact
static F869 worker SHA-256 recorded in the ledger. The architecture/machine/drive
arguments are recorded in the existing
[launcher](../../experiments/0022-ordinary-output/windows_guest.py), and the
[guest evidence](namespace-receipt-guest.md) binds the actual interrupted fixture.
Unknown OS servicing details and host device/cache behavior are disclosed limits
of the declared observations, rather than requirements for physical qualification.
The actual OS/build, filesystem, controller, request ordering and cache settings
remain explicit configuration boundaries.

| Combination | Current decision and evidence boundary |
| --- | --- |
| Declared system SATA/NTFS/QCOW2/writeback marker candidate | Refused: namespace and receipt acknowledgements, durable current custody and production integration remain unqualified under the declared best-effort contract. Physical-power or dedicated-hardware tests are not prerequisites. |
| #0048 secondary USB-hotplug raw/NTFS native-error fixture | Separate refused observation scope. It is a disposable 128 MiB raw disk with one NTFS partition at LBA 2048, distinct from system C. Its native error cells cannot qualify the system SATA image or a combined storage stack. |
| Other OS builds, architectures, filesystems, controllers, caches, worker binaries or publication sequences | Exact configuration mismatch; refuse before target effects. Linux/macOS model results cannot qualify this Windows backend. |
| Replacement, cross-volume move, network/cloud/removable production output, pair/batch publication, restore, broad prune and automatic recovery | Excluded from this candidate; independently scoped qualification remains required. An exclusion grants no capability. |
| CR3/other RAW or XMP publication | Independent format and workflow gates remain required. Marker evidence supplies neither mutation admission nor a sidecar writer. |
| Portable hypothetical all-required-premises conjunction | Supported test input only. Logical satisfaction never becomes a supported actual profile, target action or production result. |

The secondary observation configuration is recorded separately in the ledger:
134,217,728 raw disk bytes; MBR partition LBA 2048 with 260,096 sectors
(133,169,152 partition bytes; NTFS reports 133,165,056 filesystem bytes).
Its actual QMP backend is `raw` over `file`, device `usb-storage`, on the existing
`qemu-xhci` controller with its bus automatically selected. No explicit secondary
cache flags were supplied; backing host storage/cache behavior beyond the observed
methods is a disclosed limit. Actual QMP `query-block` reports `writeback=false,direct=false,no-flush=false`;
the named `file` and `raw` block nodes each report `writeback=true,direct=false,no-flush=false`.
These are distinct observations at different layers, not one inferred uniform
cache setting. This is not the system image's explicit `cache=writeback` profile.

The system guest evidence's process kills, emulator kills and NMI bugchecks are
different failure methods. Host caches remain alive. The accepted #0047 child
records **two timestamp-drift/property-refusal cells** at `receipt-written`; the
cause remains unproven. Matching bytes/names and the other matching property pairs
do not erase those counterexamples. An observational receipt is not #0045's qualified
outcome receipt and cannot attest its own future flush. Likewise, accepted #0044
caller-history guest observations do not supply automatic durable current caller
authority or freshness. Same-byte snapshot replacement remains accepted by that
bounded history mechanism.

The separate [#0106 disposable-overlay diagnostic](receipt-vmoff-properties.md)
adds integer native observations around four controlled VM-offs. Both
`receipt-written` VM-off cells show native receipt last-write drift and frozen
inspection refusal. One first rich inventory also reports a receipt size that
disagrees with independently captured bytes and later native information. Two
read-only operator continuations and their uncertain extra observations remain
explicit. This updates the `property-policy` evidence inventory while retaining
its counterexample status; it neither establishes the cause nor requalifies the
original storage configuration or another ledger cell.

The fixed eleven required cells cover exact configuration, continuous byte/name
guards, property boundaries, namespace acknowledgement, receipt acknowledgement,
caller custody, native storage errors, cumulative resources, restart actions,
production workflow and independent format admission. A missing,
duplicate or unknown cell rejects the ledger. `observed`, `unqualified`,
`counterexample`, `missing`, `pending` and `excluded` are all nonqualifying statuses.
An obsolete physical-power cell or fabricated hardware-qualification field is an
unknown input and is rejected; its absence is not a refusal reason. No remaining
required cell can disappear through an applicability flag or exclusion. Missing
or changed bound evidence, omitted criteria, unsupported configuration, duplicate
JSON members and unsupported qualification claims also refuse before effects.

#0049 supplies the measured finite live-supervisor resource increment, including
actual receipt/custody constructions, checked arithmetic and retained incomplete
charges. Its 655,360-byte charge is logical admission, not free-space reservation,
physical allocation quota or persistent global accounting. #0050's former physical
fixture requirement is withdrawn by the accepted policy and contributes no blocker.
Other missing correctness evidence still refuses future backend application.
#0048's
[five-cell native audit](native-storage-failures-native.json) records one normal
control and four actual worker storage-full `os error 112` failures: zero-byte
candidate, 32,768-byte partial candidate, failure before the prepared record and
failure before the receipt. The latter retains a 65,536-byte output, three prior
records and a zero-byte receipt. Source and read-only inspection inventories remain
unchanged, with no removals. Read/device-flush and isolated metadata-only errors
remain unrun/unqualified. These are actual storage errors, distinct from injected
control failures; incomplete secondary-volume class coverage and absent cross-device
qualification keep this required cell unqualified.

Every **WS-001–WS-024** and **SAF-001–SAF-016** criterion has an explicit entry in
`criteriaTrace`, naming required cells, the obligation retained, and whether a
separate required product scope is excluded from the marker candidate. This includes
plan/apply authorization, exact metadata semantics/no-op handling, preservation,
properties, original recovery, phase ordering, truthful outcomes, cancellation,
partial groups, rename/restore/prune, privacy, authenticity and backend verification.
The trace is completeness bookkeeping, not evidence those 40 criteria passed.
There is no shortcut from child acceptance to full WS/SAF coverage.

The [portable results](profile-admission-model.json) record **209 checked cases**:
every required-cell omission/duplication/nonqualifying status, editable qualification
claims, all exact primary/secondary configuration fields, refusal to substitute
the secondary configuration for the primary, all 40 omitted trace entries, evidence
integrity, malformed structures, forbidden profile claims and an unchanged target
witness. Regressions verify that no physical-power premise is required, all eleven
hypothetical correctness premises can satisfy the conjunction alone, and obsolete
physical cells, criterion references and fabricated hardware-qualification claims
are refused as unknown inputs. An exhaustive **2,048-row** Boolean conjunction table has exactly one
satisfying hypothetical row. These explicit test premises are separate from actual
OS/storage evidence and never enter actual inspection as qualified input. The model
does not run a filesystem worker or claim fault coverage from that truth table.

Reproduce the evidence bindings and model checks:

```console
python experiments/0051-profile-admission/build_ledger.py
python experiments/0051-profile-admission/qualify.py --public docs/write-safety/profile-admission-model.json
python scripts/check_docs.py
git diff --check
```

Rebuilding the ledger updates evidence hashes and findings; it never changes
nonqualifying status into authority. The qualifier checks the checked-in ledger
against its generator, verifies every bound public evidence digest, checks all
normative criterion IDs and binds its own sources. Private fixture paths, raw
captures, credentials, machine names and media are not included. Independent review
is required before handoff; the review and publication are recorded on the card.

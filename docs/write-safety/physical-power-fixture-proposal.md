# Disposable physical-power fixture proposal

**#0101 proposal only, 2026-10-15.** This finishes the bounded planning increment
under #0022 for [#0078's prerequisites](profile-admission.md), before #0050 can identify an
owner-approved physical fixture. The [review checklist](physical-power-fixture-proposal.json)
is a proposal, not an actual hardware inventory, permission record or qualification
result. No device has been selected, powered off, reformatted or purchased.

The [existing guest receipt evidence](namespace-receipt-guest.md) uses emulator
termination and NMI bugchecks with host caches alive. It supplies barrier/audit
experience, not this missing physical-power result. The exact current
[#0051 candidate](profile-admission-ledger.json) is virtualized; a bare-metal result
would be a new configuration and cannot silently qualify that candidate.
No RAW apply adapter, storage profile, namespace acknowledgement, automatic
recovery or production write permission follows from this proposal.

## Proposed minimal fixture and alternatives

**Preferred initial topology A:** one owner-designated spare physical x86_64
desktop, one internal SATA SSD that Terry explicitly declares disposable, and a
lawfully licensed Windows installation with NTFS. The dedicated disk contains
both this test OS and a bounded marker directory; all bytes on that disk must
be expendable, including the OS. OS/background I/O shares the physical disk and
must be reported. All other valuable drives are absent from the DUT, including
network/cloud storage mappings. There is no guest, shared host folder or original
media. This minimizes the required spare hardware; it does not optimize isolation
or establish a generally supported SATA profile.

An independently powered observer captures the barrier stream and retained caller
contexts. An owner-designated packaged switched outlet or switched PDU powers
**only the DUT and its internal storage**. The observer, its storage, network
switch and unrelated computers remain powered. No battery, UPS or other supply
may keep the DUT/storage alive after that outlet is disconnected. Owner-supplied
device manuals and a non-invasive power-state witness must establish the actual
cut domain and eventual loss of storage power; a successful outlet API response,
missing heartbeat or dark display alone is insufficient.

| Alternative | Concrete topology | Separate interpretation / cost |
| --- | --- | --- |
| A: minimal bare metal | One spare desktop and one disposable internal SATA SSD; full DUT mains cut. | Preferred first proposal. OS and marker I/O share one disk. New bare-metal configuration. |
| B: separate scratch disk | Spare desktop with disposable boot disk plus separate disposable internal SATA target SSD; both lose power together. | Better separation of target space/I/O observations; needs two expendable drives. Different controller/port/disk inventory. |
| C: power-cut virtualization host | A separate disposable physical Windows/Linux host and disposable backing disk run the exact declared Windows guest; entire host/backing-storage power domain is cut. | Closer to existing virtual topology, but host/kernel/QEMU/cache/disk identity must be fixed. Existing laptop/WSL guest is excluded; extra setup and host recovery scope. |

These are topology choices, not product recommendations or purchasing requests.
USB/removable storage, a storage-only cable/rail cut while the OS remains alive,
a laptop with an internal battery, and a controller with independent battery
power are outside the initial topology. Any later selection requires a separate
declared profile; results cannot be combined across these rows.

The allowed physical actuator is the selected packaged device's ordinary
documented power switch, operated externally. No custom mains wiring, exposed
relay or energized internal probing is part of this proposal. No power-control
software or credentials are added to imageinfo. A physical operator may perform
the cut if remote switching is unavailable; the same external timing and power
witness obligations remain.

## Owner input, then ordinary engineering work

Terry alone must identify or decline the expendable equipment and authorize its
intentional abrupt power interruptions. The concrete input request is:

1. Name the spare physical machine and disk(s) that may be dedicated to this
   experiment, with explicit confirmation that their existing contents/OS may
   be lost. Select A, B or C, or say that no spare fixture is available.
2. Identify an existing packaged power-control device and independent observer,
   or choose operator-controlled switching. Confirm which equipment may lose
   power and that Terry's normal host, valuable disks and unrelated devices are
   outside that domain. No equipment purchase is requested.
3. Confirm a lawful Windows test-installation route and willingness to approve
   the final device-specific preparation and finite run plan after inventory.
   Existing guest activation, evaluation dates and no-rearm restrictions remain
   unchanged; this proposal transfers no license or activation authority.

After those choices, Codex can collect the exact technical inventory read-only,
read the selected vendors' manuals, determine an appropriate power-state witness,
and draft the final device-specific preparation script for review. Terry need not
invent firmware/controller facts that the machine can report. The final explicit
execution approval must name the actual machine/disks, permitted preparation,
power switch/outlet, count/stop limit and restoration/retention policy. Approval
of this paper proposal alone is not approval to erase/install/cut power.

The hardware manifest must bind motherboard/system model, firmware/UEFI and power
restore settings; disk model/serial/capacity/firmware and controller/driver/port;
Windows edition/full build/servicing, NTFS volume and allocation-unit settings;
disk/device/cache policy including any power-loss protection claims; physical
power diagram, switch model/rating/method and independent observer; worker,
inspector, controller and source/dependency hashes. Unknown cache/firmware facts
stay unknown and limit the conclusion. Private serials, machine identity,
credentials and full captures remain local; publish sanitized identities/hashes.

## Preparation and stop rules for a later authorized execution

The future preparation must verify an allowlist of the approved physical disk
identities and exact marker root, confirm absence of valuable/mapped targets,
and refuse mismatch before any destructive setup. Any OS installation or disk
reset is a separately named permitted preparation action. Attach no private RAW
media. Use authored 65,536-byte source markers and fresh transaction names only.

Use the existing ordinary-owner `ordinary-receipt` research sequence, initially
the audited worker SHA-256
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`
from source `b819f54533c495b332c3d4dbb0caccef49923036`. Rebuilding or changing a
worker/controller requires fresh exact bindings and native control verification.
The worker runs as a standard test user. Provisioning/power control is separate;
no production privilege/helper or new root SDK API is introduced.

First propose one idle power-circuit preflight with no transaction active to
verify that the observer survives and the DUT/storage loses power. That is one
separately counted, device-specific approved cut. Then complete non-fault normal
publication and read-only inspection before the transaction fault schedule. Do not
change boot-failure policy or disable repair automatically. If Windows fails to
boot, asks to repair, identity changes, power cannot be confirmed off, or the
observer loses continuity, stop and retain the fixture. Further repair/reimage or
additional cuts require a new explicit decision; no automatic retry loop.

## Proposed finite worker schedule

After preparation and power preflight, propose **35 independent transactions**:
one normal control before, three full-DUT physical cuts at each of the eleven
barriers below, then one normal control after. That is **33 proposed transaction
power cuts**, with no physical runs completed now. Three repetitions provide
finite repeat observations, not statistical assurance or proof against every
possible interruption timing. Repetition order, seed/IDs, maximum runs and all
deviations must be frozen before execution; never discard an unfavorable trial.
Including the one idle preflight, the proposed entire campaign has a maximum of
**34 physical cuts**. A failed/incomplete trial is retained and stops the campaign;
it does not grant an additional replacement cut. Any expanded schedule needs a
new explicit approval.

| Barrier | Exact observation before holding the worker and cutting |
| --- | --- |
| `before-namespace-call` | Prepared candidate and intent; publication has not been released. |
| `published` | Held no-replacement rename returned successfully. |
| `installed-file-flushed` | Installed-file flush returned. |
| `parent-flushed` | Parent flush returned after installed-file flush. |
| `observation-file-flushed` | Observation-file flush returned. |
| `observation-parent-flushed` | Observation-parent flush returned. |
| `observed-record-flushed` | Ordinary observation checkpoint reached. |
| `receipt-written` | Separate receipt/context emitted; explicit receipt flush not called. |
| `receipt-file-flushed` | Held receipt-file flush returned. |
| `receipt-parent-flushed` | Receipt-parent flush returned after receipt-file flush. |
| `final-checked` | Fresh guarded artifact/property/namespace checks passed; final continuation withheld. |

The observer must receive the complete selected barrier and required caller
context before issuing a cut, while the worker remains held. Capture the last
fully received event and next unreleased action. Record separately: observer
receipt time, cut command/operator time, switch response, actual power-state
witness, off-hold interval and restart time. The controller command is not the
power-loss event. An initial **30-second off hold** is a proposed schedule choice,
not a claim about PSU hold-up time; the final device manual/witness may require
changing it. Freeze the interval and measurement resolution in the fixture plan.
Missing/partial barrier or context means no scheduled cut at that cell; report
incomplete evidence. Lost power confirmation means an unqualified trial, retained
as such, rather than relabeling it as successful physical-power qualification.

Process kill, warm reset, NMI/bugcheck, emulator termination, graceful shutdown
and actual physical loss stay distinct. Internal device power-loss protection,
if present, is part of the exact profile, not an excuse to call a surviving
OS/host-cache experiment physical loss. Neither the stage label nor returned
flush calls establishes namespace/receipt durability.

## Reboot and artifact audit

Restore power only to the approved DUT; verify a fresh boot and exact inventory.
Capture boot/servicing and any automatic filesystem/OS recovery observations
before claiming transaction inspection preserved anything. Ordinary Windows
boot/mount may already recover NTFS; **read-only inspector** describes our
application actions, not an assertion that no OS writes happened after reboot.
If the retained OS cannot boot normally, preserve the disk for a separately
approved recovery inspection; do not let an automatic repair loop run unnoticed.

Before and after the existing guarded read-only inspector, collect directory
names, file identity/size/hash/default stream, relevant timestamps/attributes,
owner/DACL/link observations and all fixed record/receipt bytes. Retain malformed,
missing, extra, foreign and partially written artifacts with explicit errors;
do not sweep names or silently omit unreadable entries. Compare source marker
bytes against the external pre-fault source witness. Root/source/foreign names
remain retained. No restart finalize/prune, replay, rollback or cleanup is run.

The observer retains the actual caller history/context outside the cut domain,
including exactly which release-fence and receipt bindings it received. An
editable transaction JSON or matching receipt alone cannot invent that history,
freshness, publication permission or a durable success acknowledgement. Lost
external history yields context-unavailable refusal, with disk artifacts retained.
No new secret/key infrastructure is inferred from integrity/custody requirements.

The later auditor must reconcile every scheduled ID, actual cut/boot witness,
worker/inspector binding, history prefix, inventory and error. Report output and
receipt survival separately from original metadata/property equality and inspector
acceptance. In particular, retain and explain timestamp drift such as the
existing `receipt-written` guest observations. Record rejected/incomplete trials
and every operator continuation; no replay can manufacture a missing cell.

## Finish line and evidence basis

This planning increment is reviewable when topology alternatives, owner inputs,
isolation, barriers, counters and audit/stop rules are consistent. The actual
fixture and all 33 physical interruption cells remain **unrun**. #0050 still
needs the concrete owner input above; #0078 still needs independently admitted
format and storage capabilities. A later finite run can supply bounded physical
observations, not automatically discharge every WS/SAF or RAW admission gate.

Primary Microsoft references rechecked **2026-10-15**:
[File Caching](https://learn.microsoft.com/en-us/windows/win32/fileio/file-caching)
(visible update 2021-01-07) describes cached data/metadata and write-through;
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
(visible update 2021-10-13) describes the per-file call and its return/error
boundary. Those API descriptions do not qualify the unselected physical stack.
The existing [namespace/receipt proposal](namespace-receipt-protocol.md),
[marker receipt implementation](namespace-receipt-marker.md) and
[exact admission ledger](profile-admission.md) retain their separate gates.

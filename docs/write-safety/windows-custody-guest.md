# Windows caller-history guest qualification

Bounded **#0044** research under organizational parent **#0022**, observed
**2026-10-14**. This work qualifies selected interruption/restart observations for
the [#0043 caller-history snapshot sequence](windows-custody.md). It uses the
existing [disposable Windows evaluation guest](windows-guest.md) and authored
64 KiB marker bytes. It does not exercise camera media or enable production recovery.

## Exact implementation and fixture

The guest worker is rebuilt from the exact **`b381576` #0043 source revision**,
with static CRT linkage for the installed guest. It is a distinct executable from
the historical native worker: source and exact executable hashes are retained
separately, together with the loaded controller and driver sources. The **exact
guest executable** passes a fresh run of the original **41-case native custody
qualifier**, with **117 worker captures**, **1,398 readable hashed paths** and one
deliberately inaccessible DACL path retained without repair. It matches that
fresh static native baseline, while differing from the historical dynamically
linked #0043 executable. Historical binaries, VM records and captures remain
unchanged; #0046's later marker receipt code is outside this qualification.

The frozen archive's **354 tracked blobs** were checked against Git revision
`b3815765d5230bec979e8a38b1cf9c6f384d1682`. The **19 historical native source
bindings** match byte for byte. The audit separately checks the frozen Rust and
manifest inputs, exact worker hash, loaded controller/driver copies and the served
guest-agent bytes across every fault. These bindings identify the experiment;
they do not authenticate caller authority or qualify snapshot freshness.

The existing fixture runs Windows 11 EnterpriseEval build **26300** as its standard
local medium-integrity test user, without an administrator token. The original
publication process remains blocked while a second worker saves caller history in
a separate fresh private directory. The supervisor supplies actual contexts
captured outside the editable transaction, retains the actual custody-root binding
and controls the held original process. It never derives authority from a matching
transaction record or from a missing output name.

No host disk or shared folder is attached. Guest-only crash settings, the evaluation
installation and existing loopback/QMP controller are unchanged. No key service,
new OS policy, privileged production helper, SDK API or dependency is introduced.

## Four interruption cells

Each case starts with a fresh marker transaction and custody directory. Every
required custody save must finish its file and parent flush calls and final
checks, returning `custody-snapshot-recorded`, before the controller advances.
The barriers and returned snapshot state are observations, not durability claims.

| Cell | History retained before fault | Fault | Required restart interpretation |
| --- | --- | --- | --- |
| Captured only | First captured snapshot saved while the original is blocked at `before-namespace-call` | Guest NMI bugcheck, then controlled emulator quit/relaunch | Captured-only history grants no restart context. Missing release history does not prove nonrelease. |
| Confirmed stopped | Actual original-process kill and exit wait without publication release, then the stop-confirmed snapshot saved | Emulator SIGKILL/relaunch | The surviving exact history may supply the caller's before-publication candidate; an explicit prune still requires fresh guarded bindings. |
| Release fenced | Release-fence snapshot fully saved, with the original still blocked before its first publication continuation | Guest NMI bugcheck, then controlled emulator quit/relaunch | A surviving fenced history grants no restart context. A fence records possible release, not proof of an attempted namespace call. |
| Observation renewed | Fence save precedes the sole publication continuation; observed and renewed matching output contexts are saved | Emulator SIGKILL/relaunch | Only the surviving exact renewed history may supply the caller's matching observation context. Existing-observation validation remains read-only. |

The supervisor records successful process exit before submitting stop attestation.
It records complete fence-save success before sending the original process its
publication continuation. These actual controls establish the bounded test
history; parsing history JSON cannot establish them independently.

After every fault the controller requires a new guest boot notification and
collects actual bugcheck evidence for NMI cases. Transaction inventories bracket
the first read-only custody inspection. A repeated custody inspection after the
separately logged caller actions checks that the custody inventory remains
unchanged. There is no claim of a complete pre-fault transaction inventory while
the live worker retains incompatible handles. Any subsequent prune or observation
request is separately explicit and audited; inspection alone never authorizes it.

## Audited observations

The [guest audit](windows-custody-guest.json) passes **four scenario sets and four
faults**: **two fresh NMI bugchecks**, **two emulator terminations** and **four
distinct post-fault boots**. It reconciles **nine native custody-save captures**,
**43 private evidence files**, **four unchanged transaction inventory pairs**
across custody inspection and **four unchanged custody inventory pairs** across
the explicit caller actions and repeated inspection. The host remained on the
same independently recorded boot. All worker tokens were standard-user tokens.

- Captured-only history survives its NMI/restart as `captured-unconfirmed`, with
  no context candidate. Repeated requests using the unattested original context
  refuse before effects and preserve the exact unpublished transaction.
- The stopped branch records actual original-process exit before saving stop
  attestation. After emulator termination/restart, its exact surviving history
  supplies the explicit caller's before-publication candidate. Fresh guarded
  prune removes three owned handles and keeps the unchanged source and root.
- The fully saved fence survives its NMI/restart as
  `publication-release-uncertain`, with no context candidate. The original had
  not received publication continuation in this cell. Unattested prune still
  refuses: the fence does not prove attempt or establish nonrelease authority.
- Renewed history survives emulator termination/restart with the exact
  three-record context. The older two-record observation context refuses; the
  renewed context validates the existing observation without effects.
  Postpublication prune refuses. Source, output and all three transaction records
  remain unchanged across these requests.

Successful snapshot persistence in these four selected cells is a bounded
observation, not proof of automatic durable custody or every interruption point.
Raw captures, private inventories and the audit's hash manifest remain private.
The guest was shut down normally after the audit; no emulator process remains
for its retained disk, and its loopback controller is stopped. The private guest
disk and captures are retained for review and later authorized qualification.

Run instructions and private-evidence handling are in the
[qualification tooling README](../../experiments/0044-custody-guest/README.md).

## Limits and remaining gates

An NMI deliberately crashes only the disposable Windows guest. Its controlled
QEMU quit/relaunch can drain submitted I/O. Emulator SIGKILL/relaunch is a distinct
fault method. Neither stops WSL or the laptop, and host caches remain alive.
The independently recorded host boot must remain unchanged. The guest OS, crash
dump and marker operations share the same NTFS/QCOW2 test volume. These finite
observations do not qualify physical power loss, every storage provider or an
unmeasured crash window.

Whole-history prefix validation and a bound custody-root identity do not
authenticate the historical identity of each snapshot, caller authority or
freshness. The native same-byte replacement acceptance remains a limitation.
Missing or captured-only snapshots cannot establish nonrelease; fenced history
cannot establish that publication occurred. No automatic antirollback protection,
durable current-history service or unattended replay/prune is added.

All commitment, namespace acknowledgement, repair and production-publication
flags remain false. Full namespace/receipt qualification, native storage-error
and cumulative resource cells, complete profile admission and independent RAW
admission remain separate work. #0027's real-camera refusal and #0023/#0024 gates
are unchanged.

# Disposable Windows qualification guest

Operational research tooling for **#0022**, **2026-10-14**. Terry requested creation
of a Windows guest after confirming no existing disposable Windows VM was known.
Its purpose is Windows interruption/restart qualification, not running imageinfo
in production or replacing the laptop's installed OS.

## Image and licensing

The official [Windows 11 Enterprise evaluation](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise)
offers a 90-day evaluation with no product key required. The actual image's embedded
EnterpriseEval terms were read: evaluation/test/demonstration use only, no resale,
production use or continued use after the evaluation period. A permanent guest
would require appropriate ongoing licensing; the host Pro license is not reused
as permission for an extra instance. No activation bypass/rearm is part of the tooling.

Observed official download **2026-10-14**:

- Microsoft Evaluation Center English x64 link resolves to
  `26300.9457.260913-1737.26h2_ge_release_svc_refresh_CLIENTENTERPRISEEVAL_OEMRET_x64FRE_en-us.iso`.
- Source host: `software-static.download.prss.microsoft.com`, HTTPS, 8,225,329,152 bytes.
- Downloaded SHA-256: `bc3f24086ebadc94489066b5ad78089e2cf5c3491e90e790bb81a2b199c10e38`.
- This is a recorded local download hash, not a claim that a separately published
  vendor hash was matched. Installer/boot media remains private and is not redistributed.

The installed guest reports **Windows 11 EnterpriseEval, 10.0.26300**. Its initial
license query reports activated (`LicenseStatus=1`) and **129,600 evaluation minutes**.
The installer is the offered 26H2 evaluation; the desktop's inherited base-build
watermark is not substituted for the actual installed build. The launcher refuses
use after 90 days from creation and provides no rearm mechanism.

## Isolation and setup

The [helper](../../experiments/0022-ordinary-output/windows_guest.py) uses existing
WSL QEMU **10.2.1**, q35/KVM, four virtual CPUs, 8 GiB RAM, a new sparse 96 GiB QCOW2
disk, UEFI with enrolled Microsoft keys, and a software TPM 2.0. No physical host
disk, shared folder, host credentials or real media is attached. The two installer/
configuration ISOs are read-only. Guest traffic uses user-mode NAT; the controller
binds only WSL loopback. Generated local guest credentials remain in private setup
state, never this repository. A statically linked private worker avoids installing
an additional VC runtime in the guest.

The guest CPU is `host,vmx=off,hv-relaxed=on,hv-vapic=on,hv-time=on,hv-spinlocks=8191`.
An initial plain `host` attempt stalled during setup in this already nested Hyper-V/
WSL environment; masking another VMX layer and using QEMU's supported Windows
[Hyper-V enlightenments](https://www.qemu.org/docs/master/system/i386/hyperv.html)
allowed installation. SATA/NTFS lives on the virtual disk with QEMU `cache=writeback`;
WSL/host disk caches remain alive. Installed restarts detach both setup media so
the initial wipe-capable unattended installer cannot run again.

The KVM device already exists but the ordinary WSL user lacks direct access. The
launcher opens it using the existing WSL root invocation, then QEMU's standard
`-run-with user=uid:gid` drops all uid/gid entries to that ordinary user before guest
execution. This was verified with a paused KVM preflight and `/proc` uid values.
Only the newly created private QMP socket/PID file is assigned to its operator;
no host feature, KVM ACL, group membership or Windows reboot is changed.

UEFI/TPM/ISO utilities were downloaded from configured Ubuntu repositories and
extracted privately; they were not installed as host services. Guest setup creates
a standard local test user and a guest-only logon agent. NMI crash/dump settings
apply only to this disposable guest. Exact tooling versions/hashes/licenses and
raw setup/guest logs remain in private provisioning evidence.

Repeated intentional crashes initially entered Windows Automatic Repair. A separate
guest-only WinPE maintenance configuration preserved the original BCD and changed
only this fixture's [boot failure policy](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/bcdedit--set)
to `IgnoreAllFailures` and `recoveryenabled No`; its verified log is retained. This
maintenance medium contains no installation or disk-wipe action. The measured
profile includes this nondefault policy, `NMICrashDump=1`, `AutoReboot=0` and small
crash dumps. No host boot policy is changed.

The agent's startup handshake reads the build directly from the registry and derives
boot time from short-lived system uptime; it does not wait on an optional WMI or
event-log query. The controller accepts only a post-fault notification with a distinct
boot time, and verifies a standard medium-integrity worker token. A local named mutex
prevents duplicate agents. Diagnostic notifications from older attempts cannot
qualify a later restart. Actual Windows bugcheck events are collected separately.
If logon startup is delayed, the driver starts that same agent through the private
guest console after a boot interval; the mutex protects an already running agent.

A later preliminary matrix stalled on its third NMI warm reset despite the verified
boot policy. That attempt and its two completed cases are retained separately.
The final driver captures the NMI bugcheck and then performs a **controlled QEMU
quit/relaunch**; emulator-termination cases instead use **SIGKILL/relaunch**. These
restart methods are explicit parts of the observations. Controlled emulator exit
can drain submitted virtual-disk work; neither method stops the host or its caches.
Do not relabel either as physical power loss or a qualified Windows warm-reset path.

## Qualification status

The [audited ledger](windows-guest-observations.json) contains **one normal run,
eight Windows NMI bugchecks and eight separate emulator terminations**, at the
eight source/candidate/record/property/publication checkpoints. Eight fresh distinct
`0x80` events and bugcheck images accompany post-fault boot notifications and
read-only inspection. The audit binds **85 private capture files**, **54 readable
post-fault artifact paths**, the exact static c63e18b worker and local controller
source hashes. The laptop's boot instant was unchanged throughout the matrix.

An [NMI](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/nmi-hardware-failure-error)
is a non-maskable interrupt. Here QEMU deliberately injects it into the virtual
CPU, causing Windows's diagnostic `NMI_HARDWARE_FAILURE (0x80)` bugcheck. It is an
intentional guest fault, not evidence of faulty laptop hardware.

| Reached checkpoint | NMI + controlled emulator restart | SIGKILL + emulator restart |
| --- | --- | --- |
| Source guarded / candidate flushed | Unattributed artifacts; output absent. | Unattributed artifacts; output absent. |
| Prepared / intent record flushed; before property / namespace call | Matching candidate retained; output absent. | Matching candidate retained; output absent. |
| Published: namespace API returned successfully | Candidate retained; output name absent. | Matching output retained, recovery-required. |
| Later observed record flushed | Matching output retained, recovery-required. | Matching output retained, recovery-required. |

The successful namespace call **did not survive the measured NMI interruption as
an output name**. A matching output in other cells does not qualify namespace or
receipt persistence. All reports keep `namespaceAcknowledged`, `committed`,
`repairAllowed` and production publication permission false. Event-log record
numbers were reused after unclean shutdown; the audit compares fresh event
timestamp/message pairs and never treats log numbering as a durable receipt.

Five additional guest actor cases and three no-effect admission/finalization/prune
refusals are bound by nine private captures. Held source/candidate data writes
refuse; a foreign output winner remains intact and its different policy refuses
inspection; owner data editing after exit succeeds and becomes an output conflict.
The .NET Framework timestamp setter also refuses while held. Its
[reference implementation](https://raw.githubusercontent.com/microsoft/referencesource/main/mscorlib/system/io/file.cs)
requests write access, unlike the native minimal-property actor. This specific API
refusal does **not** establish continuous timestamp/property exclusion under option A.
The wider [native 64-case observations](ordinary-output.md) still show allowed
property changes and boundary detection.

No complete storage profile, safe restart repair, Windows warm-reset reliability,
native disk-full/device-error cell, physical power-loss guarantee or RAW writer
is enabled. Namespace/receipt ordering and safely authorized finalization/prune
remain next work under #0022. Private media, credentials, disks, screenshots and
raw logs remain local; public CI checks tooling syntax and the native/portable
protocol separately from these guest observations.

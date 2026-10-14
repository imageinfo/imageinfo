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

The installer is the offered 26H2 evaluation. Record the actual installed build,
edition, activation/evaluation state and test configuration before claiming a run;
the ISO filename or a different host kernel does not qualify a profile.

## Isolation and setup

The [helper](../../experiments/0022-ordinary-output/windows_guest.py) uses existing
WSL QEMU **10.2.1**, q35/KVM, four virtual CPUs, 8 GiB RAM, a new sparse 96 GiB QCOW2
disk, UEFI with enrolled Microsoft keys, and a software TPM 2.0. No physical host
disk, shared folder, host credentials or real media is attached. The two installer/
configuration ISOs are read-only. Guest traffic uses user-mode NAT; the controller
binds only WSL loopback. Generated local guest credentials remain in private setup
state, never this repository. A statically linked private worker avoids installing
an additional VC runtime in the guest.

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

## Qualification status

Guest installation and interruption qualification are in progress. No Windows OS
crash, namespace persistence or receipt guarantee is claimed by this setup note.
Native [option A observations](ordinary-output.md) are independent and complete
within their stated live scope. New guest results must distinguish a Windows
kernel bugcheck from process kill, reset, emulator termination and physical power
loss; the host and its caches remain alive during virtual-machine tests.

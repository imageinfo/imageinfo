# Best-effort power-test policy

**Accepted by Terry, 2026-10-15; revision `power-test-policy-v1`.** imageinfo is
FOSS developed on a best-effort basis. Dedicated physical power-drop testing is
outside the project scope. No dedicated hardware, power controller, electrical
power-domain setup or hardware power-loss qualification is required or requested.

The ceiling for future power-related testing is **turning disposable VMs off**
and inspecting their state after restart. Existing VM/emulator-off observations
can supply that bounded evidence. Do not plan new host crashes, guest NMI/bugcheck
campaigns, physical DUT cuts or storage-only power cuts as additional requirements.
Ordinary unit tests, process cancellation and software error injection remain
available; this decision concerns the power-test scope.

Physical power-loss testing is neither a release/admission prerequisite nor an
open blocker. It must not be reintroduced through an exact-hardware qualification
field, renamed power gate, fixture request or dependency. #0050 and #0101 are
retired; no equipment or Windows installation/license decision is needed for them.

VM-off tests can leave host/device caches alive. Describe that limitation plainly;
do not present them as physical power-loss tests or promise survival of arbitrary
hardware faults, media failure or power loss. Use the available OS/filesystem
operations and bounded VM observations for best-effort interruption behavior.

Historical NMI/crash records and the withdrawn physical-fixture proposal remain
as dated research. They supply no authority for additional campaigns and no
current physical-testing obligation. This decision supersedes contrary physical-
power and dedicated-hardware requirements in older plans and handoffs.

The decision does not itself enable a writer. Source/unknown-data preservation,
byte/name guards, applicable property checks, truthful error/recovery outcomes and
independent format admission remain separate correctness work. Missing physical
power evidence alone can never refuse an otherwise supported operation.

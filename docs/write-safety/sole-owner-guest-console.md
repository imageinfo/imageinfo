# Sole-owner guest console transport checkpoint

Board #0072 is unfinished. The CLI refuses run, prepare-console and
observe-console before reading configuration or opening a socket. Direct
module functions support authored tests only. The
[retained guest attempt](post-operation-guest-contrast.md#current-0223-stop-point--2026-10-19)
is unchanged. No actual diagnostic cell ran.

The checkpoint has one serialized runner-owned connection and a result
observer with no QMP/input capability. The runner distinguishes planned,
dispatched and acknowledged input. It requires the current live parent
handoffs and keeps launch and collector confirmation separate. No saved
screen, readiness file, or prior review can authorize replay.

Read-only inventory uses the reviewed loader and canonical absolute paths:
`python -I -S /absolute/owner_entry.py /absolute/host_runner.py RUNNER_SHA256 owner-inventory`.
The same prefix with `inspect --bindings FILE --approved-bindings-sha256 DIGEST`
validates reviewed facts without guest execution. The source, loaded-code and
interpreter identities are separate from the existing controller attestation;
digests do not grant authority.

The Windows authored controls exercise one real socket and the unchanged host
auditor, using a single TCP listener as a test substitute when AF_UNIX is
unavailable. Linux AF_UNIX/peer and /proc checks, final live dispatch bindings,
cancellation under lock contention, and the retained successful two-cell
authored workflow with the full guest/artifact audit and fresh independent
review remain open. Do not enable the operational CLI modes until those gates
pass. The actual guest diagnostic is separately tracked on #0109 and requires
fresh exact execution review after #0072 acceptance.

Run the authored suite with
`python -W error::ResourceWarning -m unittest discover -s experiments/0219-namespace-guest-contrast -p "test_*.py"`.

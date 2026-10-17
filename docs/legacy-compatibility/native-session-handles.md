# Native session standard-handle observations (#0140)

The test-only [runner](../../scripts/check_native_session_handles.py) starts the
actual `imageinfo session read` executable with deliberately selected native
standard handles. It submits no read request and uses only authored guard/empty
files. These observations are separate from normal pipe EOF in
[#0116](read-session-process.md) and the caller-owned failing I/O traits in
[#0112](read-session-library.md).

The initial Windows run retained eight cases against executable SHA-256
`9497e9ce14c6c9623003cdf58abc4d94cddba46394c44c9609758499f94ffab4`.
Seven ended naturally with exact canonical LF frames, exact stderr and exact
process status. One was censored by the harness watchdog:

| Caller-supplied handles | Actual observed result |
| --- | --- |
| Empty regular-file stdin | Ready, EOF completion; status 0; empty stderr |
| Pipe stdin with its writer already closed | Ready, EOF completion; status 0; empty stderr |
| `INVALID_HANDLE_VALUE` stdin | Ready, EOF completion; status 0; empty stderr |
| Previously closed native stdin handle value | Ready, EOF completion; status 0; empty stderr |
| Valid write-only regular-file stdin | Ready, `INPUT_IO`, input-error completion; status 1; empty stderr |
| Valid read-only regular-file stdout | No captured stdout; status 1; `OUTPUT_INCOMPLETE` with `PermissionDenied` |
| Pipe stdout with its reader already closed | No captured stdout; status 1; `OUTPUT_INCOMPLETE` with `BrokenPipe` |
| NULL stdin | Ready only through the ten-second watchdog; harness termination; no natural status, EOF/error/completion assertion |

Every natural completion has zero frame attempts, zero results and null
`closeId`. Input failure has exactly the `protocol-error` frame with null `id`
and code `INPUT_IO`; the protocol exposes no native input error kind. Output
failure diagnostics are exactly
`OUTPUT_INCOMPLETE: Could not finish output (PermissionDenied).` or the same
message with `BrokenPipe`, followed by LF. Delivery of a diagnostic is a
best-effort observation, not an authoritative completion channel.

The runner compares complete output bytes to an independent fixed ready-frame
oracle, including every advertised v1 limit. It records raw stdout/stderr,
parsed frames, status, binary/tool hashes and before/after inventories for each
case. The authored inventory's names, lengths, SHA-256, modification times and
mode remained unchanged. Ordinary access-time accounting is excluded. Captures
and reports are harness-owned artifacts outside the protected fixture directory.
The initial result is retained privately under
`.local/work-wave-20261017c/140-qualified-initial/report.json`; it is not evidence
for a subsequently changed executable.

## Injection and portability limits

The [test-only launcher](../../scripts/native_session_handles.py) calls Windows
`CreateProcessW` with `STARTF_USESTDHANDLES`, bypassing Python's ordinary subprocess
repair/validation of invalid handles. This adds no production OS boundary,
dependency, privilege or installed helper. Closed means the parent opened and
closed that native handle value immediately before launch. It does not prove
that Windows or the child runtime retained the same invalid handle state. In
particular, invalid/closed setup yielding EOF is not evidence that `INPUT_IO`
was exercised. The write-only case supplies that positive native input-failure
observation. `INVALID_HANDLE_VALUE` is also a pseudo-handle for certain Windows
handle-management APIs, so `GetHandleInformation` is not used to certify it.

NULL startup did not complete within the watchdog both in restricted execution
and in an authorized ordinary host retry. Its cause is not established. The
watchdog kills only the owned child; forced status 124 belongs to the harness,
not the session. This finite observation establishes no product deadline,
cancellation policy, eventual completion or native error outcome.

The POSIX branch uses direct child fd manipulation with no shell. Its seven
declared cases are regular-file/pipe EOF, closed stdin, write-only stdin,
directory stdin, read-only stdout and broken-pipe stdout. Platform results must
be retained from an actual native execution; a portable script alone qualifies
neither Linux nor macOS. Runtime normalization of missing descriptors must be
distinguished from a read failure. No general handle-type coverage is claimed.

Native flush-only failure injection is **unavailable** in these cases. Failed
stdout targets fail a write; they do not demonstrate a successful native write
followed only by a failed flush. The actual library faulting-writer tests retain
that distinct path. Successful flushes never prove later consumer delivery.

## Reproduction

Use a fresh retained output directory and an already built executable:

```text
python scripts/check_native_session_handles.py --binary target/release/imageinfo.exe --output .local/native-session-handles-run
```

On Linux/macOS omit `.exe`. The runner refuses an existing output directory and
returns nonzero for any unexpected status/frame/diagnostic, changed inventory,
changed executable or launcher failure. The fixed Windows NULL case is reported
as `censored-watchdog`, separately from `natural-exact`; matching that observation
does not turn it into a natural session outcome. The ten-second per-child
watchdog and post-run 8 KiB capture validation are harness checks, not production
timeouts or physical disk quotas.

This work enables no media mutation, publication, recovery, cancellation,
flush-only native qualification, broad compatibility or storage-profile admission.

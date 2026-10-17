# Bounded sequential read-session observations (#0146)

The [collector](../../scripts/measure_session_resources.py) measures actual
`imageinfo session read` OS pipes with authored structural fixtures. The
[independent auditor](../../scripts/audit_session_resources.py) reloads retained
frames and checks exact standalone read oracles, IDs/order, statuses, UTF-8 input
byte counts/hashes, LF boundaries, final completion and source inventories.
The [functional controls](../../scripts/test_session_resources.py) exercise actual
failure-then-valid isolation, protocol caps, automatic close, retained timeout and
missing-final-frame requests, and corrupted-record rejection.

The fixed campaign has three fresh sessions at each of 1, 64 and 255 admitted
reads followed by explicit close: 960 total admitted read attempts in nine
sessions. The single-read cells select ISO/raw values. Longer sessions repeatedly
alternate selected ISO/raw and all metadata/all values, placing usage,
missing-file and invalid-file failures before later valid reads. Request failures
do not change the clean session exit status. All valid paths contain authored
Unicode text; exact byte counts use UTF-8 rather than character counts.

Seven additional controls use 128/129-byte IDs, duplicate IDs, exactly 524,288
input bytes including LF or CRLF, 524,288 non-LF bytes that force refusal, and
256 admitted reads with maximum-length unique IDs and automatic limit completion.
That last cell alternates selected/all reads and retains all 256 results plus
the complete final frame while stdin remains open. No queue or concurrent-request
capability is inferred from these sequential requests.

## Collection and audit

Prepare a fresh ignored `.local` directory against the final frozen executable,
then run only in a serialized measurement slot. Preparation exports the shared
public authored Rust fixture and captures ordinary standalone JSON results for
five request classes. The auditor compares the entire session result with those
oracles after verifying and normalizing invocation IDs. It normalizes only the
CLI executable spelling `imageinfo.exe` to the in-process spelling `imageinfo`
inside syntax-error diagnostic messages. It retains values, coverage, issues,
source paths and all other result fields. Independent hardcoded expected statuses
remain separate from the standalone executable oracle.

```console
python scripts/measure_session_resources.py --run-root .local/session146-final --prepare PATH_TO_FROZEN_IMAGEINFO
python scripts/measure_session_resources.py --run-root .local/session146-final
python scripts/audit_session_resources.py --run-root .local/session146-final
python scripts/test_session_resources.py
```

Set `IMAGEINFO_SESSION_BINARY` to select another built executable for functional
controls. These are authored tests, not camera measurements. The campaign binds
the executable and exact required collector/auditor/helper inventory, including
the independently imported telemetry auditor, and checks their hashes after
collection. Preparation also records the repository revision plus exact hashes
of every `src` file, Cargo manifest/lock and pinned toolchain; the campaign refuses
source changes and the auditor requires this complete inventory. This binds the
declared build source but does not independently reproduce or attest compilation.
A fixture inventory includes byte length/hash,
modification time and physical identity before/after the campaign. This does not
promise suppression of filesystem access-time accounting.

Ready latency begins immediately before `Popen` and ends when the reader receives
the complete ready LF. Each request starts before its writer is scheduled and
ends at the complete matching result LF, timestamped before parsing. Total time
continues through child exit, pipe draining and final direct-process sampling.
It therefore includes collector overhead; it is not pure processing time.
Per-request bytes/hash, send/end offsets, latency and memory-checkpoint indexes
are retained alongside complete bounded stdout/stderr and all telemetry samples.

The collector reuses [#0142 telemetry](read-telemetry.md) without copying its
Windows counter implementation. Ordinary 10 ms sampling is supplemented by a
ready checkpoint and a checkpoint after every result. The same monotonic origin
aligns observation brackets and frame timestamps. The independent #0142 auditor
checks counter arithmetic, null reasons, sample bounds, membership observations,
maxima and final samples. Ready-to-last-result working-set/private-commit deltas
describe sampled retained state during each lifetime; the post-exit memory sample
is not used as retained-state evidence. Each checkpoint requires a new nonfinal
sample bracketed by observed-live child checks, after its LF and before the next
request send. Automatic close can race the final result checkpoint; that endpoint
and its growth delta stay unavailable if live sampling cannot be established.
CPU counters are process lifetime thread
time; logical process I/O includes pipe traffic and does not measure device I/O.

## Limits and outcome boundary

Each session has a 30-second harness watchdog, 32 MiB retained cap per output
channel and the helper's 2,048-sample bound. Separate writer/reader threads keep
the main supervisor able to stop a blocked direct child. Failure, cancellation,
overflow, timeout and absent final frames retain partial output and requests;
unfinished request latencies remain null and the session is censored. A failed
cell is not removed from the fixed denominator. The collector is not journaled:
collector crashes, repeated interruption or record-write failures can still
prevent the final record. The auditor requires a complete campaign before
producing its campaign report and preserves censored cells as ineligible. Every
available complete frame in a censored cell still undergoes the same ready,
ID/order, status, exact-result and completion-prefix checks; a later timeout never
excuses an earlier malformed or incorrect result.

Measurements are single-host descriptive observations with uncontrolled warm
exposure. The small authored fixture exercises lifetime saturation without camera
content. Bounded sampled growth is not a leak proof, RSS quota, persistent cache
qualification, resource default or product timeout. Sampled child membership is
not containment. Existing [library](../legacy-compatibility/read-session-library.md)
and [process](../legacy-compatibility/read-session-process.md) correctness and
lifecycle limits remain unchanged. No cancellation policy, queue, concurrency,
performance recommendation, mutation or production storage admission follows.

Actual campaign results are pending the serialized final-executable slot; the
functional controls alone are not a latency or resource baseline.

# Offline startup observations — 2026-10-17

These bounded observations use the separately frozen [protocol](offline-startup.md).
The original protocol remains byte-identical for retained-audit reproduction.

One fixed campaign used source `4d47da31423d6ac9b50bc399665c85fd71809753`
and the exact source-bound release executable after the VM campaign had ended
and its guest was normally shut down. All 65 attempts are retained: fifteen
warmups and fifty measured attempts. Separate retained-artifact audit and fresh
independent arithmetic review found all outputs, statuses and resource records
valid, with no missing or censored attempts. No retry or trimming occurred.

The [machine summary](offline-startup/qualification.v1.json) binds the exact
protocol/executable/record/audit and retains all ranges and direct-process
counters. These medians use ten measured attempts per case:

| Offline invocation | First byte received, median ms | Complete output and observed exit, median ms |
|---|---:|---:|
| Root help | 15.112 | 25.420 |
| Metadata-read leaf help | 19.036 | 33.944 |
| Session-read leaf help | 16.270 | 28.347 |
| Version text | 12.694 | 18.050 |
| Version JSON | 12.075 | 12.203 |

Collector completion remains a separate endpoint. The small outputs, warm-exposed
uncontrolled caches, shared workstation background activity and instrumented
Windows process scope limit interpretation. No format/tag discovery, cold-start
bound, metadata-read benchmark, cross-host comparison, default, regression
threshold or release budget is established by these values.

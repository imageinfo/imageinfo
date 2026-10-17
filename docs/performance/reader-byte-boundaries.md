# Native reader byte-budget boundaries

#0148 qualifies two existing default limits with public authored containers and an
independent recording `Read + Seek` source. It changes no production reader policy.

`tests/reader_byte_boundaries.rs` executes six native consumption cells:

| Axis | Below | At | Above | Other byte constraint |
| --- | ---: | ---: | ---: | --- |
| Total metadata request bytes | 8,388,607 | 8,388,608 | 8,388,609 | Every request <= 1,048,576 |
| Largest individual request | 1,048,575 | 1,048,576 | 1,048,577 | Total requests < 8,388,608 |

The below/at cells return complete metadata with three stored-preview observations.
Each above cell returns exactly `LIMIT_EXCEEDED` / `Metadata byte budget exceeded`.
A separate control raises only its exercised limit by one byte and completes the
same above-boundary container. This distinguishes the actual budget branch from
invalid structure, insufficient TIFF entries, box counts or other limit failures.

The authored fixture grows four CMT payloads and four sample descriptors. CMT
trailing bytes contain zeros; CRAW descriptor extensions are valid `free` atoms;
the CTMD descriptor retains its fixed fields and uses unused trailing bytes. All
sample offsets, enclosing sizes and descriptor lengths are rebuilt. The original
camera/mode fields, track assignments, timed record and stored preview extents
remain valid. These are authored parser controls, not camera acceptance evidence.

The independent oracle enumerates the authored layout's expected ordered read
ranges without calling the native reader. The recording source retains offset,
requested length and returned length for each actual underlying `Read`. Tests
compare the entire sequence to the expected admitted prefix, sum those lengths,
and compare successful sums to native `Metadata.bytes_read`. The first denied
request never reaches the recording source. Failure exposes no complete result or
charged-byte field. Repeated overlapping reads are counted repeatedly: these are
logical requests, not unique source coverage or attempted I/O on failure. The
immutable in-memory source is SHA-256 checked before/after. No file publication,
preview extraction or source mutation occurs.

Six additional native configuration cells use immediately below/at/above
268,435,456 metadata bytes and 8,388,608 block bytes. A small fixture completes
below/at; above returns the exact supported-ceiling refusal before any source
read. These establish configuration acceptance only; they do not consume or
qualify either hard capacity.

The process probe is `examples/reader_byte_boundaries.rs`. After the final binary
freeze, use `scripts/reader_byte_boundary_campaign.py --binary <probe>
--prepare-freeze <manifest>` to save exact executable, tool, fixture, recorder and
production source hashes. Retain the manifest SHA-256 independently in the parent
freeze witness. Run the collector with `--binary <probe> --freeze <manifest>
--freeze-sha256 <witness-hash> --output <fresh-private-directory>`. It retains one attempt for each of
the six default cells, bounded stdout/stderr, actual native read nanoseconds,
end-to-end process time and unchanged shared direct-process telemetry. Audit with
`scripts/audit_reader_byte_boundaries.py <campaign> --freeze <manifest>
--freeze-sha256 <witness-hash>`, which checks the external witness, exact bindings,
per-attempt argv, fixed denominator,
complete retained captures, independent range arithmetic, exact refusal prefix,
result completeness and final counters. It validates every CPU, memory and logical
I/O sample as a nonnegative integer, checks sample alignment and the final
endpoint, errors/stop state, cumulative counters and independently recomputed
memory maxima. Physical I/O must remain explicitly unavailable. All rejected
attempts remain in scope. One authored valid retained report and 28 adversarial
report controls qualify the auditor separately from actual measurements.

The actual campaign ran on 2026-10-17 against source commit
`61e6e8b719c35d9fc48412f6702faea7f14ea618`. The exact release probe SHA-256 was
`d0dce969ec80b1e03b483dc3fc221c80013733f5bd8d661262efd4050260a90c`;
the independently recorded campaign-freeze manifest SHA-256 was
`b53d90f10da44a0ced792366f2d33581f7819be0674491bbbfc982fe107e1ca6`.
The parent full-source freeze SHA-256 was
`67fca8899cf70e20b2355e2adf61d9a05080012d3dfbc3f7b36938403cfa0390`.
Every tracked source file and both production/probe binaries matched that parent
freeze before and after the exclusive serialized run.

All six declared cells ran once, with no warmups or adaptive retries. Four native
reads completed; both above-boundary reads returned the precise expected limit
refusal. There were no unexpected failures, censored or missing attempts. The
independent retained-artifact audit checked all six complete captures, exact
ordered range/accounting prefixes, source immutability, counters and frozen
bindings. Independent actual-evidence review passed. Detailed evidence remains
private; the [sanitized authored-only summary](read-limits/byte-boundary-results.v1.json)
retains every cell, including both refusals and all final process counters.

| Cell | Planned logical bytes | Actual source bytes / requests | Native read ms | Process ms |
| --- | ---: | ---: | ---: | ---: |
| Metadata below | 8,388,607 | 8,388,607 / 98 | 2.9621 | 91.4752 |
| Metadata at | 8,388,608 | 8,388,608 / 98 | 3.3318 | 28.5010 |
| Metadata above, refused | 8,388,609 | 8,388,597 / 97 | 2.4494 | 24.4541 |
| Block below | 1,050,570 | 1,050,570 / 98 | 0.4524 | 12.0936 |
| Block at | 1,050,571 | 1,050,571 / 98 | 0.4897 | 15.2467 |
| Block above, refused | 1,050,572 | 492 / 60 | 0.0847 | 12.3981 |

The metadata-above cell refused its final 12-byte request; the block-above cell
refused its 1,048,577-byte CMT1 request. Neither offending request reached the
source, and neither produced complete metadata or a reported charged-byte result.
Sampled working-set maxima across the six cells ranged from 5,124,096 to
20,692,992 bytes; sampled private-commit maxima ranged from 2,768,896 to
21,721,088 bytes. Final user CPU counters were 0 or 15,625,000 ns and final system
CPU counters were 0 ns, at the observed counter resolution. The source used an
in-memory buffer. All six final OS logical read counters were zero
operations/bytes; process output and other logical operations remain separately
reported in the summary.

Direct-process counters include fixture construction, hashing and JSON output;
the probe's native read timer excludes those steps. Final memory counters can be
lower than sampled maxima. Sampled memory is not an allocation peak, and physical
traffic remains unavailable. These six single observations establish no
performance distribution, noise/regression budget, OS quota, hard-capacity
admission or six-limit policy. Hard-ceiling tests remain configuration-only.

Verification: `cargo test --test reader_byte_boundaries`,
`cargo build --example reader_byte_boundaries`, and
`python scripts/check_read_limits.py`. The latter remains the separate #0064
scalar specification check.

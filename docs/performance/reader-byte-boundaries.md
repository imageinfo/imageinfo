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

The campaign is pending the parent's serialized measurement slot. Native
correctness tests alone establish no time, CPU, memory or logical-I/O measurements.
Direct-process counters include fixture construction, hashing and JSON output;
the probe's native read timer excludes those steps. Sampled memory is not an
allocation peak, physical traffic is unavailable, and no noise/regression budget,
OS quota or six-limit policy follows from this finite campaign.

Verification: `cargo test --test reader_byte_boundaries`,
`cargo build --example reader_byte_boundaries`, and
`python scripts/check_read_limits.py`. The latter remains the separate #0064
scalar specification check.

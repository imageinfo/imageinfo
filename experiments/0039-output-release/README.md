# Fresh owned output-policy release experiment

**#0039** qualifies the live operational-output gap under first-ranked #0022.
It uses authored 64 KiB markers, not camera media. No production writer/profile,
source ACL change, elevation, key management or restart repair is introduced.

```console
cargo build --locked --release --manifest-path experiments/0039-output-release/Cargo.toml
python experiments/0039-output-release/qualify.py --binary experiments/0039-output-release/target/release/imageinfo-output-release-probe.exe --parent .local/output-release-qualification
python experiments/0039-output-release/audit.py --root <retained-private-run> --binary experiments/0039-output-release/target/release/imageinfo-output-release-probe.exe --public docs/write-safety/output-release-observations.json
```

The process exclusively creates an ordinary private root and fresh sealed stage,
retains the creation handle, validates identity/content/properties, and conditionally
renames that same object to `output.marker`. It checks again before attempting the
existing `SetSecurityInfo` helper on the owned handle. Requested creator masks compare
ordinary read/write plus DELETE/READ_CONTROL/WRITE_DAC, explicit full control, and
missing WRITE_DAC. Requested rights are not claimed to be granted rights.

All three sealed cases return actual access denied and retain the sealed output.
The ordinary unsealed control reaches the setter but fails the existing exact
descriptor check; no descriptor flags are ignored or guards weakened. Both outcomes
are reported as `owned-output-policy-release-unverified`, never committed.

Thirty cases cover eight held actors, four actors after the attempted release,
three process-kill and three cancellation boundaries, two labeled protocol injections,
a foreign collision winner, post-exit editing/name behavior and three strict refusals.
Normal sealed files permit read but deny data/ADS/time/security/link/attribute actors
after exit. **Post-exit rename and deletion succeed**: this is restricted editing,
not immutable storage. The ordinary control is deliberately writable after exit.

Qualifiers require Python assertions enabled. Capture helper and same-user actors
reuse project-owned #0034/#0033 code. Each process has its existing 60-second watchdog;
individual waits are 15 seconds. Control input is bounded to 32 bytes, marker reads
to 65,537 bytes, and there is no tree search, deletion retry or pathname ACL repair.
Every root/capture and earlier attempt stays private. Unix adapters refuse before
worker artifacts. The actual matrix, rather than an empty Rust test harness, supplies
native verification; source format/lint/build gates run on three platforms.

See [public findings](../../docs/write-safety/output-release.md),
[dependency admission](../../docs/write-safety/output-release-dependencies.json) and
[boundary review](ffi-review.md). Other strategies and platform/filesystem versions
are not ruled out by these observations. The complete #0022 backend remains open.

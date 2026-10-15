# Second environment reference reproduction

Card **#0073**, method dated **2026-10-15**. The separate
[research runner](../../experiments/0073-reference-reproduction/reproduce.py)
replays the initial admitted private baseline's ExifTool **13.59** operations in
an existing **Ubuntu 26.04 LTS WSL2** environment with native Linux **Perl 5.40.1**.
The original baseline used Windows Strawberry Perl 5.32.1. WSL runs a Linux
kernel and Linux ELF interpreter; changing the invoking shell alone is not the
environment distinction. Working data remains on the existing NTFS volume through
WSL's filesystem bridge, so this is not a separate physical storage experiment.

The source remains pinned to ExifTool commit
`2200871d9cef988051d2a99d67df3bda6cbb30a8`. The existing selected-source manifest,
historical API observer and baseline records supply the operation definitions.
No moving reference release, new root dependency or production behavior is added.
The original 13.55 comparison is outside this replay.

## Private reproduction procedure

Authorized maintainers need the restricted baseline and existing admitted source
packages. Review its fixture grants before execution: camera-derived reports,
including aggregate outcomes, remain private because `publishReports` is denied.
This page publishes the procedure and its limits; it publishes no camera results,
counts, per-image identities, captured metadata or photographs.

Run in the declared native Linux runtime with an absolute repository path and a
fresh directory under its ignored `.local` tree:

```console
python3 experiments/0073-reference-reproduction/reproduce.py --repository REPOSITORY --output REPOSITORY/.local/NEW_PRIVATE_RUN
python3 experiments/0073-reference-reproduction/audit.py --ledger REPOSITORY/.local/NEW_PRIVATE_RUN/ledger.private.json --output REPOSITORY/.local/NEW_PRIVATE_RUN/audit.private.json
```

The runner verifies historical artifact hashes and scoped admission, binds source,
runtime and observer identities, then orders records by their original start times.
It preserves the exact option tokens and empty configuration argument. Only the
interpreter and absolute path tokens change for Linux. Every generated XMP output
has a fresh destination; subsequent operations consume the new derivative. Nested
preview reads likewise consume the newly extracted binary capture. Existing RAWs,
baseline sidecars, captures and manifests are immutable inputs.

The private ledger retains baseline-record identities, both exact argument arrays,
the declared process environment, UTC timing, exit/timeout status, stdout/stderr
bytes, per-call input hashes, regenerated-input identities and generated artifacts.
Source/runtime inventories bracket execution. A 180-second process timeout matches
the historical bound; memory, decoded-byte, depth and record caps remain explicitly
unconfigured. This trusted private-input replay establishes no adversarial bound.
Save the executed runner byte for byte inside each private run and bind it in
the ledger. The published wrapper's failure-handler guard prevents a rejected
existing destination receiving a failure report and has an authored refusal test.
When reviewing retained captures, inspect their actual executed snapshot and any
private refinement record; do not infer execution from the current wrapper bytes.
Keep both exact identities and the scope of any later change private with the
evidence. The exact-decimal auditor can independently process retained captures
without rerunning the reference engine. This procedure states no camera outcome.

## Comparison and review boundaries

The comparison policy is saved and hashed before replay. It declares **no excluded
fields**. JSON comparison rejects duplicate members and nonfinite values, preserves
scalar types and array order, and ignores only object-member serialization order.
JSON numbers use exact numeric comparison; spelling variants such as `1`, `1.0`
and `1.00` compare as the same number, while booleans, strings and null retain
their distinct kinds. Large decimal values are not rounded through binary floating
point. Original capture bytes still distinguish their number spellings.
Binary resources, write-status output and stderr use exact byte comparison.
Environment paths, module locations and filesystem observations can therefore
appear as explicit differences; no blanket normalization silently removes them.
The complete equality/difference ledger stays private, including values needed to
explain each finite discrepancy.

Independent auditing of captures and inventory bindings is separate from using an
independent metadata engine. Repeating the same pinned engine under another runtime
does not independently validate RAW or JPEG decoding, metadata semantics, safe
writes, privacy removal, performance, all ExifTool behavior or general cross-platform
parity. The replay supplies no production format, storage-profile or write admission.

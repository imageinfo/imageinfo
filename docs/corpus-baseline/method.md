# Reference method and private evidence

Observation date: **2026-10-10**. These are research-tool choices, not imageinfo
implementation dependencies or architecture decisions.

## Source and runtime identity

The primary reference is ExifTool **13.59**, pinned at
[`2200871d9cef988051d2a99d67df3bda6cbb30a8`](https://github.com/exiftool/exiftool/tree/2200871d9cef988051d2a99d67df3bda6cbb30a8).
The comparison is **13.55**, pinned at
[`de11d240cf7e521e939a0575a128ffe01b63be05`](https://github.com/exiftool/exiftool/tree/de11d240cf7e521e939a0575a128ffe01b63be05).
The [official release history](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/history.html)
identifies 13.55 as the most recent production release in this retrieved baseline;
13.59 is a development release. This is dated evidence, not a moving “latest” pin.

Unmodified `exiftool`, `lib`, `README` and `LICENSE` were obtained through sparse
official Git checkouts; no upstream sample-image collection was imported. Exact
selected-source packages and per-file hash manifests are retained privately.
The existing Windows application remains at **12.76**; it was not upgraded globally.
The isolated 13.55 and 13.59 source tools were actually invoked and version-checked.

Both ran with the existing Strawberry Perl **5.32.1 x64** interpreter. Its 462-file
runtime/library manifest and retained notices identify what was present; the
installed runtime was not independently rebuilt or authenticated against its
original installer. The stripped installation needed JSON::PP **4.04**, acquired
from matching official [Perl 5.32.1 source](https://github.com/Perl/perl5/tree/df9d952d734ef94233ed84af97ca318d7972eed0/cpan/JSON-PP),
with the source's Artistic and Copying notices retained. No global Perl configuration
was changed. Private reviews authorize unmodified local reference execution and
storage, not redistribution or incorporation into imageinfo.

The inventory's executable hash identifies the **interpreted ExifTool entry script**.
Private experiment tool descriptors identify the invoked **Perl executable**, plus
pinned source, runtime components and driver manifests. Neither single hash alone
identifies the complete executable toolchain. Private oracle records are acquired
instances; the published [planned oracle example](../fixture-plan/oracle-profile.v1.json)
remains unchanged so historical synthetic examples keep their exact identities.

## Acquisition and observation controls

1. Index supplied candidates locally, select eight by size/time quantiles, hash
   originals, copy, verify source/copy hashes and source modification times, and
   mark received RAW copies read-only. Retain a restricted source map and permission
   record. Do not place private filenames in public reports.
2. Record tool versions, source commits, executable/runtime/module/driver hashes,
   acquisition packages and notices. Verify ExifTool modules loaded by the API
   driver resolve under the pinned source tree.
3. Run the planned RX-002/RX-003 normalized/display recipes against every received
   RAW using both references. Disable default configuration with `-config ""`.
   Keep group/path/duplicate information and both presentation views. Strict JSON
   loading rejects duplicate object members in the captured results.
4. Use a private API observer with `Duplicates`, `Unknown`, `Struct`, `SavePath`,
   `SaveFormat` and `Binary` enabled, `PrintConv=0`, `ListJoin=0`, and configuration
   disabled before module import. Record tag IDs/languages, group families 0–7 and
   Raw/Rational/ValueConv/PrintConv views. Byte strings carry byte evidence; binary
   values carry lengths/digests. These are upstream observations, not native model
   serialization or a completed canonical adapter.
5. Resolve each preview selector uniquely, extract with `-b`, compare its exact
   bytes with the API binary value, and read its nested metadata. Keep padding.
6. Create separately named XMP outputs, record parent/recipe identities, and read
   them through CLI/API. Preserve the supplied RAW and every preceding sidecar.
7. Retain exact argv, allowlisted environment, UTC start/end times, termination,
   stdout/stderr, input hashes before/after and output artifacts for each run.
   Recheck originals and received copies at completion.

The environment records Windows version/architecture, NTFS working storage,
`LC_ALL=C`, `LC_CTYPE=C`, `LANG=C`, `TZ=UTC0`, and explicit library paths.
Perl locale and localtime/gmtime probes support those settings. A hostile local
configuration sentinel was detected without suppression and suppressed with the
CLI flag/API initialization, for the tested entry points. The host timezone is
separate from the reference process setting.

Each invocation had a **180-second supervised timeout**. Memory, decoded-byte,
depth and record-count caps were **not configured**. This trusted private-input
characterization does not demonstrate adversarial resource safety. Experiment
schema version 2 records those absent limits as null with individual explanations;
version 1 still requires configured values. No limits were invented to make the
records appear more complete.

Two early observer attempts exposed incorrect assumptions: the first omitted
explicit binary API mode; the second assumed EOI must occupy the final two bytes.
Their captures, drivers and reasons are retained separately. The 97-run count covers
the corrected final runs, excluding setup probes and those failed attempts.

## Reproduction and independence limits

Authorized maintainers need the restricted fixture manifests, source mapping,
provenance reviews, acquired profiles, reference packages/manifests, observer
drivers, exact argv/environment and captured artifacts. Resolve their configured
artifact roots, validate schemas and hashes, recreate the private environment,
and run against fresh working copies with separately named outputs. A public
reader can inspect the requirements and aggregate findings, but cannot reproduce
this exact media corpus from the public repository alone.

The auxiliary Python standard-library XML check parses all three sidecars and
asserts selected labels, subject entries, language alternatives and a one-hour
base-clock difference. Its script/report are retained, but it has not been promoted
to a complete `independentRuns` validator record. Consequently this report makes
no independent write-safety or RAW-usability claim. `independentRuns` remains empty
in the reference-only records. A later validator must identify its exact components,
environment and bounded assertions before supplying such evidence.

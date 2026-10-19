# imageinfo

A modern, approachable metadata tool, starting with **camera RAW images**.
Full ExifTool feature parity is the long-term goal; the first delivery scope is
deliberately focused on RAW photography workflows.

**First target: Canon EOS R5 `.CR3` files**, associated XMP sidecars, and embedded
previews, prioritizing the camera's full RAW setting. C-RAW is tracked separately;
other RAW families follow later. See the
[Canon EOS R5 milestone](docs/canon-eos-r5-cr3.md).

**Status: first native R5 reader.** Terry accepted
[ADR-0011](docs/implementation-selection/README.md). The current build provides
a [declared R5 full RAW metadata/preview slice](docs/reader/README.md), contextual
help, version reporting and explicit partial coverage. Broader command examples
remain proposals; other RAW variants and metadata writes are not implemented.
The build also provides a [read-only date-intent preview](docs/reader/date-preview.md)
and [explicit or opt-in same-stem RAW/XMP pairing](docs/sidecars/pairing.md).
The library provides bounded [in-memory XML/XMP packet inspection](docs/sidecars/packet-profile.md),
without sidecar publication or general XML semantic clearance. It can also
validate [saved preview intent](docs/legacy-compatibility/cr3-preview-plan.md) and
[revalidate its source binding](docs/legacy-compatibility/cr3-preview-source-binding.md).
These observations keep mutation and storage admission refused.
The library also exposes an opt-in [read-session runtime](docs/legacy-compatibility/read-session-library.md)
over caller-owned buffered input/output, with bounded JSONL frames and fresh
metadata-read requests. The [session CLI](docs/legacy-compatibility/read-session-process.md)
exposes the same v1 runtime through `imageinfo session read` on standard input/output.

```console
cargo run --locked -- help
cargo run --locked -- metadata read help
cargo run --locked -- version --output json
cargo run --locked -- preview date-time-original help
cargo run --locked -- sidecar pair help
```

See [reader behavior and limits](docs/reader/README.md),
[setup/checks](docs/foundation/README.md) and [validation](docs/reader/validation.md).

The project starts with three goals:

- Build toward ExifTool's functionality through an explicit, evidence-based
  compatibility program, starting with RAW format and metadata edge cases.
- Make that power discoverable through a hierarchical CLI, contextual help at every
  level, and optional interactive cascading menus.
- Build a sustainable project with shared format knowledge, reproducible validation,
  documented decisions, and a practical path for multiple maintainers.

Start with the [documentation index](docs/README.md),
[product requirements](docs/product-requirements.md), and
[CLI requirements](docs/cli-requirements.md).

The RAW roadmap includes DNG and proprietary camera RAW formats, associated XMP
sidecars, and embedded preview metadata/extraction, starting with EOS R5 CR3.
Standalone rendered images,
video, audio, documents, and archives are deferred. RAW development, rendering,
and pixel conversion are outside this metadata tool's scope. See the
[RAW scope](docs/raw-scope.md).

The [roadmap](docs/roadmap.md) distinguishes the long-term compatibility goal from
RAW-first delivery. The [research ledger](docs/research-sources.md) records sources and limits
of the initial investigation. ExifTool is the independent upstream project by Phil
Harvey and its contributors; imageinfo is not affiliated with or endorsed by it.

## Project decisions

The initial requirements and private R5 reference baseline have been reviewed.
Rust is accepted; the [first implementation milestone](docs/implementation-selection/first-milestone.md)
defines a bounded read-only start. Architecture and evidence develop incrementally.
The project uses the [MIT license](LICENSE), with copyright attribution to Terry Ott
and imageinfo contributors. See the [license decision](docs/license-decision.md).
No ExifTool code, tag tables, or test images are vendored here.

## Local planning

Contributors can use [GitHub issues](https://github.com/imageinfo/imageinfo/issues)
and pull requests without access to the local board. See [CONTRIBUTING.md](CONTRIBUTING.md)
for onboarding and current checks, [GOVERNANCE.md](GOVERNANCE.md) for the proposed
shared-maintenance model, and [SECURITY.md](SECURITY.md) for security concerns.

Work is tracked on a local localswim board. Private board data, credentials, service
descriptors, and logs are excluded from this repository. See
[local board setup](docs/local-board.md) for the workflow.
The [dated executable runway](docs/planning/executable-runway-2026-10-19.md)
distinguishes immediately executable handoffs from dependency waits and owner holds.

# Fixed-width CR3 candidate experiment

Card **#0021**, first child of **#0014**, observed **2026-10-11**. Terry chose new
CR3 outputs first and authorized splitting the safety work. This is research code,
kept outside the production package. The production CLI still exposes no metadata
writer. No publication/storage profile is enabled by this experiment.

The probe stages one existing CMT2 `EXIF:DateTimeOriginal` as the fixed invented
value `2001:02:03 04:05:06`, preserving its 20-byte ASCII allocation. It never
inserts/deletes a tag, moves a block, patches an arbitrary offset, rewrites the
source, or recompresses sensor bytes. Other date, offset and subsecond occurrences
stay unchanged; this intentionally leaves date copies unsynchronized. That is a
visible experiment limitation, not a proposed automatic date-editing rule.

See the [evidence and boundaries](../../docs/write-safety/new-output-preservation.md).

## Build and check

Use the root's pinned Rust 1.99.0 toolchain. This small standalone Cargo package
depends on the existing imageinfo reader and Serde JSON; its lockfile adds no new
registry packages. No decoder or upstream metadata implementation is linked.

```console
cargo fmt --manifest-path experiments/0021-cr3-candidate/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0021-cr3-candidate/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0021-cr3-candidate/Cargo.toml
cargo build --locked --release --manifest-path experiments/0021-cr3-candidate/Cargo.toml
```

Run only on admitted media in a private research directory with sufficient scratch
space. Supply a new staging name ending in `.candidate.cr3`:

```console
imageinfo-cr3-candidate-probe stage admitted-source.cr3 private.candidate.cr3
```

The fixed test value is intentional: this tool is a preservation experiment, not a
general-purpose editor. Successful output reports `private-candidate-validated`
and `published: false`. It rereads actual candidate bytes, compares the entire
complement of the edit, and checks declared occurrence/resource values and spans.

An existing candidate is never overwritten. An already satisfied test edit creates
nothing. This tests the probe's edit effect, not the future production request to
create a new output: that request must account for namespace creation even when its
input metadata already matches. #0023 defines that user-visible behavior separately.
An error or forced kill after staging begins may retain a partial private artifact;
there is no production cleanup or recovery engine. A staging name must never be
treated as a committed output. The caller supplies private-directory access controls;
the probe does not enforce the future private-owner permission policy.

On Windows, a held read handle denies new content-write/delete handles through
the copy and comparison. The separate `source_guard` tool lets a test supervisor
observe that same share mode. Ancestor identity, properties and persistence remain
unverified. On Unix, the probe has no equivalent exclusion guard; synthetic CI
checks do not establish a usable Linux/macOS mutation profile.

## Disposable storage observations

`storage_probe.py` accepts a disposable scratch **parent**, never a RAW path. It
creates its own retained directory, uses authored marker data, and kills only its
own bounded child processes at explicit stdin/stdout barriers. It does not crash
the OS, interrupt the host, or claim power-loss recovery.

```console
python experiments/0021-cr3-candidate/storage_probe.py --parent PRIVATE_SCRATCH_PARENT
```

Windows can additionally pass `--guard PATH_TO_SOURCE_GUARD_EXE`. The script records
and checks controlled stale replacement, no-clobber linking, advisory/share guards,
directory-flush calls and four process-kill boundaries. Every report explicitly
sets `profileVerified: false`. Retained directories/reports are local research data;
do not publish them or include them in a release.

These observations identify requirements for **#0022**, not a reusable production
transaction abstraction. **#0023** integrates a reviewed writer only after those
gates pass. Do not promote this code merely because its candidate comparisons pass.
**#0027** retains write admission/checksum/authenticity refusal proof.

# Read-only CR3 date admission research

**#0027**, observed **2026-10-12**. The root library's
[`reader::admission`](../../src/reader/admission.rs) supplies native observations
for the proposed existing CMT2 DateTimeOriginal ASCII20 edit. This separate
executable is research, not a product mutation command. It writes no source,
candidate, report, sidecar or destination. Every result denies production mutation.
See [the qualification and remaining gates](../../docs/write-safety/write-admission.md).

```console
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo build --locked --release
cargo fmt --manifest-path experiments/0027-cr3-admission/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0027-cr3-admission/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0027-cr3-admission/Cargo.toml
cargo build --locked --release --manifest-path experiments/0027-cr3-admission/Cargo.toml
imageinfo-cr3-admission-probe inspect SOURCE "2000:02:29 23:59:59" [EXPECTED_OFFSET]
```

The optional offset asserts the current unique occurrence's allocation, with fixed
length 20. It is a conflict check, not a saved-plan identity, file guard or authority.
Root library callers supply a stable Read+Seek stream and typed `DateTime`; no JSON
profile/boolean is imported. The CLI rejects non-regular directly named inputs,
holds a read handle (Windows read sharing only), and compares length/mtime before
and after. These are invocation observations, not complete source/path/property
guards. Ordinary read/access-time effects remain possible.

Input dates use exact ASCII `YYYY:MM:DD HH:MM:SS`, years 1..9999 and seconds 0..59.
Blank/partial dates, invalid Gregorian dates, timezone suffixes/conversions,
fractions, leap seconds, trimming, insertion/deletion/growth and other fields are
outside this proposed operation. The source date must also be complete in the
unique existing ASCII20 slot. Other date, offset and subsecond copies are separate;
an already matching value never bypasses provenance/dependency/storage gates or
authorize creating a new output name.

Exit 0 means the **read-only assessment completed**, including explicit refusals.
Exit 2 reports a bounded request/input/structure/limit diagnostic. Neither means
metadata application succeeded. JSON contains occurrence ranges for private review;
public qualification summaries remove offsets, dates, paths and per-image hashes.
No product CLI exit-code/wire-contract compatibility is claimed.

## Private derivative reproduction

`qualify_private.py` requires an explicit reviewed manifest binding eight admitted
clones, their expected hashes, existing decoded baselines, pinned native/#0021/
ExifTool/Perl/LibRaw executable identities, inherited corpus/tool permission and a
new empty owner-only scratch directory. It never expands a directory glob into
permission. It creates only separately named derivatives there, with exclusive
new-file opens, and checks every tool input's hash/mtime before and after.

```console
python experiments/0027-cr3-admission/qualify_private.py --manifest PRIVATE_REVIEWED_MANIFEST --root NEW_EMPTY_PRIVATE_ROOT --public SANITIZED_SUMMARY_PATH
```

On the observed Windows machine the owner-only ACL is installed and verified on
the new empty scratch root **before** copying any private bytes. This does not
qualify atomic private-root creation or recovery custody for a production backend.
At least 8 GiB free scratch was checked for this bounded eight-file run. The driver
uses a 120-second child timeout, not an OS hard memory/aggregate-output quota.
It retains all derivatives, captures, tool/argv/environment hashes and lineage.
Do not run it on unadmitted media, publish the private manifest/captures, or treat
its manifest as an application authorization. The driver is private evidence
tooling, not a production library dependency or per-request external validator.

The #0021 candidate is used only to demonstrate its previously documented
undecoded-pointer limitation. Eight deliberately aliased date derivatives show
both date names changing despite an exact complement and identical independent
RAW unpack. The native admission gate refuses that allocation alias. None of those
private candidates is published as a user output or replaces an existing file.

Dependency archives/notices match [the root notices](../../THIRD_PARTY_NOTICES.md)
and [scoped admission](../../docs/write-safety/admission-dependencies.json).
No new root dependency, C2PA SDK linkage, upstream implementation, tag table,
camera fixture or compiled release artifact is imported/distributed. Pinned
ExifTool 13.59 and LibRaw 0.22.2 remain separately admitted private subprocess
references under the existing corpus/tool review.

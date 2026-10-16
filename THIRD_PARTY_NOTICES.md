# Third-party notices

imageinfo is MIT licensed. Third-party packages keep their own terms.

This collection identifies the exact Cargo.lock graph admitted for local/CI foundation builds. It retains copyright/license notices; dependency source is fetched through Cargo and is not vendored here. A release must include the applicable notices with the actual compiled distribution and receive an assembled-artifact review.

The local MIT `imageinfo-windows-storage` crate (#0166/#0195) uses the existing
exact `winapi-util 0.1.11`, `windows-sys 0.61.2` and `windows-link 0.2.1`
packages below. Its additional Windows SDK feature selection and isolated unsafe
boundary are reviewed in [SDK-REVIEW.md](crates/imageinfo-windows-storage/SDK-REVIEW.md);
no external package version or notice changes are introduced.

| Package | Selected terms | Retained notice |
| --- | --- | --- |
| anstyle 1.0.14 | MIT | [anstyle-1.0.14-LICENSE-MIT.txt](licenses/dependencies/anstyle-1.0.14-LICENSE-MIT.txt) |
| block-buffer 0.10.4 | MIT | [block-buffer-0.10.4-LICENSE-MIT.txt](licenses/dependencies/block-buffer-0.10.4-LICENSE-MIT.txt) |
| cfg-if 1.0.5 | MIT | [cfg-if-1.0.5-LICENSE-MIT.txt](licenses/dependencies/cfg-if-1.0.5-LICENSE-MIT.txt) |
| clap 4.6.7 | MIT | [clap-4.6.7-LICENSE-MIT.txt](licenses/dependencies/clap-4.6.7-LICENSE-MIT.txt) |
| clap_builder 4.6.7 | MIT | [clap_builder-4.6.7-LICENSE-MIT.txt](licenses/dependencies/clap_builder-4.6.7-LICENSE-MIT.txt) |
| clap_lex 1.1.1 | MIT | [clap_lex-1.1.1-LICENSE-MIT.txt](licenses/dependencies/clap_lex-1.1.1-LICENSE-MIT.txt) |
| cpufeatures 0.2.17 | MIT | [cpufeatures-0.2.17-LICENSE-MIT.txt](licenses/dependencies/cpufeatures-0.2.17-LICENSE-MIT.txt) |
| crypto-common 0.1.7 | MIT | [crypto-common-0.1.7-LICENSE-MIT.txt](licenses/dependencies/crypto-common-0.1.7-LICENSE-MIT.txt) |
| digest 0.10.7 | MIT | [digest-0.10.7-LICENSE-MIT.txt](licenses/dependencies/digest-0.10.7-LICENSE-MIT.txt) |
| generic-array 0.14.7 | MIT | [generic-array-0.14.7-LICENSE.txt](licenses/dependencies/generic-array-0.14.7-LICENSE.txt) |
| itoa 1.0.18 | MIT | [itoa-1.0.18-LICENSE-MIT.txt](licenses/dependencies/itoa-1.0.18-LICENSE-MIT.txt) |
| libc 0.2.190 | MIT | [libc-0.2.190-LICENSE-MIT.txt](licenses/dependencies/libc-0.2.190-LICENSE-MIT.txt) |
| memchr 2.8.3 | MIT | [memchr-2.8.3-LICENSE-MIT.txt](licenses/dependencies/memchr-2.8.3-LICENSE-MIT.txt) |
| proc-macro2 1.0.107 | MIT | [proc-macro2-1.0.107-LICENSE-MIT.txt](licenses/dependencies/proc-macro2-1.0.107-LICENSE-MIT.txt) |
| quote 1.0.47 | MIT | [quote-1.0.47-LICENSE-MIT.txt](licenses/dependencies/quote-1.0.47-LICENSE-MIT.txt) |
| roxmltree 0.21.1 | MIT; inherited ego-tree ISC attribution | [roxmltree MIT](licenses/dependencies/roxmltree-0.21.1-LICENSE-MIT.txt), [ego-tree ISC](licenses/dependencies/roxmltree-0.21.1-ego-tree-ISC.txt) |
| same-file 1.0.6 | MIT | [same-file-1.0.6-LICENSE-MIT.txt](licenses/dependencies/same-file-1.0.6-LICENSE-MIT.txt) |
| serde 1.0.229 | MIT | [serde-1.0.229-LICENSE-MIT.txt](licenses/dependencies/serde-1.0.229-LICENSE-MIT.txt) |
| serde_core 1.0.229 | MIT | [serde_core-1.0.229-LICENSE-MIT.txt](licenses/dependencies/serde_core-1.0.229-LICENSE-MIT.txt) |
| serde_derive 1.0.229 | MIT | [serde_derive-1.0.229-LICENSE-MIT.txt](licenses/dependencies/serde_derive-1.0.229-LICENSE-MIT.txt) |
| serde_json 1.0.152 | MIT | [serde_json-1.0.152-LICENSE-MIT.txt](licenses/dependencies/serde_json-1.0.152-LICENSE-MIT.txt) |
| sha2 0.10.9 | MIT | [sha2-0.10.9-LICENSE-MIT.txt](licenses/dependencies/sha2-0.10.9-LICENSE-MIT.txt) |
| strsim 0.11.1 | MIT | [strsim-0.11.1-LICENSE.txt](licenses/dependencies/strsim-0.11.1-LICENSE.txt) |
| syn 3.0.7 | MIT | [syn-3.0.7-LICENSE-MIT.txt](licenses/dependencies/syn-3.0.7-LICENSE-MIT.txt) |
| typenum 1.20.1 | MIT | [typenum-1.20.1-LICENSE-MIT.txt](licenses/dependencies/typenum-1.20.1-LICENSE-MIT.txt) |
| unicode-ident 1.0.26 | MIT AND Unicode-3.0 | [unicode-ident-1.0.26-LICENSE-MIT.txt](licenses/dependencies/unicode-ident-1.0.26-LICENSE-MIT.txt), [unicode-ident-1.0.26-LICENSE-UNICODE.txt](licenses/dependencies/unicode-ident-1.0.26-LICENSE-UNICODE.txt) |
| version_check 0.9.5 | MIT | [version_check-0.9.5-LICENSE-MIT.txt](licenses/dependencies/version_check-0.9.5-LICENSE-MIT.txt) |
| winapi-util 0.1.11 | MIT | [winapi-util-0.1.11-LICENSE-MIT.txt](licenses/dependencies/winapi-util-0.1.11-LICENSE-MIT.txt) |
| windows-link 0.2.1 | MIT | [windows-link-0.2.1-license-mit.txt](licenses/dependencies/windows-link-0.2.1-license-mit.txt) |
| windows-sys 0.61.2 | MIT | [windows-sys-0.61.2-license-mit.txt](licenses/dependencies/windows-sys-0.61.2-license-mit.txt) |
| zmij 1.0.23 | MIT | [zmij-1.0.23-LICENSE-MIT.txt](licenses/dependencies/zmij-1.0.23-LICENSE-MIT.txt) |

See [the admission record](docs/foundation/dependencies.json). No license choice here relicenses upstream source.

The #0082 read-only explicit pairing resolver adds exact `same-file` 1.0.6 to
the root graph, with `winapi-util` 0.1.11, `windows-sys` 0.61.2 and `windows-link`
0.2.1 on Windows. Their MIT notice bytes were checked against the exact cached
package archives and reused where already retained for research. This is a
separate production dependency admission for the
[bounded pairing API](docs/sidecars/pairing.md); it does not promote any research
publication, storage or recovery implementation.

The #0077 source binding admits exact `sha2` 0.10.9 with default features disabled
and `std` enabled. Its locked hashing/buffering/CPU-detection closure appears in
the table and admission record, including target-only `libc`. MIT notice bytes
and package archive hashes were checked against the exact registry packages.
SHA-256 supplies content integrity comparisons; it introduces no secrecy,
encryption or key-management requirement. The optional assembly dependency is
disabled. `generic-array` has a compiler-version cfg build script; target-only
`libc` has its upstream ABI/configuration build script. Their reviewed behavior
and target limits are recorded in the admission record. No new SDK wrapper or
root unsafe code is introduced.

The #0183 bounded in-memory XML/XMP packet profile adopts exact `roxmltree`
0.21.1 with default features disabled and `std`/`positions` enabled. Its only
linked dependency is existing `memchr` 2.8.3. MIT is selected for both; the
heavily modified ego-tree lineage additionally retains the ISC attribution
reviewed in #0081, with the original fork revision still unidentified. The
[packet profile](docs/sidecars/packet-profile.md) and root admission record name
this production boundary. Research XML crates remain separate; no serializer,
network resolver, file publication or cryptographic validation is adopted.

The separate #0028 research package has its own
[exact dependency admission](docs/write-safety/recovery-dependencies.json) and
[notice index](experiments/0028-recovery-evidence/NOTICES.md). Its SHA-256 and Linux
descriptor wrappers are admitted for scoped local/CI experiments, not production
adoption or an assembled executable release. Root Cargo.lock is unchanged.

The #0029 guard experiment has a separate
[27-package admission](docs/write-safety/guard-dependencies.json) and
[notice index](experiments/0029-object-guards/NOTICES.md), selecting MIT for the
additional `winapi-util` safe handle-information wrapper. This remains research
scope; no production dependency graph or license decision changes.

The #0032 Windows publication experiment reuses those same archive versions and
notices under its [scoped admission](docs/write-safety/bound-publication-dependencies.json)
and [notice index](experiments/0032-windows-publication/NOTICES.md). Direct SDK feature
use and the isolated native operations have a [boundary review](experiments/0032-windows-publication/ffi-review.md).
No Windows DLL, upstream implementation or public assembled executable is imported
or distributed. Root dependencies and the locked MIT project decision are unchanged.

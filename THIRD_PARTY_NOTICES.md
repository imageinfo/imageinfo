# Third-party notices

imageinfo is MIT licensed. Third-party packages keep their own terms.

This collection identifies the exact Cargo.lock graph admitted for local/CI foundation builds. It retains copyright/license notices; dependency source is fetched through Cargo and is not vendored here. A release must include the applicable notices with the actual compiled distribution and receive an assembled-artifact review.

| Package | Selected terms | Retained notice |
| --- | --- | --- |
| anstyle 1.0.14 | MIT | [anstyle-1.0.14-LICENSE-MIT.txt](licenses/dependencies/anstyle-1.0.14-LICENSE-MIT.txt) |
| clap 4.6.7 | MIT | [clap-4.6.7-LICENSE-MIT.txt](licenses/dependencies/clap-4.6.7-LICENSE-MIT.txt) |
| clap_builder 4.6.7 | MIT | [clap_builder-4.6.7-LICENSE-MIT.txt](licenses/dependencies/clap_builder-4.6.7-LICENSE-MIT.txt) |
| clap_lex 1.1.1 | MIT | [clap_lex-1.1.1-LICENSE-MIT.txt](licenses/dependencies/clap_lex-1.1.1-LICENSE-MIT.txt) |
| itoa 1.0.18 | MIT | [itoa-1.0.18-LICENSE-MIT.txt](licenses/dependencies/itoa-1.0.18-LICENSE-MIT.txt) |
| memchr 2.8.3 | MIT | [memchr-2.8.3-LICENSE-MIT.txt](licenses/dependencies/memchr-2.8.3-LICENSE-MIT.txt) |
| proc-macro2 1.0.107 | MIT | [proc-macro2-1.0.107-LICENSE-MIT.txt](licenses/dependencies/proc-macro2-1.0.107-LICENSE-MIT.txt) |
| quote 1.0.47 | MIT | [quote-1.0.47-LICENSE-MIT.txt](licenses/dependencies/quote-1.0.47-LICENSE-MIT.txt) |
| serde 1.0.229 | MIT | [serde-1.0.229-LICENSE-MIT.txt](licenses/dependencies/serde-1.0.229-LICENSE-MIT.txt) |
| serde_core 1.0.229 | MIT | [serde_core-1.0.229-LICENSE-MIT.txt](licenses/dependencies/serde_core-1.0.229-LICENSE-MIT.txt) |
| serde_derive 1.0.229 | MIT | [serde_derive-1.0.229-LICENSE-MIT.txt](licenses/dependencies/serde_derive-1.0.229-LICENSE-MIT.txt) |
| serde_json 1.0.152 | MIT | [serde_json-1.0.152-LICENSE-MIT.txt](licenses/dependencies/serde_json-1.0.152-LICENSE-MIT.txt) |
| strsim 0.11.1 | MIT | [strsim-0.11.1-LICENSE.txt](licenses/dependencies/strsim-0.11.1-LICENSE.txt) |
| syn 3.0.7 | MIT | [syn-3.0.7-LICENSE-MIT.txt](licenses/dependencies/syn-3.0.7-LICENSE-MIT.txt) |
| unicode-ident 1.0.26 | MIT AND Unicode-3.0 | [unicode-ident-1.0.26-LICENSE-MIT.txt](licenses/dependencies/unicode-ident-1.0.26-LICENSE-MIT.txt), [unicode-ident-1.0.26-LICENSE-UNICODE.txt](licenses/dependencies/unicode-ident-1.0.26-LICENSE-UNICODE.txt) |
| zmij 1.0.23 | MIT | [zmij-1.0.23-LICENSE-MIT.txt](licenses/dependencies/zmij-1.0.23-LICENSE-MIT.txt) |

See [the admission record](docs/foundation/dependencies.json). No license choice here relicenses upstream source.

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

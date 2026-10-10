# Card 0011 validation and decision boundary

Date: **2026-10-10**. Scope: language/component selection and disposable probes.

## Acceptance coverage

| Card criterion | Evidence |
| --- | --- |
| Compare modern options against compatibility, safety and CLI needs | Rust/Go/C# comparison; constraints mapped to PR/CLI/MDL requirements; 21 Rust CLI cases expose and exercise policy differences |
| Portability and performance | Primary target/deployment sources; Windows-only execution explicitly labeled; no cross-platform or performance ranking invented |
| Extensibility and maintenance | Data-first increment, no initial plugin/runtime framework, Rust contributor costs and Go fallback recorded |
| Concrete implementation recommendation | ADR-0011 names language, build approach, CLI/JSON components, ordinary library/binary boundary and deferred component choices |
| Reviewable delivery sequence | Executable foundation, bounded reader and declared R5 metadata/resource subset, with later XMP/menu/write gates |
| Evidence/provenance | Locked research graph with 15 archive checksums and retained license/notice identities; synthetic probes public, personal media/private captures excluded |
| Accepted decision | **Pending Terry's review**. Authorization to evaluate and prototype is not fabricated acceptance of the recommendation. |

## Checks performed

- Rust probe compiled and ran with the locked dependency graph; final 21 CLI cases,
  help/operand assertions, authored exact-wire round trip and six header cases pass.
- Go probe compiled and passed the same six header cases.
- Both compiled probes ran with a 60-second supervising timeout on eight private
  copies, returned zero, agreed on header counts and left all input hashes unchanged.
- All 15 cached registry package archives match Cargo.lock checksums. License
  declarations and retained notice files were reviewed. The unicode-ident package
  retains an additional Unicode-3.0 obligation alongside the MIT choice.
- All 15 scoped operational dependency reviews validate against the project's
  provenance schema; detailed local notice/handling evidence remains private.
- Documentation links, JSON, requirement references, consistency of command
  examples, source attribution, formatting and `git diff --check` were checked.

The research graph review allows the recorded local research uses. It does not
approve a future shipped dependency graph or certify supply-chain security.
No dependency implementations/binaries, media, personal paths, capture metadata
or private logs are included in the commit.

The card has no production build gate because no production implementation was
added. The research executables were actually built and run; that evidence does
not promote any of the 49 inventory capability rows beyond specified.

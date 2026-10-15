# Foundation verification

Subsequent #0020 implements the [native R5 slice](../reader/README.md).
The foundation record below describes its original increment; current read/list/
extract behavior and tests are authoritative in the linked reader guide.

Card **#0019**, observed 2026-10-10. This records the executable foundation's
limited implemented behavior, separately from future RAW capability evidence.

## Local results

- Pinned Rust/Cargo 1.99.0, Windows x64 MSVC, successful locked debug/release builds.
- Formatting and clippy with warnings denied pass.
- 16 local tests pass: twelve CLI/process tests, three wire tests and one
  transport-failure unit test.
  Table-driven cases cover root/group/leaf help spellings, malformed syntax with
  help, duplicate scalars across scopes, exact literal/Unicode/newline paths,
  noninteractive plain output, complete refusal envelopes and deterministic version
  JSON. Unix jobs additionally exercise non-Unicode path bytes.
- Synthetic wire transport retains duplicate ISO occurrences with different
  namespaces and raw versus normalized rational pairs. This is not a parser/model
  conversion test or complete metadata-contract implementation.
- Emitted version/refusal/usage-result JSON is checked against the applicable
  published schemas through the public recipe below.
- Sixteen exact registry archive checksums match Cargo.lock; scoped admission
  records validate against the provenance schema. Seventeen selected copyright/
  license notices are retained. Public release/vendoring review remains separate.
- All 34 scoped package, notice and CI-action reviews validate. The checkout
  action is pinned to the acquired official source revision and retains its license.
- Public docs links, JSON member uniqueness, requirement/source consistency,
  private-artifact boundaries and `git diff --check` pass.

## Reproduce schema checks

Use an available JSON Schema draft 2020-12 validator. This optional isolated QA
command uses Python tooling; it is not an imageinfo runtime dependency:

```console
uv run --no-project --with jsonschema==4.26.0 python scripts/check_output_schemas.py
```

Build `target/debug/imageinfo` first (or `target/debug/imageinfo.exe` on Windows).
The checker validates actual version/error records plus read-only date-preview
and explicit-path pairing observations. It compiles a temporary standard-library
Rust fixture harness using the public authored structural builder, so the pinned
`rustc` must also be on PATH. It resolves schema references locally, uses only
temporary authored inputs, and never fetches schemas or opens personal media.

## CI evidence

[Workflow run 38096862606](https://github.com/imageinfo/imageinfo/actions/runs/38096862606) passed all three jobs on code commit
`c94163819bda24dee23f7e518a3dba3f4e9b6ae5`. Formatting, clippy, tests, release builds and
public docs/JSON checks succeeded on Windows x64, Ubuntu x64 and macOS arm64.
Windows executes 16 tests; Unix jobs execute 17, including native non-Unicode path
bytes. The macOS toolchain log confirms `aarch64-apple-darwin`.
See [recorded run/job evidence](ci-results.json). These are foundation environments,
not a future RAW-reader compatibility or OS-baseline certification. The final board
handoff links the final published commit and its corresponding CI run.

**#0065 update, 2026-10-15:** The
[clean hosted contributor verification](../contributing/clean-machine.md)
records fresh hosted checkouts and pinned toolchain installation at
`5f7a86eca8e36b48d8334c8e754e3859dd9bb213`, with the actual 80 Windows / 82
Unix root tests, schema checks, release builds and sanitized token permission
inspection. This is a current contributor-check outcome; the original #0019
results above remain historical and no bare-OS or release-readiness claim follows.

## Remaining boundaries

No sensor/container/tag parsing, extraction, XMP handling, menu, configuration,
transport session, mutation or full result/metadata-schema capability is delivered.
The original increment used plain stderr for grammar failures. Subsequent
[#0037](../legacy-compatibility/native-json-errors.md) implements JSON syntax-error
routing for one unambiguous valid explicit selector, with portable executable tests.
Invalid/duplicate/absent format selection remains plain stderr. Broader #0015/LG-006
integration and RAW capability verification remain separate.

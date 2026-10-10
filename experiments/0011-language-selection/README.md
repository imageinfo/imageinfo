# Disposable implementation-selection probes

Card #0011 research only. These programs are deliberately small experiments, not
production imageinfo code, reusable parser infrastructure, or a supported CLI.
Do not promote them into the product. Findings belong in the decision record.

The Rust probe tests clap help/argument policy, exact JSON wire values, and a
bounded top-level BMFF header walk. The Go probe tests the same header-walk cases
using its standard library. Neither reads Canon metadata or develops RAW pixels.
Optional local file arguments are opened read-only; only aggregate counts are
printed. No personal fixture is bundled.

From this directory, using the toolchain versions recorded in the report:

```console
cargo run --locked --manifest-path rust/Cargo.toml
go run go/main.go
```

Append privately admitted CR3 paths to either command to repeat the optional
header walk. Do not publish those paths or tool output that identifies media.
Build outputs and local raw execution logs are ignored. Cargo.lock records exact
research dependencies; this is not imageinfo's product dependency selection.

The probes deliberately do not benchmark languages. They check feasibility and
expose assumptions. The C# alternative is a documentation comparison; no .NET SDK
was available in the inspected environment, so no C# prototype was run.

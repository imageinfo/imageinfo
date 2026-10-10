# imageinfo CLI requirements and proposed command model

Status: proposed user experience and interface contract; commands in this document are design examples and are not implemented. Research date and RAW-only scope revision: 2026-10-10. This specification intentionally makes no implementation language or framework choice. Product requirements use `PR-*`; interface requirements use `CLI-*`.

Current delivery scope is camera RAW metadata, associated XMP sidecars, and embedded-preview metadata/extraction. DNG and proprietary RAW families such as CR2/CR3, NEF/NRW, ARW, RAF, ORF, RW2, PEF, and SRW are the requirements horizon; each variant needs its own tested capability claim. The eventual ambition is full ExifTool feature parity, with other media families deferred to later scope decisions. No RAW pixel developing, rendering, demosaicing, or conversion is part of this CLI specification.

## What “like the AWS CLI” means

The first delivered camera/format is **Canon EOS R5 CR3**. Examples below use CR3
and paired XMP; other RAW names above describe later coverage. See the
[first milestone](canon-eos-r5-cr3.md).

AWS documents help at three levels: `aws help`, `aws ec2 help`, and `aws ec2 describe-instances help`. Operation help includes parameter explanations, examples, and output descriptions. Its v2 auto-prompt is a separate feature that suggests commands and arguments with descriptions and offers contextual documentation; shell completion is another separate feature. [AWS help](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-help.html), [AWS auto-prompt](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-parameters-prompting.html), [AWS completion](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-completion.html).

For imageinfo, translate this into three coordinated experiences: a predictable command hierarchy; complete help at every node; and an optional keyboard-driven cascading menu that builds the same command. The menu is an imageinfo proposal, not a claim that AWS help itself is a cascading menu. Interactive guidance must never interrupt scripts or mutate files merely because a user explored a menu.

## Proposed command tree

Common structure: `imageinfo <group> <operation> [options] [--] <inputs...>`. Global options are accepted before or after the group/operation and documented at every level. Bare root/group invocation shows concise help and exits without entering a menu. `interactive` or `--interactive` is an explicit request to enter guided mode.

```text
imageinfo
  help [command-path...]                    Browse offline help
  version                                  Version and capability-data revision
  interactive [command-path...]            Build/review a command through menus
  metadata
    read                                   Read selected or all metadata
    write                                  Set/append/remove/transform tag values
    delete                                 Delete selected tags/groups/blocks
    copy                                   Copy/map tags between files
    import                                 Load edits from a structured document
    export                                 Produce reports or interchange documents
    diff                                   Compare metadata with identity preserved
    sync                                   Reconcile namespaces using explicit policy
  tags
    list | search | show                   Discover canonical tags and capabilities
  formats
    list | show                            Discover RAW/XMP read/write constraints
  binary
    list | extract                         Inspect/export embedded RAW assets
  sidecar
    create | read | apply | diff            Work with RAW-associated XMP sidecars
  time
    inspect | set | shift | sync            Explain and change timestamp semantics
  geo
    inspect | set | tag | export | delete   RAW/XMP coordinates and track mapping
  files
    list | rename | move | copy | set-times Organize RAW files with paired sidecars
  privacy
    inspect | scrub | verify                Explain profile coverage and residuals
  validate
    file | plan                             Check structures or an intended mutation
  plan
    show | apply                            Review and apply saved changes
  backup
    list | restore | prune                  Manage recoverable originals
  batch
    run | status | resume                   Run ordered requests and inspect outcomes
  compat
    translate | report                     RAW-focused legacy migration guidance
  config
    show | set | reset                      Inspect provenance and configure defaults
  completion
    generate                               Emit shell integration for review
```

The tree is the proposed RAW-workflow discovery model. Early releases advertise only implemented operations; the capability inventory retains remaining RAW variants and workflows. Group help can link to planned RAW functionality but must mark it unavailable. Shortcuts/aliases can be explored later; canonical examples use the hierarchy. Broader ExifTool command/format coverage is deferred and does not become an initial requirement because it exists upstream.

Metadata operations take supported camera RAW files and their associated XMP sidecars. Standalone JPEG/PNG, video, audio, documents, and archives are out of current delivery scope. Extracted preview files are RAW-derived output assets; their extraction does not advertise standalone JPEG metadata support. `time`, `geo`, and `privacy` share the same RAW tag identities and mutation engine.

Default directory selection includes only recognized in-scope RAW inputs. Associated XMP selection requires an explicit sidecar/pairing workflow; arbitrary unrelated `.xmp` files are not swept into a RAW collection operation. An explicitly supplied out-of-scope media input receives a clear diagnostic rather than silently expanding the task.

## Help contract

All of these requests resolve to the same appropriate help node:

```text
imageinfo help
imageinfo --help
imageinfo metadata help
imageinfo metadata --help
imageinfo help metadata write
imageinfo metadata write help
imageinfo metadata write --help
```

Root help provides a one-sentence purpose, quick-start reads, mutation safety summary, groups, interactive entry point, output options, and a next-step example. Group help provides child operations, an explanation of their differences, common options, and two representative workflows. Leaf help provides synopsis, parameter types/defaults/constraints, tag/format prerequisites, side effects, examples, output fields, exit codes, and links to relevant local topics. Tag help describes canonical identity, aliases, groups, units, structure/list behavior, format-specific writability, and values.

Help is available offline, without credentials, network requests, or reading media files. Plain text is the baseline. A pager is allowed only for a terminal with explicit user configuration or an explicit option; `--no-pager` always bypasses it. Help redirected to a file contains no ANSI color, cursor control, progress, or prompt.

## Requirements and acceptance criteria

| ID | Priority | Requirement | Acceptance criterion |
| --- | --- | --- | --- |
| CLI-001 | P0 | Offer root/group/leaf help through both `help` and `--help`. | Walk every published node; all spellings return equivalent content and status 0 without media I/O. |
| CLI-002 | P0 | Use readable verb-oriented hierarchy and actionable usage errors. | Invalid group, operation, or flag returns status 2, the nearest valid help path, and bounded spelling suggestions; an unknown tag never becomes an accidental new tag. |
| CLI-003 | P1 | Provide cascading interactive menus with contextual help and breadcrumbs. | A novice can choose group → operation → inputs → tags/values → preview using keyboard navigation; Back and Cancel preserve the editing session without writing files. |
| CLI-004 | P0 | Keep automation deterministic and noninteractive. | When stdin or stdout is redirected or unavailable, no menu, confirmation, pager, or cursor control opens; explicit `--interactive` fails with an actionable error in this condition; `--no-interactive` overrides configuration. |
| CLI-005 | P0 | Share one command definition across help, validation, menus, and completions. | Each command's required parameters, defaults, and capability restrictions agree across all surfaces; interactive export produces an equivalent noninteractive command/request. |
| CLI-006 | P1 | Complete commands, flags, values, tags, namespaces, formats, profiles, and safe paths. | Published integrations for supported shells pass a shared completion corpus; completion performs no mutation, telemetry, or mandatory network access. |
| CLI-007 | P0 | Preserve tag identity and type in structured output. | Duplicate labels/groups/instances survive JSON and JSON Lines output; null/absent/empty/list/structure/binary distinctions are documented and testable. |
| CLI-008 | P0 | Separate result data, diagnostics, and progress. | JSON stdout remains parseable when warnings/errors occur; diagnostics/progress use stderr; binary stdout contains only bytes when explicitly requested. |
| CLI-009 | P0 | Provide stable schemas, issue codes, and exit meanings. | Output validates against its named schema version; scripts can distinguish full success, invalid invocation, total failure, partial failure, stale plans, and cancellation without parsing prose. |
| CLI-010 | P0 | Preview media, metadata-target, collection, and backup mutations and require explicit application. | Each such leaf defaults to a no-write preview; `--apply` or `plan apply` is needed for execution; `--dry-run` and `--apply` together fail before any writes. |
| CLI-011 | P0 | Check RAW variant/tag capabilities and destructive consequences before changes. | Preview identifies unsupported fields, XMP mapping, maker-note/preview preservation, lossy conversions, and incomplete privacy coverage; invalid whole requests write nothing; unsupported embedded writes offer a sidecar workflow. |
| CLI-012 | P0 | Preserve recoverability and reject stale/conflicting plans. | Existing-file changes establish a verified recoverable original; valid no-ops do not create backups. Inputs changed since preview fail as stale; publication must satisfy the supported concurrency profile (WS-009). |
| CLI-013 | P1 | Support large input manifests, request files, and persistent request framing. | Inputs with newlines work through JSON manifests or NUL-delimited path lists; request responses carry IDs and cannot bleed state between requests. |
| CLI-014 | P0 | Handle international text and difficult filenames explicitly. | A shared Windows/macOS/Linux fixture set covers non-ASCII and supplementary characters, spaces, leading hyphens, and embedded newlines; `--` ends option parsing. |
| CLI-015 | P1 | Explain RAW/XMP pairing, filters, traversal, precedence, and ordering. | Selection is repeatable under documented pairing, recursion, hidden-file, symlink, duplicate-input, and ordering policies; collection plans show paired RAW/XMP paths; `config show` identifies effective value sources. |
| CLI-016 | P1 | Provide discoverable safety profiles and migration guidance. | Profile help lists exact coverage/limits; compatibility translations show differences and never execute their generated command automatically. |
| CLI-017 | P0 | Provide an accessible plain terminal experience. | Commands function without color and in a narrow terminal; help does not require mouse input; progress can be disabled; menu actions have text equivalents. |

## Shared options and semantics

| Area | Proposed options | Contract |
| --- | --- | --- |
| Help/discovery | `help`, `--help`, `--version` | No operation side effects; `help` before inputs is reserved syntax; literal filenames named `help` use `--`. |
| Interaction | `--interactive`, `--no-interactive` | Explicit opt-in, terminal-only; no implicit prompt on an invalid automated command. |
| Presentation | `--output text\|table\|json\|jsonl\|csv\|xml`, `--color auto\|always\|never`, `--no-pager`, `--quiet`, `--no-progress` | Unsupported output formats fail clearly for that operation; structured output overrides presentation decoration. |
| Selection | repeated `--tag`, `--exclude-tag`, `--group`, `--recursive`, `--include-hidden`, `--follow-symlinks`, `--where`, `--with-sidecars` | RAW/XMP pairing is explicit; canonical identity is preserved; expressions have a documented safe grammar, never implicit shell execution. |
| Input | `--files-from <manifest>`, `--files-from0 <path-list>`, `--request-file <document>`, `--` | Define formats explicitly; never split newline-containing paths heuristically. |
| Read representation | `--values raw\|normalized\|display\|all`, `--unknown`, `--embedded`, `--max-depth` | Original precision and provenance remain accessible; fast/partial modes state omissions. |
| Mutation | `--dry-run`, `--apply`, `--save-plan <path>`, `--backup-dir <path>`, `--no-backup`, `--on-error stop\|continue`, `--target embedded\|sidecar`, `--sidecar-dir <path>` | Preview default; RAW embedded writes require per-variant capability; sidecar targeting is explicit; `--no-backup` cannot be inherited; continue is explicit. |
| Identity/config | `--config <path>`, `--profile <name>`, `--schema-version <version>` | CLI > environment > named profile > user configuration > built-in defaults; output can report effective provenance. |
| Boundaries | `--jobs <count>`, `--timeout <duration>`, `--max-bytes <size>` | Bounded resource use; no parallel writes to one physical file; failures have stable issue codes. |

Use understandable string assignment for simple tags, for example `--set XMP-xmp:Label=Reviewed` in an associated sidecar. Complex typed values use `--values-file <JSON-document>` or a separately documented `--set-json` form. Setting an empty string, deleting a tag, and omitting a value are distinct operations. Lists have explicit replace/append/remove operations. Structures have explicit merge/replace policies. Parsing must not silently infer dates, booleans, or numbers from a user's intended string.

Preview/application rules cover changes to media, metadata destinations such as sidecars, collection paths/timestamps, and backup restoration/pruning. Read-oriented reports and binary extraction may create a new explicitly named output artifact immediately, refusing existing targets by default; they also support `--dry-run`. Configuration updates use their explicit `config set/reset` action and show effective values afterward. These distinctions appear in each command's help.

Unknown/write-only/read-only tags, ambiguous aliases, and RAW-variant restrictions are resolved before application. A direct RAW target means embedded metadata only when that exact operation is supported; there is no silent fallback to a new sidecar. Users can explicitly choose `--target sidecar`, see the associated path and mappings, and keep RAW originals untouched. Friendly names remain searchable, with canonical group-qualified names available to experts and scripts.

## Guided menu behavior

The menu starts with actions such as Inspect RAW metadata, Edit associated XMP, Edit supported RAW metadata, Organize RAW collection, Privacy, and Explore RAW support. Each step shows the breadcrumb, short purpose, help, required fields, and a way back. File selection previews the RAW/XMP pairing; tag selection shows units/type/writability for the actual variants. Large collections show a count and expandable examples.

Final review shows the command/request, affected files, before/after values, backups, skipped/unsupported fields, and warnings. The default highlighted action is Preview. Apply is a distinct explicit action; cancelling this review makes no target changes. Cancellation after application starts can leave committed units or require recovery, as WS-016 specifies. Users can save the plan or export the exact command/request to repeat later. No privacy-sensitive metadata values enter persistent history unless the user explicitly enables it.

With redirected streams, requests fail or run in documented batch mode. Interactivity configured in a profile is suppressed whenever stdin or stdout is not a terminal. A broken stdout pipe terminates streaming cleanly; it cannot trigger a menu fallback.

## Workflow examples

All examples below illustrate the proposed contract. Relative filenames are example inputs. Use `--values-file` and `--request-file` for complex values to avoid shell-specific escaping. The documentation will supply separate quoting examples for PowerShell and POSIX shells.

Inspect a RAW file and discover a tag without knowing its storage details:

```text
imageinfo help
imageinfo metadata read help
imageinfo metadata read --values all --output json photo.cr3
imageinfo tags search copyright
imageinfo tags show EXIF:Copyright
imageinfo formats show CR3
imageinfo formats list
```

Preview an edit to an existing associated XMP sidecar, save a plan, review it, then explicitly apply it:

```text
imageinfo metadata write --set XMP-xmp:Label=Reviewed --save-plan label.plan.json photo.xmp
imageinfo plan show label.plan.json
imageinfo validate plan label.plan.json
imageinfo plan apply label.plan.json
imageinfo backup list photo.xmp
```

The first command leaves media and metadata targets unchanged and writes the requested plan artifact. Applying a saved plan checks the original sidecar identity and required permissions again; `photo.cr3` stays untouched. A direct `metadata write ... --apply` is also explicit application; a saved plan is optional. Embedded RAW edits use the same process but remain disabled until that exact RAW-variant/tag operation has preservation evidence.

Compare two RAW files and copy a tag to an existing associated XMP sidecar with an explicit mapping:

```text
imageinfo metadata diff original.cr3 edited.cr3 --output json
imageinfo metadata copy --from original.cr3 --tag EXIF:Copyright --mapping xmp edited.xmp
imageinfo metadata copy --from original.cr3 --tag EXIF:Copyright --mapping xmp --apply edited.xmp
```

Inspect a RAW timestamp, preview a correction in its existing XMP sidecar, then plan geotagging a RAW collection into associated sidecars:

```text
imageinfo time inspect photo.cr3
imageinfo time shift --tag XMP-exif:DateTimeOriginal --by=-1h photo.xmp
imageinfo geo tag --track walk.gpx --time-tag EXIF:DateTimeOriginal --assume-timezone America/New_York --target sidecar --sidecar-dir xmp --save-plan geo.plan.json raw-photos
imageinfo plan apply geo.plan.json
```

The timezone assumption and RAW/XMP destination mapping are visible in the plan. The GPX file is auxiliary workflow input, not an additional supported media family. Ambiguous/missing local-time information produces a diagnostic; choosing a zone must not silently overwrite an existing explicit offset. Calendar shifts and elapsed-duration shifts have separate documented meanings.

Create a sidecar, extract a preview, and plan an organized destination:

```text
imageinfo sidecar create --format xmp --to photo.xmp raw-photo.cr3
imageinfo binary list raw-photo.cr3
imageinfo binary extract --tag PreviewImage --output-file extracted-preview.jpg raw-photo.cr3
imageinfo files rename --with-sidecars --template '{capture-date:yyyyMMdd-HHmmss}-{sequence}.{extension}' --save-plan rename.plan.json raw-photos
```

Sidecar creation is also a mutation: its default is preview, and `--apply` is needed to create the output. Binary extraction copies a pre-existing embedded asset; it does not develop/render a RAW image or promise JPEG input support. It refuses an existing output by default and leaves the RAW source unchanged. `--tag PreviewImage` must be qualified if multiple matching instances are present. Rename plans show both RAW and paired-XMP destinations and refuse ambiguous pairings.

Inspect and remove a declared privacy category, then verify what remains:

```text
imageinfo privacy inspect --profile location --with-sidecars public-photo.cr3
imageinfo privacy scrub --profile location --target sidecar --save-plan privacy.plan.json public-photo.cr3
imageinfo plan apply privacy.plan.json
imageinfo privacy verify --profile location --with-sidecars public-photo.cr3 --output json
```

This example only changes the associated XMP. Verification still checks the RAW file and reports any location information left in it or its embedded previews. “Verified” means the named profile's supported checks passed; it cannot certify anonymization if targeted information remains, any relevant region is uninspectable, or the RAW variant lacks safe deletion support.

Produce scriptable output without terminal interaction:

```text
imageinfo metadata read --files-from collection.files.json --output jsonl --no-interactive --no-progress
imageinfo metadata export --format csv --output-file inventory.csv --recursive raw-collection
imageinfo compat translate --request-file legacy-command.json
imageinfo interactive metadata write
```

Export-to-file operations report their output path; refusing to overwrite remains the default. Compatibility translation describes differences and produces a reviewable suggestion. It must not automatically run that suggestion.

## Structured result contract

The proposed request/file envelope must carry snapshots conforming to the
[metadata boundary contract](metadata-model/README.md). Its
[synthetic snapshot](metadata-model/examples/snapshot.synthetic.json) is the concrete
payload example. It replaces the earlier flat illustrative tag record, which did
not represent the required identity, provenance, and value states completely.

The envelope adds request IDs, operation, per-file outcomes, and summary counts.
It must not flatten the snapshot into a single object keyed by tag name. JSONL can
emit per-file snapshot payloads with the same model revision; schema versions for
the envelope and metadata model are independently named. Exact field placement in
the envelope remains part of the CLI walkthrough work.

A requested output view may omit unavailable/unrequested data only with explicit
coverage and value states. Large binary values remain bounded references unless
an explicit self-contained export is requested. Display text is never the default
copy/import representation. See MDL-010 through MDL-019 for precision, absence,
selection, export, and edit-intent rules.

JSON Lines emits typed request/file/summary records with the same schema identity, including a final summary where output completes. Partial output after cancellation is documented. Errors are typed issues with stable `code`, `severity`, `path`, `tag` where applicable, and `message`; user-facing wording may improve without changing issue codes. In JSON mode, preflight failure still produces a valid result envelope on stdout; human diagnostics remain on stderr.

## Proposed exit status contract

| Status | Meaning |
| --- | --- |
| 0 | Requested work completed successfully, including a valid preview or help; deliberate filter exclusions are counted separately |
| 1 | Operation failed and no requested item succeeded |
| 2 | Invalid syntax, missing required input, configuration error, or a request that fails whole-request preflight |
| 3 | Partial failure: some items succeeded and others failed or were unsupported under explicit continue policy |
| 4 | Plan could not be applied because an input changed or a write conflict was detected |
| 5 | Post-publication verification/durability failed or recovery remains uncertain; results describe observed changes and recovery artifacts |
| 130 | User cancellation/interruption; prior completed file results are reported where possible |

Warnings alone do not change exit status unless `--warnings-as-errors` is enabled. Unsupported RAW or explicitly supplied out-of-scope media input is a failure by default, never a silent success. No-files-selected is an explicit result and fails unless the user opted into `--allow-empty`. Exit values are imageinfo proposals; any later RAW-specific compatibility mode must document its limited contract separately.

## Mutation/application contract

The [safe mutation and recovery contract](write-safety/README.md), WS-001 through
WS-024, defines the detailed proposal. Its storage profiles remain unverified.
`--no-backup` discards temporary recovery material only after successful
finalization; it never disables recovery during a write. Valid no-ops do not
rewrite files. Real content changes update filesystem mtime by default; preserving
it is explicit. Capture dates do not change unless the plan calls for it.

A final content check and rename alone do not exclude unrelated writers. Refuse
replacement where its required guards cannot be established; never silently switch
to another target or a weaker overwrite policy. See the linked platform constraints.

Preflight parses the complete request, validates target paths/capabilities/values, resolves mappings, checks collisions and protected structures, then produces a plan. Saved plans include schema version, operation sequence, original content identity, proposed changes, destination paths, and backup policy. They contain no automatically executable shell commands. Any mutable source supplying copied metadata is also fingerprinted.

Plans are not a claim of all-or-nothing transaction across a directory. Each file has an explicit outcome. Default application stops at the first runtime failure; earlier completed edits remain recoverable. `--on-error continue` is explicit and reports partial failure. Files with multiple ordered changes are rewritten as one planned unit where the format permits.

Backup creation and replacement must succeed before the original is considered safely updated. Write verification rereads changed tags and validates preservation constraints. A verification failure does not claim successful completion; the result names the backup and current-file state. Backup restoration is itself planned and checks destination identity. Backup pruning requires explicit selection and application, and never removes media originals based on a wildcard surprise.

Unknown RAW metadata blocks, decoding-critical make/model and maker notes, embedded previews, read-only files, symlinks, hardlinks, and RAW/XMP pairing require documented variant/platform policies. Do not infer safety solely from a writable directory. Any detectable signed/provenance-bearing RAW structure must have an explicit preservation/impact policy before writing is enabled. Sensor payloads are protected throughout every metadata-only operation.

## Remaining specification decisions

Use the proposed metadata and write-safety contracts in #0003 walkthroughs. Specify exact RAW/XMP pairing/discovery and mapping choices, expression grammar, plan/result serialization, recovery commands, output-format support, and mixed-error exit precedence. Exercise cancellation and partial outcomes without changing their safety guarantees. Tag-level write evidence and storage profiles remain future work. RAW-focused compatibility guidance is separate from eventual full ExifTool parity. Decide aliases only after testing the canonical tree with users. CLI experiments can be mockups or specifications; they do not require selecting an implementation language.

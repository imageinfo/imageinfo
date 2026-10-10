# Research sources and baseline

Observation date: **2026-10-10**. This ledger records primary sources for the initial
requirements investigation. It is not an assertion of completed compatibility.
The research covers ExifTool broadly because full parity remains the eventual goal.
Current imageinfo delivery requirements are limited to [camera RAW](raw-scope.md).

## Reproducible upstream snapshot

The official GitHub API returned this `exiftool/exiftool` master revision during
the investigation:

- Commit: [`2200871d9cef988051d2a99d67df3bda6cbb30a8`](https://github.com/exiftool/exiftool/commit/2200871d9cef988051d2a99d67df3bda6cbb30a8)
- Commit timestamp: `2026-05-27T16:44:48Z`
- Commit subject: `Update to 13.59`
- Source version observed: **13.59**

This identifies the inspected source snapshot. It does **not** establish the newest
downloadable release as of October 10. Direct requests to exiftool.org returned
HTTP 403 in this research environment, so the project's official GitHub source
and bundled documentation were used. A later compatibility harness must choose an
actual executable distribution, record its hash and runtime options, and verify
its reported version before recording results.

## Primary reference map

| Source | What to use it for |
| --- | --- |
| [Official repository](https://github.com/exiftool/exiftool) | Upstream identity and source history. |
| [Pinned README](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/README) | Format summary, dependencies, distribution layout, copyright/license statement. |
| [Feature overview](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html) | Features and file-level read/write/create support. |
| [CLI manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html) | Selection, copying, output, write modes, argument files, conditionals, process protocol. |
| [API manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/ExifTool.html) | Options, tag identity, groups, raw/converted values, library behavior. |
| [Tag index](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/index.html) | Metadata families; entry point to per-format and per-tag constraints. |
| [FAQ](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/faq.html) | Duplicate tags, writing ambiguity, encoding, dates, and other user-facing traps. |
| [Structured XMP](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html) | Structures, arrays, flattened views, and copy semantics. |
| [Sidecars](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/metafiles.html) | Import/export and source-to-sidecar mapping. |
| [File naming](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/filename.html) | Filename/directory pseudo-tags, patterns, and collision handling. |
| [Geotagging](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geotag.html) | Track formats, interpolation, timestamp matching, and clock correction. |
| [Geolocation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geolocation.html) | Geographic lookup; distinct from matching GPS tracks. |
| [Upstream tests](https://github.com/exiftool/exiftool/tree/2200871d9cef988051d2a99d67df3bda6cbb30a8/t) | Test organization and evidence to investigate; fixture redistribution requires provenance review. |
| [Changes](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/Changes) | Behavior changes and possible regression cases. |
| [AWS CLI help](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-help.html) | Help at root, service, and operation scopes. |
| [AWS CLI auto-prompt](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-parameters-prompting.html) | Interactive discovery as a distinct feature from nested help. |

The topic documents contain more specific citations. ExifTool source material remains
attributed to its authors; this repository records independent requirements and
analysis, rather than importing its implementation or redistributing its fixtures.

## What this investigation establishes

The review covers the main command and API contracts, representative container and
tag families, high-risk metadata mutations, and the workflows that shape a replacement.
It establishes the scope of a compatibility program and an initial RAW-focused product
contract. Non-RAW findings are a reference for later expansion, not current work.

It is **not** a tag-by-tag audit, a benchmark, a source security audit, or a successful
run of a differential test suite. Format counts and tag counts are deliberately not
used as completion metrics. A future inventory must distinguish file recognition,
readability, writability, creatability, deletability, and preservation.

## Maintaining the research

1. Record an immutable upstream source revision and the artifact version/hash used
   for each actual experiment.
2. Record environment, configuration, optional dependencies, command arguments,
   fixture provenance, and expected behavior alongside each result.
3. Compare upstream changes against the feature inventory; investigate additions and
   corrections without silently rewriting old expected results.
4. Keep observed behavior, documented behavior, and imageinfo's proposed behavior
   separately labeled, especially when they disagree.

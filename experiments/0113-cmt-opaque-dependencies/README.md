# Authored opaque CMT dependencies

#0113 measures a pinned reference date rewrite on wholly authored small CMT2
fixtures. The independent observer separates stored-byte relationships from
explicitly invented dependencies. No camera media, production writer, decoder or
storage profile participates. See the
[method and limits](../../docs/write-safety/cmt-opaque-dependencies.md).

```text
python -m unittest discover -s experiments/0113-cmt-opaque-dependencies -p "test_*.py" -v
python scripts/check_docs.py
git diff --check
```

The declared matrix has two TIFF byte orders, same/changed invented date
assignments, and five shapes: known-only baseline, opaque inline value, opaque
out-of-line value, exact date-allocation alias and invented date checksum.
There is no external media-input option and no padding-mode sweep.

```text
python experiments/0113-cmt-opaque-dependencies/runner.py --root FRESH_PRIVATE_ROOT
python experiments/0113-cmt-opaque-dependencies/audit.py --root FROZEN_PRIVATE_ROOT --output FRESH_PRIVATE_AUDIT_JSON
```

The runner verifies the existing pinned tool/runtime closure before and after
execution. It archives all package Python sources and the complete matrix before
commands. Fresh captures retain the restricted environment, exact commands,
complete stdout/stderr, failures/partial outputs, bytes/hash/mtime bindings and
capture manifest. Each input is at most 64 KiB; each command has a 120-second bound.
Configuration is disabled and only ExifIFD DateTimeOriginal is assigned.

`audit.py` does not import the fixture generator. Its TIFF witness retains logical
entry identities and shared physical storage. Dependency consistency and byte
preservation are separate results: an unchanged invented checksum can become
stale, and equal logical values need not continue sharing a physical allocation.
The public report contains authored observations only.

The retained [authored results](authored-results.json) cover twenty actual
derivatives with independent byte checks. Opaque stored values survive; all exact
date aliases split into separate storage; changed-date assignments leave the
invented checksum stale. These are finite authored observations, not camera
dependency proof. Twenty-two local tests cover capture handling and independent
ownership/dependency challenges. A separately retained sandbox launch-failure
attempt precedes the final frozen capture.

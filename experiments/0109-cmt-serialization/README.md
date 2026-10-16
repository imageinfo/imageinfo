# Authored CMT reference serialization

#0109 tests the pinned reference serializer using independently authored small
BMFF/CMT controls. No camera bytes, inferred camera constants, media decoder,
production writer or storage profile participate. See the
[method and limits](../../docs/write-safety/authored-cmt-serialization.md).

```text
python -m unittest discover -s experiments/0109-cmt-serialization -p "test_*.py" -v
python scripts/check_docs.py
git diff --check
```

The finite matrix is two TIFF byte orders, four companion storage shapes,
same/changed authored date assignments and default/explicit QuickTimePad modes.
Every input is constructed in the runner; there is no external media-input flag.
The complete 32-cell plan is saved before commands run. A fresh run directory
holds archived source, exact tool/runtime closure, commands, complete captures,
inputs, derivatives, failures, per-cell records and a final file manifest.

The runtime must already match the reviewed local manifests. Configuration is
disabled and each command has a 120-second timeout. An operator supplies a fresh
private output path; local paths and runtime details stay in that private capture.

```text
python experiments/0109-cmt-serialization/runner.py --root FRESH_PRIVATE_ROOT
python experiments/0109-cmt-serialization/audit.py --root FROZEN_PRIVATE_ROOT --output FRESH_PRIVATE_AUDIT_JSON
```

`audit.py` independently parses actual input/output bytes, including TIFF
ownership, entries and complete value bytes, box extents and unallocated storage.
Its literal controls challenge malformed extents, aliasing, missing storage and
zero padding masquerading as preserved nonzero data. It does not import the
fixture generator. Public results contain authored observations only.

The retained [authored results](authored-results.json) record 32 successful
independent byte checks from the frozen source set. A setup attempt and an earlier
successful viability pilot remain separately retained privately; neither is the
final qualification capture. Eighteen package tests cover runner failure/capture
handling and independent literal/adversarial observer challenges.

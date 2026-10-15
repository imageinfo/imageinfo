# Same-value CR3 reference control

#0105 measures one original-value assignment using the exact frozen #0099
source/tool/grant cohort and existing #0102 attribution. It never repeats the
changed-date write. See [the method](../../docs/write-safety/same-value-control.md).

Camera-derived values, hashes, counts, Boolean outcomes, classifications and
inventories remain private because the bound grants deny report publication.
Public material contains only this method and authored marker controls.

```text
python -m unittest discover -s experiments/0105-same-value-control -p "test_*.py" -v
python scripts/check_docs.py
git diff --check
```

The operator creates a fresh owner-only empty private directory and supplies the
retained Windows source guard. The runner checks complete frozen capture hashes,
original admission/grants, pinned tool closures and exact #0099/#0102 driver
sources. It reproduces the retained attribution before invoking a writer.

```text
python experiments/0105-same-value-control/control_private.py --prior FROZEN_PRIVATE_0099_ROOT --attribution FROZEN_PRIVATE_0102_ROOT --root FRESH_PRIVATE_0105_ROOT --guard RETAINED_SOURCE_GUARD
```

Only the original unique ExifIFD DateTimeOriginal assignment is sent to the pinned
reference tool, with configuration disabled and a fresh output name. The runner
retains commands/captures, failures, incomplete/no-artifact outcomes, derivative
provenance, source fingerprints, complete byte summaries, three-way attribution,
metadata deltas and the existing independent LibRaw unpack comparison. It never
widens assignments to manufacture a rewrite or overwrites prior evidence.

The independent auditor verifies the actual private ledger separately. A no-op or
shared rewrite does not establish semantic independence, necessity, a production
format/storage profile or permission to apply dates to RAW sources.

## Read-only classification and audit

The immutable media capture retains its exact write-driver source. A later
classification correction uses a separate fresh root and explicitly binds that
historical write revision to the final analysis revision. It changes only
`cellClassification`; all original metadata, byte-accounting, decoder and command
evidence remains unchanged. Missing/added relationships always stay unexplained,
including cases where both outputs lack the same source role.

```text
python experiments/0105-same-value-control/reclassify_private.py --control FROZEN_PRIVATE_0105_ROOT --root FRESH_PRIVATE_RECLASSIFICATION_ROOT
python experiments/0105-same-value-control/audit_private.py --root FROZEN_PRIVATE_0105_ROOT --reclassification FROZEN_PRIVATE_RECLASSIFICATION_ROOT --output FRESH_PRIVATE_AUDIT_FILE
```

For captures made directly with the final classifier, omit `--reclassification`.
The reclassifier executes no reference writer, metadata reader or decoder. It
checks captured report names against the frozen manifest and binds each artifact
path to its admitted source or fresh derivative lineage before writing reports.
All previous attempts and immutable manifests remain retained privately.

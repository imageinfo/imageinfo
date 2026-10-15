# Frozen CR3 rewrite attribution

#0102 advances the format prerequisite of #0078 using the already retained #0099
artifacts. It performs **read-only analysis**: no new camera output, reference
write, decoder invocation, production writer or storage profile is introduced.

See [the method and limits](../../docs/write-safety/cr3-rewrite-attribution.md).
All camera-derived findings, including counts, Boolean conclusions, allocation
inventories, pointer relationships and residual intervals, remain private under
the source grants. Public files contain authored controls and the method only.

## Public checks

```text
python -m unittest discover -s experiments/0102-cr3-rewrite-attribution -p "test_*.py" -v
python scripts/check_docs.py
git diff --check
```

The implementation controls construct marker-only CMT/track/CTBO files. They cover
exact field identity rather than payload matching, duplicate tag ordinals, both
TIFF byte orders, complete disjoint byte accounting, zero/nonzero unallocated
bytes, sample reference/offset limits, missing/ambiguous date shapes, aliases,
malformed directories and unsupported widths. The independent audit has separate
authored controls and a separately implemented reader. No control asserts a valid
RAW sensor sample or real camera provenance.

## Private analysis

The supervisor supplies the frozen #0099 root, its independently reviewed source
admission chain and a fresh owner-only private analysis directory. The source
manifest is loaded from the #0099 recorded path and must match its recorded hash;
the directory is not an arbitrary current copy of that manifest.

```text
python experiments/0102-cr3-rewrite-attribution/attribute_private.py --prior FROZEN_PRIVATE_0099_ROOT --root FRESH_PRIVATE_ANALYSIS_ROOT
```

The driver binds every source ID/hash to the frozen grant and checks all retained
#0099 file hashes. Source content/mtime must remain unchanged across analysis.
The new root retains a scoped review, exact driver source, native/reference
allocation/interval/pointer reports, an index and a complete hash manifest. No
public output option exists. Partial/error analysis is retained and must not be
reported as a complete denominator.

Independent verification reads the original bytes and reports without importing
the attributor. Its actual findings and audit report remain private. A final
private handoff identifies the retained paths; publishing this method grants no
access to those records and no production apply authority.

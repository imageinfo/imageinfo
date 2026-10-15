# Private CR3 reference-write effects characterization

#0099 advances the independent format prerequisite of #0078. It characterizes an
actual pinned reference **write**, rather than reading a native candidate and
treating that as an independent writer comparison. This is research tooling;
there is no production writer, admission change or storage profile.

[The method and disclosure boundary](../../docs/write-safety/cr3-reference-effects.md)
describe the exact question and private audit. Public files contain the method and
independently authored structural controls only. Camera-derived outcomes, including
counts, Boolean conclusions, dependency inventories and aggregate reports, must
remain private under the actual `publishReports: denied` grant.

## Public checks

```text
python -m unittest discover -s experiments/0099-cr3-reference-effects -p test_controls.py -v
python scripts/check_docs.py
git diff --check
```

The twelve standard-library tests exercise independently authored little/big-endian
CMT markers, allocation/structure overlap and ambiguity refusals, exact changed
run accounting across buffer boundaries, a deliberately added `mdat` effect,
malformed/cyclic structures, reference JSON duplicate rejection and metadata/file/
derived effect classification, complete streamed run digests with bounded samples,
relocation-aware complete byte partitions, and pinned distribution-component mutation. The
marker `mdat` is not RAW sensor data. Passing
these controls is not camera qualification, checksum closure or writer admission.

## Private execution

Execution requires authorized private fixture, provenance, tool and baseline
unpack records. It is not runnable from the public repository alone. The caller
must create a fresh empty private directory, apply owner-only inherited access
before any private record/output is created, and supply the previously reviewed
Windows source-share guard executable. The driver never changes source ACLs.

```text
python experiments/0099-cr3-reference-effects/qualify_private.py --manifest PRIVATE_ADMISSION_MANIFEST --root FRESH_PRIVATE_ROOT --guard REVIEWED_SOURCE_GUARD
```

There is deliberately no `--public` option. The final stdout message only points
the operator to their selected private root; it prints no camera-derived result.
The root retains scoped grants, tool/driver identities, controlled environment,
exact argv/captures, original and candidate allocation inventories, byte-run and
decoded metadata comparisons, independent unpacks and a complete hash manifest.
Existing source/decoded/candidate data are never overwritten or automatically
cleaned. A partial/error run remains retained and is not a successful qualification.

The trusted supervisor must review the private `summary.private.json`,
`results.private.json`, `runs.private.json`, `scoped-review.private.json` and
`capture-manifest.private.json` together. No record imports authority into the
production program. Restart/recovery/prune is outside this tool.

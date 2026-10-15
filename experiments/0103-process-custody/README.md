# Process-owned marker custody runtime

Card **#0103**, observed **2026-10-15**. Read the
[runtime contract and limits](../../docs/write-safety/process-custody.md).

`runtime.py` supplies one reusable trusted-caller API, `ProcessCustody`, around
the unchanged frozen F869 marker worker. It captures context from its actual
child process, withholds publication, saves caller history, confirms that exact
child's exit before release, and permits one existing guarded unpublished prune.
Alternatively it completes a release-fence save before continuing publication.
It accepts no imported context or existing supervisor root as authority.

The fixed worker SHA-256 is
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`.
A current CI build with different bytes is refused. No checksum override is
provided. The runtime reuses #0049's checked 655,360-byte per-operation admission
charge; it adds no SDK call, Rust dependency, source-media mutation or OS policy.

Run the portable synthetic transport/control tests:

```console
python -W error experiments/0103-process-custody/test_runtime.py
python -m py_compile experiments/0103-process-custody/runtime.py experiments/0103-process-custody/test_runtime.py experiments/0103-process-custody/qualify.py experiments/0103-process-custody/audit.py
```

The six portable tests exercise actual Python child-process transport with authored
protocol data and failures. They are not Windows/native publication qualification.
The separate native qualifier/auditor uses only the exact frozen worker and fresh
authored marker roots; all raw captures and artifacts remain private and retained.

```console
python experiments/0103-process-custody/qualify.py --binary .local/0047-build/release/imageinfo-windows-publication-probe.exe --root .local/process-custody-qualification
python experiments/0103-process-custody/audit.py --root .local/process-custody-qualification --output .local/process-custody-audit.private.json
```

Use a fresh `--root` and `--output` for every run; the auditor creates its output
exclusively. The published sanitized ledger comes from the retained independently
audited native run. Follow the qualifier's exact argument help if
retaining independent capture roots. No actual native pass is inferred from a
portable test or a different executable.

This is process-local caller orchestration, not automatic durable custody, an
importer, general repair, namespace/receipt qualification, RAW admission or a
production writer. Power testing remains subject to the accepted VM-off ceiling;
this child runs no VM or OS fault campaign.

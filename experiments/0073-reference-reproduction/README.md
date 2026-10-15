# Pinned reference in a second environment

Research tooling for **#0073**. This replays existing admitted private reference
operations in native Linux using an installed Perl interpreter and the original
ExifTool 13.59 source and API observer. It neither imports upstream media nor
changes imageinfo production dependencies.

Read [the method and disclosure boundary](../../docs/corpus-baseline/second-environment.md)
before running. Only authorized maintainers with the private baseline can perform
the exact replay. Keep every generated file under the ignored `.local` directory.

```console
python3 experiments/0073-reference-reproduction/reproduce.py --repository REPOSITORY --output REPOSITORY/.local/NEW_PRIVATE_RUN
python3 experiments/0073-reference-reproduction/audit.py --ledger REPOSITORY/.local/NEW_PRIVATE_RUN/ledger.private.json --output REPOSITORY/.local/NEW_PRIVATE_RUN/audit.private.json
python -m unittest discover -s experiments/0073-reference-reproduction -p 'test_*.py'
```

The audit independently checks invocation accounting, captured hashes, input and
component preservation and strict comparisons. Its report is private. Authored
tests exercise comparison behavior without camera-derived data. The comparison
policy excludes no observations, so environment-specific values remain visible as
differences. Neither a match nor a difference is independent media validation or
a general cross-platform compatibility finding.

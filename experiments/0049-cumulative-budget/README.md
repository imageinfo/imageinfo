# Finite cumulative marker budget

Card **#0049**, observed **2026-10-15**. Read the
[implemented contract and limits](../../docs/write-safety/cumulative-budget.md).

`supervisor.py` is an importable trusted-caller research supervisor around the
unchanged #0032 receipt/custody worker. Each operation prepays a monotonic
655,360-byte logical admission charge and one finite operation slot before any
operation construction. All outcomes retain that charge. There is no deletion,
refund, restart adoption or recovery API.

`qualify.py` runs 15 checked-arithmetic, admission, native integration and retention
cells. Actual marker sources, candidates, four transaction records and four custody
snapshots use the frozen worker; no Rust/SDK boundary is added or changed.

```console
python experiments/0049-cumulative-budget/qualify.py --binary .local/0047-build/release/imageinfo-windows-publication-probe.exe --parent .local/0049-cumulative-budget --public docs/write-safety/cumulative-budget-native.json
```

All scratch is retained under the ignored parent. The public evidence contains
aggregate observations and executable/source hashes. This is logical byte admission,
not free-space reservation, physical allocation quota or a persistent global budget.
No production profile, automatic custody/recovery or RAW admission is enabled.

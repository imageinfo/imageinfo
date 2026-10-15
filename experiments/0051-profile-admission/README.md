# Exact profile refusal ledger/model

Card **#0051**, observed **2026-10-15**. Read the
[contract, supported inputs and refusal boundaries](../../docs/write-safety/profile-admission.md).

`admission.py` inspects the fixed actual-observation ledger and bound public evidence.
All actual results refuse before target effects. It has no worker or target mutation
API. Explicit hypothetical Boolean premises are consumed only by a separate pure
test conjunction; logical satisfaction enables no actual profile.

`build_ledger.py` authors the twelve required cells and all 24 WS/16 SAF traces.
`qualify.py` checks 206 refusal/structure/configuration/trace cases and all 4,096
hypothetical truth-table rows. Its authored witness remains retained privately.

```console
python experiments/0051-profile-admission/build_ledger.py
python experiments/0051-profile-admission/qualify.py --public docs/write-safety/profile-admission-model.json
```

Current output is a read-only documentation/model handoff, not backend/profile,
RAW/XMP publication, automatic custody/recovery, restore or prune enablement.

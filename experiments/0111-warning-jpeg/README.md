# Warning-aware authored JPEG qualification

#0111 research only. [Method and limits](../../docs/fixture-plan/warning-aware-jpeg-validator.md)
describe the exact installed TurboJPEG API, profile, seven controls and finite result.
No camera inputs or external image-path argument are supported.

Use the bundled Python executable returned by the workspace dependency tool:

```text
python experiments/0111-warning-jpeg/qualify.py --attempt-root .local/111-fresh-attempt
```

The attempt directory must not exist and its parent must exist. It retains the
frozen profile, bounded child streams/process records, incremental observations
and final report. Keep unsuccessful attempts. The runner never regenerates its
profile; mismatched components/settings/source refuse. Compare the final report
with `observations.json`. Follow the separate audit script's help for independent
replay and harness checks. No dependency installation or root Cargo change is needed.

```text
python experiments/0111-warning-jpeg/audit_qualification.py --candidate-attempt-root .local/111-fresh-audit --output .local/111-audit.json
```

The independent audit reconstructs the seven authored extents, uses a separate
native binding in fresh children, compares the curated observations, and checks
wrapper bounds, stuffing-aware traversal and changed settings/components. Four
separate harness injections exercise actual stdout/stderr overflow, deadline
expiry and nonzero exit. Their bounded streams/process records stay in the fresh
audit directory. [Curated audit observations](audit-observations.json) record the
finite results and exact candidate/profile/audit source hashes. Native decoding
of progressive/nonzero suffix controls succeeds, so wrapper refusal remains an
explicit syntax/extent decision rather than a native entropy-error claim.

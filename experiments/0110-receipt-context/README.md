# #0110 checked receipt context

Standalone authored-marker research around the separate
`ordinary-receipt-checked-flush` mode in the existing Windows research worker.
See [the boundary contract](../../docs/write-safety/checked-receipt-context.md).

On Windows, run the eleven native controls with a newly built candidate and the
retained frozen F869 inspector:

```text
python experiments/0110-receipt-context/qualify.py --binary CANDIDATE --inspector FROZEN_F869 --output NEW_PRIVATE_DIRECTORY
```

The collector retains complete process events, control lines, exits, actual
contexts, inventories, source bindings and harness bytes. `audit.py` independently
checks retained artifacts; `test_audit.py` supplies authored negative controls.
`audit_completion.py` independently verifies the explicitly assisted sign-in and
final Windows host continuity after the frozen core audit. `current_audit.py`
checks current-worker/current-inspector CI regressions with their narrower label.
Passing the current candidate as inspector is useful as a CI regression only and
must not be described as frozen-inspector qualification.

Public authored results are [eleven native cells](native-result.json) and
[two guest cells](guest-result.json). The latter preserves reproduced pre-context
receipt last-write drift and a matching checked-context inspection as distinct
finite observations. One first-postfault sign-in was assisted before any reader
job was queued; no actor, fault or read-only job was retried.

`guest.py` is WSL-only orchestration for exactly two VM-offs in one fresh private
overlay. Its `prepare`, `serve` and `run` commands require explicit scoped paths.
The actor, F869 inspector and separate existing #0106 observer are distinct
payloads. `console.py --bootstrap` is used once before measurement to replace the
retained legacy agent; later sign-ins use login only and never replace an agent
while jobs are queued. Readiness includes a challenge serviced by the exact
hash-bound agent instance after all payload downloads.

No tool enables a storage profile, production publication, repair, automatic
custody or RAW mutation. No old guest matrix is replayed. Final normal shutdown
and owned-helper stop proofs remain part of the private evidence.

# Optional retain-and-install policy

Terry approved this separately named optional direction on 2026-10-19. It does
not satisfy or replace the strict existing-target replacement and immutable
original-snapshot requirements tracked by #0194 and #0198.

The operation first moves the actual expected old object to a fresh retained
name. It then installs the held candidate only if the target name is still
absent. The target can be absent between those steps. A later foreign winner is
preserved; the retained old object and staged candidate remain available, with
an explicit partial or uncertain outcome. There is no automatic rollback,
retry, winner deletion or restoration.

The retained original is the actual old object, with its properties and any
permitted actor edits still attached. It is owner-editable after release, not an
immutable point-in-time backup. Candidate properties must be explicitly planned;
cloning the old object's owner, ACL or streams is unsupported. The initial mode
always keeps the old object, including after success.

Initial implementation is bounded authored-marker work in a controlled fresh
Windows private root. Its design needs an explicit held two-object/three-slot
map, retained ancestor guards and the finite guarded continuation policy from
the existing cycle research. Newly vacated names can affect creation time:
distinct baselines and exact post-installation checks must retain mismatches,
never reset timestamps or refresh a baseline to manufacture success. The known
twenty-second wait is finite evidence, not a general tunnel-expiry guarantee.

Only independently qualified backend and format combinations may later execute.
Observed completion is not durable commitment, a qualified receipt, restart
authority, a production storage profile or permission to edit RAW media.
Unsupported platforms refuse; this policy adds no filesystem service, driver,
privilege requirement or pathname/hash-check fallback.

The first two implementation scopes are the actual held operation and a
separate read-only artifact inspector. Restore and grouped callers need their
own sufficient ownership/namespace designs and the completed operation; they
are not immediately executable merely because the policy is approved.

Related evidence: [held existing-object move](held-existing-move.md),
[held marker cycle](held-marker-cycle.md),
[existing-target boundary](existing-target-boundary.md) and
[original retention](original-retention.md).

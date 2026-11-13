# Optional retain-and-install runtime

The selected [retain-and-install policy](retain-install-policy.md) is a
bounded marker operation. Its live session and the read-only diagnostic
inspector are independent consumers of the storage SDK. Neither adds a product
command, admits a storage profile, or grants restart or cleanup authority.

The live session holds the actual old and candidate objects, the fresh private
root and its ancestry. It records the exact three-slot map at each confirmed
prefix: old target with staged candidate; retained old with vacant target; then
retained old with installed candidate. The final move is no-replace, so a later
foreign winner cannot be overwritten. The selected policy waits at least 20
measured seconds with the guards held before reusing the target name, checking
current authority and cancellation. The wait is part of this finite method, not
an assertion about arbitrary directory history or NTFS tunnel expiry.

An attempted call and a confirmed prefix are separate. Cancellation after old
retention is partial. A lost response or contradictory binding stops live work;
the observation does not authorize replay or restoration. The actual old object
remains an ordinary retained object, not an immutable backup. The prior
[immediate-method counterexample](held-marker-cycle.md) remains separate.

The inspector accepts explicit distinct target, retained and staging names and a
bounded diagnostic expectation. It inspects current objects under read guards,
comparing identity before bytes and supported properties. Equal bytes on a
different identity are foreign. A complete matching layout describes current
resemblance only; it does not establish the history, custody, original caller,
durable outcome or permission to act. Missing, unsupported and inaccessible
observations are distinct, and unreadable slots cannot be filled from the
expectation. Other root entries are observed within a bound, never followed.
Properties and absence are sampled at guarded checkpoints; the report is not
one atomic snapshot of the namespace and all properties.

Focused authored controls: `cargo test --locked --lib storage::retain_install`
and `cargo test --locked --lib storage::retain_inspection`. Actual positive
marker outcomes require the Windows native cases; non-Windows refusal and
portable models do not qualify native storage behavior. The inspector makes no
writes; read-induced access-time effects are outside the retained snapshot.

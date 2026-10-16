# Live guarded date candidate (#0186)

The crate-private Windows [candidate module](../../src/sidecar_candidate.rs)
connects explicitly selected actual RAW/XMP files to an in-memory date derivative
or byte-exact no-op. It opens no output, changes no source permissions, publishes
nothing and grants no apply, format, storage-profile or RAW mutation authority.
The received camera pair's separate admission result is unchanged; this scope
uses independently authored structural controls only. It makes no positive
camera derivative or usable-image claim.

## Actual bindings and boundaries

Exactly one explicit destination intent supplies a property ordinal and conflict
policy with named destination fraction/zone loss acknowledgments. Empty or multiple
intents refuse, including repeated same-target intents. There is no saved-plan
format, caller-supplied date/coverage flag, caller-supplied source bytes or imported
prepared-result constructor.

The [pair resolver](pairing.md) supplies an initial advisory path observation.
The actual selected spellings are then independently opened by the existing
[`GuardedSource`](../../crates/imageinfo-windows-storage/src/windows.rs) facade;
canonical paths cannot hide a selected alias or reparse component. Both physical
objects, bytes, names and ordinary ancestors remain held together. Physical
identity comparison refuses aliases, and a second resolver observation must match
the first while both guards are live. The facade's stricter hard-link, stream,
case, path, local-fixed-NTFS and property rules remain unchanged. No second backend,
native API, dependency or unsafe boundary is introduced.

The actual guarded read is capped at **64 MiB RAW** and **65,536 bytes XMP** before
allocation by the shared facade; callers can reduce either bound. Historical
#0104's 256 MiB slice bound does not enlarge this filesystem consumer. Native
reader limits and the adopted [packet profile](packet-profile.md) apply as well.
These are logical bounds, not an allocator quota, deadline or cancellation claim.

One immutable original RAW/XMP snapshot supplies native CMT2 observations and all
mapping/conflict inputs. An earlier derivative is never an overlay. Exact tag,
allocation, structural path and stored text observations are retained, together
with mapping version, selected destination ordinal, previous/mapped strings,
losses, explicit acknowledgments, conflict policy and a SHA-256 candidate content
identity. The hash is a local content comparison, not object or caller authority.
No primitive byte fields can construct the private `Prepared` type.

Both original full byte vectors and the shared original property snapshots stay
retained. Fresh complete byte/identity/name/ancestor/property checks run after
preparation and on explicit `recheck()` boundaries. An observed conflict latches
terminally without accepting reverted properties as a fresh baseline. Guards
continuously exclude incompatible default-stream writers and name replacement;
same-owner properties remain boundary observations under the accepted option A.
Dropping the candidate only releases holds. It deletes or repairs nothing.

## Reviewed promotion boundary

This change promotes independently authored logic from
[#0104](native-date-adapter.md), [#0083](date-mapping.md) and
[#0084](date-preservation.md) into production-owned internal source, subject to
ordinary independent source review before handoff:

| Source | Owned implementation and adaptation |
| --- | --- |
| #0104 native adapter | [adapter.rs](../../src/sidecar_candidate/adapter.rs): actual root reader, exact CMT2 tags, opaque-coverage refusal, same-parent IFD checks; no input metadata or coverage flag |
| #0083 date mapping | [mapping.rs](../../src/sidecar_candidate/mapping.rs): cardinality, calendar/fraction/offset grammar, singleton destination, explicit ordinal/conflict/loss checks; snapshot coverage is constructed only after native checks |
| #0084 preservation | [preservation.rs](../../src/sidecar_candidate/preservation.rs): parser-bound plain-value span, exact prefix/suffix, bounded ASCII replacement and target-only semantic reparse |

The mapping and preservation now consume the production immutable `xmp::Packet`
getters instead of the research model's mutable fields. The adopted packet profile
and `check_edit_constraints()` run before both derivative and no-op preparation.
Concrete declared coupling and read-only packet indicators refuse. There is no
fallback serialization, insertion, CDATA/reference rewrite or general XML writer.
Research crates are not linked into the root and their historical evidence stays
separate. Unknown namespace semantics remain unverified; an internal candidate
does not clear source-specific publication admission.

## Verification and remaining gates

[Actual native unit controls](../../src/sidecar_candidate/tests.rs) exercise the
compiled crate-private module, actual authored filesystem reads, derivative and
no-op paths, exact complements and source ranges, competing byte/name/ancestor
actors, property staleness/reversion, alias/read limits, original-snapshot reuse,
duplicate intents, explicit conflicts/losses/ordinal and incomplete CMT2/coupled
packet refusal. Each fixture independently rereads the original files and neighbor
after releasing holds and checks the exact namespace count. These controls are
finite Windows observations, not a VM/power campaign or cross-platform proof.

The result remains **internal prepared candidate/no-op/refusal**, not a published
artifact or public command. Native RAW parsing is not format authenticity or
complete source dependency admission. Existing-sidecar replacement, new-name
publication, source-specific effects/rights, qualified profiles, durable receipts,
restart custody and all original #0085 gates remain separate. The accepted
[VM-off-only power policy](../write-safety/power-test-policy.md) is unchanged.

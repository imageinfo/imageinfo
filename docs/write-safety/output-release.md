# Owned output editing-policy qualification

**#0039**, observed **2026-10-13**, tests #0022's next live operational gap: whether
the creator can release a fresh guarded Windows output to ordinary private-owner
editing. **The measured transition is not qualified.** New safe Rust reuses the
unchanged SDK boundary; no new API, source ACL change, privilege or production
writer/profile is introduced.

## Findings

The worker creates a fresh sealed marker, retains its original handle, verifies
bytes/identity/properties, and publishes that held object without replacement into
its own private root. After rechecking, it attempts the ordinary protected private
owner DACL through the existing `SetSecurityInfo` helper.

| Cell | Actual result |
| --- | --- |
| Creator requests WRITE_DAC in addition to read/write, DELETE and READ_CONTROL | Setter returns access denied, error 5; sealed output retained. |
| Creator requests explicit full control | Same error 5; a requested mask is not proof of effective authorization. |
| Creator omits WRITE_DAC | Same error 5, with no reopen/privilege fallback. |
| Ordinary unsealed control | Setter returns success, then exact descriptor check refuses. Private flag observation has protected + auto-inherited, one explicit FullControl allow, no inherited entries; after-exit read/write succeeds. |
| Held sealed actors | Read succeeds; seven time/attribute/security/owner/ADS/data/link actors refuse. Four actors also refuse after the release attempt. |
| Sealed files after exit | Read succeeds; data/ADS/time/security/owner/link/attribute actors refuse. Separate rename/delete cases succeed: restrictive editing is not immutability. |
| Kill/cancel before rename, before release, after attempt | Actual stage/output presence retained; no fabricated committed or terminal kill report. Cancellation after publication retains output. |
| Injected failure before/after release | Labeled protocol injection, not fabricated OS failure; actual output remains. |
| Destination collision | Foreign winner and owned stage retained; release never attempted. |
| Admit/finalize/prune; unsupported platforms | Refuse before worker artifacts; no restart or backend permission. |

The control's descriptor mismatch is kept distinct from sealed access denied.
No representation flag is ignored, policy softened, source ACL changed or path
reopened for a repair attempt. There is no assertion about the internal reason for
the denial or impossibility of every other strategy. Releasing ordinary editing
rights would also end property exclusion; it needs an explicit protocol boundary
before any implementation can claim a committed outcome.

## Evidence

[The ledger](output-release-observations.json) audits **30 worker captures**,
**40 actor captures** and **381 readable artifacts**. Marker names, role outcomes
and errors are public; SIDs, object IDs, private paths, media, captures and binaries
remain local. Earlier first/control attempts are retained. Observations use Windows
11 x64 build 26200, local NTFS, the ordinary current token and unchanged DOS mapping.
No OS crash or physical power loss was exercised.

[The marker experiment](../../experiments/0039-output-release/README.md) has explicit
size/control/wait bounds and preserves all roots. The actual matrix verifies native
behavior; its Rust harness contains no unit tests. Research formatting/Clippy/release
and root formatting/Clippy/**44 Windows tests**/release pass. Python syntax and docs/
link/JSON checks accompany [three-platform source CI](output-release-ci.json).

[Dependencies](output-release-dependencies.json) reuse the same 14 packages and 15
notices as #0038; exact lock/archive identities and notice hashes were checked.
[Boundary review](../../experiments/0039-output-release/ffi-review.md) records reuse
and primary references. Shared SDK source, root lockfile and production unsafe
policy remain unchanged.

## Handoff and remaining gates

This completes the scoped experiment, with a failed operational-output enablement
cell. **Do not adopt the sealed research descriptor as ordinary product output.**
It obstructs owner editing after exit, and the measured creator-held release does
not resolve that obstruction. Repeat queries against the same mechanism cannot
substitute for a supported output strategy.

#0014/#0022 retain complete source/property/path handling, usable output policy,
Windows namespace/receipt persistence and safe restart/finalization/prune. #0027
still refuses actual RAW mutations. These observations do not enable #0023,
replacement, rollback or a writer, and do not qualify other OS/filesystem adapters.

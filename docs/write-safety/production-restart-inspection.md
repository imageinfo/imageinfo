# Bounded production restart inspection

**#0170, 2026-10-17.** The internal storage implementation now parses the actual
`windows-new-output-contract-v1` records and reacquires read-only native guards.
It implements the selected [current caller survivor rule](new-output-contract.md)
without finalization, prune, restore, publication or public apply effects. The
fixed Windows profile remains unqualified; inspection grants no RAW admission.

The caller explicitly supplies the source path, transaction root, operation,
format revision, output leaf and candidate length. Records never supply paths to
follow. The collector holds the physical source, existing root and ancestry,
candidate or installed output, and each required record. Every regular file is
checked for exact identity, bytes, length, creation/write time, attributes,
owner/DACL, single-link topology and default-stream-only support. Owned artifacts
must retain the root's ordinary private owner/DACL. The root is an existing
private directory, opened without write/delete access. Every guard remains held
through classification; dropping the inspection only closes handles.
The first failed recheck permanently closes that inspection attempt, including
namespace mismatch and directory-enumeration errors. An actor reverting its
change cannot revive the same inspector or allow its old authority to classify a
survivor. A new interval requires an explicitly fresh inspection.

The exact namespace contains one candidate **or** one installed output, followed
by a contiguous prefix of the four fixed record leaves. There are at most five
entries. Missing, additional, foreign, case-aliased, hard-linked, inaccessible,
changed, oversized, empty, torn and unsupported states refuse and retain all
artifacts. In particular, absence of the output after release never establishes
that publication did not occur. There is no missing-output fallback to staging.

Each record is at most 65,536 bytes. Parsing borrows fixed length-prefixed fields
with exact known counts, fixed profile/implementation revisions, exact prior
binding prefixes and the expected diagnostic phase sequence. It rejects trailing
fields, unknown revisions, duplicate identities, overlong fields and truncated
lengths. A phase sequence supplies consistency evidence only: it creates no live
acknowledgement or caller authority. Source and candidate reads retain the
existing 64 MiB per-file native bound. The independently retained caller binding
set also has its existing 65,536-byte cumulative construction ceiling.

Directory size/write time change during child creation. The original live binding
therefore contains historical root and containing-parent observations. Inspection
retains their **actual current** held snapshots separately, verifies identities
and the declared stable directory properties against the historical observations,
and only then compares the unchanged historical binding with independent caller
history. Size/write time and the directory archive bit are excluded by that
existing directory policy; file snapshots are never projected or rebased. This
does not prove an uninterrupted guard interval before restart.

The collector exposes observations without authority. Classification consumes an
unrevoked, single-use [explicit current caller token](caller-custody.md)
and freshly checks the complete held set again:

| Fresh actual state and authorized action | Read-only interpretation |
| --- | --- |
| Candidate, expected output absence and one or two complete prior records; stopped-before-release authority for unpublished prune | Expected absence established; nothing is removed. |
| Installed output and complete prepared/intent/observation prefix, with an existing complete receipt when previously bound; explicit finalization authority | Recoverable installed unit; no new completion or flush is claimed. |
| Installed output and all four complete records; independent terminal-completion authority | Previously completed match recognized; nothing is republished. |
| Missing, stale, contradictory or mismatched authority, wrong survivor/action, or failed fresh checks | Recovery required or refusal, with all material retained. |

An unexpectedly missing previously bound receipt cannot become eligible merely
because the remaining three records parse: the current binding set fails the
independent caller's exact comparison. A later owner edit similarly invalidates
the old matching survivor. There is no parser-to-authority constructor, PID test,
receipt self-authentication, automatic history importer or mutation method.

## Evidence and limits

Authored native cases execute the actual internal publication runtime for the
complete receipt control, then close its original handles before inspection.
Separate authored prepublication controls retain the candidate and prior records.
The tests cover complete and absent survivors, missing/truncated/torn/extra/foreign
records, same-byte foreign replacement, later owner edits, readonly changes,
hard-link aliases, absent/both candidate-output names, missing and revoked
authority, and property conflict after reacquisition. Every read-only matrix cell
compares independent before/after names, hashes, separately held physical-file
identities, available full file snapshots, ordinary file metadata, directory
properties and protected source bytes. The identity inventory remains available
when an unsupported link count or preexisting writer prevents guard acquisition.
Parser controls include every
truncated prefix of each authored exact record, malformed bounds and deterministic
fuzz inputs. Detailed authored artifacts and audit results remain in the ignored
private work directory.

A separate actual-runtime control stops immediately before receipt creation,
after the native observation/root flush. Its independently captured three-record
installed state permits the read-only recoverable interpretation under fresh
released-and-stopped caller authority. Removing an already bound receipt from the
four-record control produces the same visible prefix but fails the caller's
exact historical binding comparison. Namespace regressions cover both bounded
name mismatch and enumeration-limit failure, followed by actor reversion and
continued refusal from the same inspector.

These are native Windows process observations, not guest restart or VM-off
qualification. No source media, source ACL, physical power, VM, cleanup, repair,
fresh finalization, durable acknowledgement or production profile is exercised.
The existing [VM-off-only best-effort policy](power-test-policy.md) remains in force.

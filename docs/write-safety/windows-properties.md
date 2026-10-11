# Windows private properties and publication boundaries

**#0030**, observed **2026-10-11**, under #0022. The
[authored marker experiment](../../experiments/0030-windows-properties/README.md)
qualifies security-at-creation and measures publication/property boundaries.
**The complete Windows backend fails the enablement gate.** No CR3 metadata writer,
storage profile, committed receipt or automated repair is enabled.

## What the actual sequence establishes

| Cell | Observation | Disposition |
| --- | --- | --- |
| Private directory/artifact creation | Managed constructors receive the protected owner-only ACL at creation; exact owner/DACL/ACE, attributes and streams are checked before proceeding. | Scoped creation-policy observation. No temporary broad inherited ACL followed by sensitive-data repair. Other-user token access and privileged threats were not tested. |
| Strict held candidate | Read sharing excludes the tested content writer and also refuses our pathname move with sharing violation 32. | Safe refusal; this managed move cannot implement the required full guarded publication. |
| Delete-share candidate, no ancestor guard | A complete marker appears at the absent output name; pathname-observed device/inode matches the earlier candidate. A racing destination is retained. | Conditional new-name visibility observation, not held-stage identity authority or complete atomicity/durability proof. |
| Delete-share candidate plus #0029 held ancestors | Ordinary competing stage/parent moves and our publication are refused. The anchor's held identity/content remain stable. | Integrated exclusion works for the measured actor; the selected move does not compose into a usable backend. No fallback by releasing guards. |
| Timestamp, readonly bit, DACL and alternate stream actors | Mutations succeed before/after visibility despite exclusion of default-stream content writers; checks detect and refuse/retain uncertainty. | Property observation is not mandatory property protection. Streams are separate from default-stream contents. |
| Late named candidate substitution | After the last check, an actor moves the held stage and creates foreign bytes at its old name. The unguarded pathname move publishes those foreign bytes; post-check rejects. | **Failed enablement gate.** A held content stream plus a pathname check is not a bound publication operation. |
| Candidate/record/output flushes | Ordered `Flush(true)` calls return; observation record explicitly says recovery-required and not committed. | File acknowledgements only. No directory/namespace acknowledgement or durable receipt. |

No successful publication in this experiment has **all** required guards. The two
different sharing policies are explicit independent test modes, never an automatic
downgrade. The late counterexample uses authored foreign marker bytes, not a private
photo. It is retained alongside the still-correct held stage; nothing is rolled back
or cleaned up by filename.

## Scope and verification

The local suite has **43 cases**: creation/publication comparisons, racing destination,
content writers, before/after timestamp/readonly/ACL/stream changes, candidate/parent
renames, guarded comparisons, late substitution, failure and process kill at each of
nine barriers, cancellation before/after publication, existing root and unsupported
operand refusal. Failed method hypotheses are retained privately; final passing
qualification means the assertions about both successes and **counterexamples** hold.
It does not mean the full backend passed.

The local environment is Windows 11 x64 build 26200, fixed local NTFS, ordinary drive
mapping and installed Windows PowerShell 5.1 / .NET Framework. The exact worker
versions and sanitized per-case results are in
[the machine-readable observations](windows-property-observations.json).
Hardware/write-cache/controller guarantees and synchronization configuration are not
established. No admin/volume flush, host reboot, existing WSL disruption, OS crash or
power-loss experiment occurs. Public CI uses marker data only; private RAW inputs and
network originals are never accessed by this experiment.

The supervisor retains exact argv, stdin, stdout/stderr, files and observations in
ignored scratch storage. Some property tests deliberately broaden a marker ACL;
those retained files are **not** advertised as private media. Reports contain no
account SID, filesystem object ID, personal-media path or per-image hash. No third-
party source/assembly is copied and no Cargo dependency changes.

## Retained implementation and safety gates

Terry authorized splitting write work. #0030 hands off these qualification findings;
**#0032 retains the unfinished implementation criteria from #0030** under #0022:

- Select/review a conventional Windows publication operation that binds the actual
  held candidate and checked parent, preserves required exclusion, refuses collisions
  and does not need unguarded pathname substitution or releasing guards.
- Integrate private creation/property policy with live stable identity authority.
  Resolve creation races and property windows; do not label repeated path checks as
  mandatory protection. Review any unavoidable isolated FFI and explain its benefit.
- Establish the actual candidate/record/namespace/receipt acknowledgement sequence,
  including a supported namespace persistence method or an explicit unsupported
  disposition. File flush success and process survival are insufficient.
- Demonstrate deterministic OS failures and bounded uncertainty/artifact retention
  around the actual boundary on a declared OS/filesystem/storage configuration.
  No host volume/admin shortcut without separately authorized scope.

#0031 is blocked on that usable sequence as well as the accepted #0029 evidence;
it retains isolated crash/durability and guarded repair. #0022/#0014 remain open.
WS-009/010/011/013/014/015/023/024 and GAP-004/GAP-009 are **not** relaxed. #0027
format/authenticity admission and #0023 CLI integration remain separate gates.
An owner-only DACL cannot by itself freeze same-user or privileged property/namespace
actors. A future weaker concurrency policy requires Terry's explicit product decision.

## Primary sources and engineering choice

Viewed **2026-10-11**, live Microsoft references; no immutable documentation revision
is asserted. These sources identify API contracts; the measured counterexamples are
our own experiments and must not be generalized to every possible Windows backend.

- [DirectoryInfo.Create(DirectorySecurity)](https://learn.microsoft.com/en-us/dotnet/api/system.io.directoryinfo.create?view=netframework-4.8.1): security-at-creation overload; existing directory creation is not exclusive.
- [FileStream security constructor](https://learn.microsoft.com/en-us/dotnet/api/system.io.filestream.-ctor?view=netframework-4.8.1): supplies file security at creation, avoiding an exposure window from setting ACLs later.
- [FileShare](https://learn.microsoft.com/en-us/dotnet/api/system.io.fileshare?view=netframework-4.8.1): distinct sharing permissions, including deletion.
- [File.Move](https://learn.microsoft.com/en-us/dotnet/api/system.io.file.move?view=netframework-4.8.1): the two-argument move refuses an existing destination; same-volume NTFS is the measured scope.
- [FileStream.Flush](https://learn.microsoft.com/en-us/dotnet/api/system.io.filestream.flush?view=netframework-4.8.1) and [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers): file-level synchronization contracts, not proof of this complete namespace/receipt protocol.
- [WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile): last-write time can remain incompletely updated until writing handles close. Held-stream time checks are snapshots; the supervisor separately reports post-close time equality and makes no time-preservation guarantee.

Managed installed APIs let us measure security-at-creation without a new Rust
dependency or application-owned unsafe code. This is a disposable **qualification
choice**, not a PowerShell/.NET production stack decision. The failed composition
explains why an ordinary high-level move cannot simply be promoted into imageinfo.

# Existing-target Windows marker replacement (#0093)

The isolated [marker probe](../../experiments/0093-conditional-replacement/README.md)
measures a bounded Windows NTFS `std::fs::rename` replacement sequence. It is an
explicitly unsupported profile. Every observation leaves production replacement,
commitment and profile enablement false. A retained target on refusal is useful
evidence about that attempt; successful unguarded controls do not establish a
conditional expected-target replacement operation.

This ticket uses only fresh authored scratch markers. `input.marker` is a
distinct protected original input, retained and checked independently in every
case. `candidate.bin` is separately authored staging material; only that staging
entry is passed as the rename API's source. No protected original, RAW media,
source ACL, frozen worker or guest capture is changed. Roots, unrelated entries,
old targets moved by actor controls and partial/error artifacts remain retained.

## Exact boundary reviewed before use

Observed on 2026-10-15 against pinned Rust **1.99.0**, revision
`b940084d7eb6a299eb4bfeb8e34901bc051e7ac4`. The
[standard-library documentation](https://doc.rust-lang.org/std/fs/fn.rename.html)
and [exact Windows implementation](https://github.com/rust-lang/rust/blob/b940084d7eb6a299eb4bfeb8e34901bc051e7ac4/library/std/src/sys/fs/windows.rs)
were reviewed before native qualification. Windows `std::fs::rename` first uses
`MoveFileExW` with replacement. An access-denied result can trigger a source DELETE
reopen and `SetFileInformationByHandle` with `FileRenameInfoEx`, replacement and
POSIX-semantics flags. It is therefore incorrect to describe this as a fixed
MoveFileEx-only call or infer an exact native failure from the public Rust API.
The probe records the actual outcome and returned OS error; it does not trace
which internal call ran or claim that a fallback was observed merely from success.

The experiment invokes only ordinary safe Rust APIs. Windows `OpenOptionsExt`
sets fixed share modes; a fresh-root directory handle uses zero desired access
and the documented backup-semantics flag. Safe `same-file` 1.0.6 handles compare
actual simultaneously held volume/index identities. Safe `winapi-util` 0.1.11
reads existing handle information, including link count. The complete isolated
lock graph uses existing root-admitted versions and notices. No new SDK wrapper,
hand-written unsafe code, API import, privilege, source ACL operation or dependency
implementation is added. The root's unsafe prohibition is unchanged.

Primary Windows references:
[sharing compatibility and delete/rename access](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[replacement flags](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw),
and [safe OpenOptionsExt API](https://doc.rust-lang.org/std/os/windows/fs/trait.OpenOptionsExt.html).
These describe requested API behavior; the native observations remain the evidence
for the declared machine/filesystem configuration.

## Holds, checkpoints and actor windows

Before exposing the first actor gate, the worker captures actual open target,
candidate and fresh-root identities. The protected input is opened with read-only
access and read sharing in every mode. Fixed baseline bytes and properties come
from these held objects, not from a supplied JSON assertion or filename alone.

| Mode | Extra holds during the attempted call | Purpose |
| --- | --- | --- |
| `target-guard` | Target read access, read sharing; fresh-root directory excludes delete sharing | Isolate the existing target hold |
| `source-guard` | Staging candidate read access, read sharing; fresh-root directory excludes delete sharing | Isolate the rename source-path reopen restriction |
| `both-guard` | Both file holds plus fresh-root directory hold | Test their conjunction |
| `unguarded-control` | Baseline observation handles only | Disposable positive API control |
| `weak-target-control` | Target read access with read/delete sharing | Show the gap when pathname deletion/renaming is allowed |

File checks compare captured and freshly opened name identities, exact default-
stream marker bytes, length, creation/write times, readonly/attribute bits, link
count and volume/index. Strong modes renew these checks after the last actor gate
before calling rename. A mismatch refuses before the worker attempts the rename;
it retains the actual current foreign/directory/modified state rather than
restoring a stale baseline over it. All handles remain open through independent
result inspection. No mode drops a strong file guard to turn its refusal into
a success claim.

The actor suite separately measures data-write/name attempts, preopened writers,
case-specific collision/missing/foreign names and option-A property changes.
Controls intentionally omit the renewed final check to expose the time between
the last validation and an unconditional pathname replacement. Such a control is
an authored counterexample experiment, with no authority to overwrite a real
foreign object.

The worker checks only its declared basic-property subset. The independent
observer also reads owner/DACL and named-stream inventory before/after. Those
observations do not add worker security/ADS admission checks. Access time is
excluded because reads themselves can affect it. The fresh root is held in strong
modes, but higher ancestor exclusion is unqualified. See
[option A's exact property boundary](practical-output-policy.md).

## Qualification and limitations

The [29-case curated observation record](../../experiments/0093-conditional-replacement/qualification.json)
binds the exact release worker, compiler, source, lock graph and independent
[actor/observer implementation](../../experiments/0093-conditional-replacement/qualify.py).
The [separate standard-library review](../../experiments/0093-conditional-replacement/stdlib-review.md)
records the native boundary reasoning. The final run on 2026-10-15 used local
**NTFS, Fixed**, Windows **10.0.26200.0**, X64, and the pinned Windows MSVC toolchain.

| Actual final-run outcome | Cases | Observed result |
| --- | --- | --- |
| Unqualified successful controls | 4 | Ordinary and weak baseline replacement; late weak-target and weak-candidate name substitution controls |
| Attempted replacement refused by the native operation | 11 | Two returned OS error 5; nine returned error 32 |
| Refused before the worker attempted replacement | 14 | Held identity, exact bytes, basic properties or incompatible guard admission refused |
| Target and complete observed namespace retained across refusal | 25 of 25 refusals | Exact independent before/after comparisons, after any actor's changes |
| Protected original input and unrelated marker retained | 29 of 29 | Names, identities, default bytes, basic properties, owner/DACL and stream inventory unchanged |

The target-only baseline returned error **5**, while candidate-only and both-file
baseline holds returned **32**. The weak late-readonly control also returned **5**
with the actual namespace retained. These are observed Rust-operation results,
not a trace proving which internal Windows calls ran.

The weak target-name control passed the original validation, then an actor moved
the old target aside and installed a fresh foreign marker at its name. The
unconditional operation overwrote that marker. The weak candidate-name control
similarly installed foreign staging bytes after validation; those bytes became
the target. Both are concrete failures of the relaxed pathname sequence to bind
the intended objects. They are deliberately confined to newly authored scratch
objects and never produce a commit or qualified-profile claim.

Other vectors measure missing/directory/foreign names before checks, changed
default bytes, preopened writers, denied late data/name attempts, protected-input
negative actors, and time/readonly/link/stream actors. Worker property checkpoints
and observer coverage remain distinct; the observer measures stream names and
lengths, not ADS content hashes, and does not cover group/SACL/mandatory labels.

Two earlier observer setup attempts stopped at `ready`, before replacement was
issued, because inherited PowerShell module paths prevented the read-only
observer from loading modules. Explicit observer module imports corrected that
setup. The final 29-case evidence is one fresh stable-source run; the earlier
24-case run and all setup/error roots remain private and retained. No raw
security snapshots, private paths, account SIDs or local process logs are public.

Compilation alone is not Windows sharing, rename, collision or property evidence.
Non-Windows invocation refuses without creating fixture files; it does not
simulate Windows success. No Unix filesystem or other Windows volume is qualified.

The observed primitive cannot enable a production replacement profile. Full
ancestor/name and candidate/object exclusion, a conditional expected-target
operation, complete relevant property checkpoints, original-retention/recovery
semantics, namespace/receipt persistence and restart actions remain independent
gates. There is no crash, guest reboot or physical-power test in this ticket.
The experiment does not establish a universal impossibility result for other
Windows APIs or filesystem profiles. #0094 and #0097 retain their separate scopes;
no source deletion, rollback, group operation, media edit or production publication
permission follows from this bounded result.

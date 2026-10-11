# Windows private-property and publication qualification

Card **#0030**, observed **2026-10-11**. This experiment operates only on authored
64 KiB marker bytes. It accepts no media input and is not the imageinfo writer.
The [findings](../../docs/write-safety/windows-properties.md) distinguish successful
creation checks from failed full-profile qualification. **Production permission
and committed results remain false on every path.**

## Reproduce on Windows

Build the reviewed [#0029 guard](../0029-object-guards/README.md), then run:

```powershell
cargo build --locked --release --manifest-path experiments/0029-object-guards/Cargo.toml
python experiments/0030-windows-properties/qualify.py --parent .local/windows-properties-qualification --guard experiments/0029-object-guards/target/release/imageinfo-object-guard-probe.exe
```

The supervisor explicitly launches installed **Windows PowerShell 5.1 / .NET
Framework**. PowerShell Core is not an interchangeable backend: the security-at-
creation constructors used here belong to the Framework API. Python uses only its
standard library. No assembly, third-party source, package or dependency is imported;
the root and experiment Cargo lockfiles are unchanged. There is no application FFI,
P/Invoke, nightly Rust, elevated volume handle or administrator flush.

On other platforms the same supervisor reports unsupported without invoking the
Windows worker or creating worker artifacts; its own empty scratch directory remains.
Use `--parent` under an ignored disposable test directory. All scratch artifacts,
control inputs and stdout/stderr are retained. Mutation cases deliberately broaden
or change **marker-only** properties; do not use this as a private-data intake tool.

## Worker and actual actors

`worker.ps1` supplies protected owner-only security descriptors during private
directory/file creation. It checks exact owner, DACL protection, one explicit owner
FullControl ACE with no inheritance/propagation, allowed attributes and the single
default stream. It observes creation/write times and hashes bytes through the held
stage stream. The current owner can still change these properties; syntactic ACL
verification is not a test using another user's token or a privileged adversary.
After visibility it separately reads at most 65,537 bytes from the installed path;
foreign output with matching ACLs/length/times is detected by its differing contents.
This post-check cannot prevent that publication or establish live installed identity.

`qualify.py` controls nine barriers with a 30-second wait/child bound, injects failures,
cancels or kills only its own worker, and tests actual unrelated file/property actors.
It compares Python's **pathname-observed** device/inode before/after publication.
That is not live handle identity authority. The inherited guard's live handle identity
protects the marker anchor/ancestors, not the managed stage handle.

Strict stage sharing refuses pathname publication. Delete sharing permits the ordinary
move but permits a late stage substitution. Adding held ancestors refuses both that
substitution and our publication. No test changes from strict to weaker sharing after
a refusal: these are separate explicitly selected research comparisons.

## Acknowledgements and limits

Barriers follow actual successful operations:

1. Owner-only root/anchor creation and verification.
2. Candidate `Flush(true)` and property/content verification.
3. New private prepared record `Flush(true)`.
4. New private intent record `Flush(true)`.
5. Before-publication control point.
6. Final check complete, before pathname move.
7. Namespace operation returned; output observed.
8. Post-check and output file `Flush(true)`.
9. Private **observation**, not committed, record `Flush(true)`.

There is **no namespace persistence acknowledgement**. Records are bounded authored
observations, not integrity/authentication/custody or automated recovery implementation.
A record flush cannot fill that missing boundary. All successful-visibility runs end
with exit 5, `recovery-required`, `committed:false`, `namespaceAcknowledged:false`.
Cancellation before an attempted move exits 130; post-attempt uncertainty exits 5.
No file cleanup, property repair, original replacement, retry or fallback occurs.

Host supervision is not an interruptible OS I/O deadline or memory quota. Process kills
are not OS crashes or power loss. Root creation/path checks are not exclusive directory
creation or protection against ancestor substitution. Network/removable/cloud paths,
cross-volume publication, extended paths, alternate storage providers, privileged
actors, hardware cache behavior and a complete property-preservation policy remain
unqualified. [#0032's retained gates](../../docs/write-safety/windows-properties.md)
must be satisfied before #0031 durability/repair and production integration.

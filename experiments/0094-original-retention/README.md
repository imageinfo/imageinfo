# Original retention marker protocol (#0094)

This isolated Windows research executable creates only fresh authored marker
files below this checkout's ignored `.local` directory. It retains the current
original object and a distinct owned byte-for-byte original copy before measuring
#0093's unsupported replacement operation. It enables no production replacement,
restore, cleanup, durability, storage profile or RAW operation.

```powershell
cargo build --manifest-path experiments/0094-original-retention/Cargo.toml --locked --release
# The parent exists; this particular root must not exist.
experiments/0094-original-retention/target/release/imageinfo-original-retention-probe.exe C:\Projects\imageinfo\.local\retention-example keep
```

The second argument is exactly `keep` or `no-backup`. Both execute the same
precommit retention path; `no-backup` only records the request. It never authorizes
discarding the recoverable original. There is no postcommit deletion path.

Each JSON event waits for the exact input line `continue`, except `result`, which
waits for `exit`. EOF, malformed gates and I/O errors stop the worker and retain
all artifacts. Gates are `ready`, `retention-created`, `retention-written`,
`retention-synced`, `precommit`, then `result`. The caller can actually terminate
this disposable worker at any gate, then inspect its retained artifacts without
replaying the operation. A killed process emits no later result.

Fixed files are `target.bin` (`OLD094\n`), `candidate.bin` (`NEW094\n`),
`unrelated.marker` (`OTHER094\n`) and `retained-original.bin`. The latter is absent
at `ready`, empty at `retention-created`, and contains the exact original target
bytes from `retention-written` onward. A partial or failed copy never grants
replacement permission. The unchanged current target is the recoverable original
before the copy completes.

Ownership comes from actual fresh creation and simultaneously held handles,
not JSON supplied by a caller. Safe `same-file` handles compare identities;
`winapi-util` supplies the existing safe link/volume/index query. The isolated
lock graph reuses #0093's admitted versions. No new unsafe block, SDK boundary,
privilege, cryptographic construction or production dependency is introduced.

See the [protocol and evidence limits](../../docs/write-safety/original-retention.md)
and the independently maintained `qualify.py` / `qualification.json` beside this
file. Build checks alone are not Windows sharing or interruption evidence.

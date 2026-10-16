# Local planning board

The initial imageinfo board uses Terry's seven-lane localswim workflow:

Backlog → Ready For Work → In progress → Ready for review → Completed,
with separate Blocked and Needs Terry lanes. The embedded policy defines the exact
allowed transitions. Bot does not approve its own work into Completed.

Terry reiterated on **2026-10-14**: only an explicit Terry hold or insufficient
detail justifies Backlog. Fully scoped cards, including organizational umbrellas,
stay Ready for Work when their remaining constraint is another ticket. Record the
prerequisites as relationships. Execute bounded children and hand those off into
Ready for review; do not repeatedly hand off partial progress on an umbrella.

Terry's lane definitions, clarified 2026-10-11: Backlog means insufficient scope
or an intentional hold by Terry. Ready For Work means sufficiently scoped, even
when completion depends on other Ready For Work tickets. Record those dependencies
explicitly rather than using Backlog as a dependency queue. In progress also covers
a resumption point explicitly designated by Terry. Blocked records an actual blocker
for started work; Needs Terry records a concrete decision/input/approval request.
Ready for review is the verified/published handoff; Terry alone accepts Completed.
See [AGENTS.md](../AGENTS.md) for the standing triage guidance. #0012 is intentionally
held by Terry and remains Backlog.

Terry clarified triage precedence on **2026-10-14**: every In progress card ranks
ahead of every Ready for Work card. Lane precedence comes before blocking depth,
priority and ticket number; those order cards within a lane. Query In progress
first and work existing cards before pulling from Ready for Work. A combined CLI
query that interleaves the lanes does not override this rule.

The active board is stored at
`C:\Projects\localswim-state-store\imageinfo\imageinfo.json` in Terry's private
state-store repository, approved on 2026-10-12. The old ignored
`boards/imageinfo.json` is a migration backup; do not launch or mutate it.
Terry's current multi-project UI is
**[http://localhost:8810/board/imageinfo/imageinfo](http://localhost:8810/board/imageinfo/imageinfo)**,
confirmed on **2026-10-14**. The workspace gateway proxies requests to each board's
individual service. The CLI still targets the imageinfo JSON path and resolves
that service's descriptor; the active snapshot and sole writer do not change.

Imageinfo's individual service port can change when the shared gateway launches
it with an automatically assigned port. Resolve the current live service port on
each resume from its runtime descriptor or its owned process listener; keep runtime
credentials private. **8810** is the workspace gateway port. Pass the verified
individual service port to the monitor. Port-independent proxy status is available at
`http://localhost:8810/api/v001/workspace/boards/imageinfo%2Fimageinfo/status`.
These addresses work only on this machine. Keep board data and credentials out of
the public repository.

## Reuse and lifecycle

Read the board's configured port and check `/api/v001/status` before starting a
service. Reuse a healthy service for that board. With localswim installed, the
commands are:

Reuse the existing multi-project gateway. When it needs a fresh launch, run
`uv run --frozen localswim --autopush C:\Projects\localswim-state-store --port 8810`
from `C:\Projects\localswim`. The workspace reuses healthy board services and starts
missing ones; `--autopush` applies to newly started services. Verify imageinfo's own
push status even when the workspace is healthy. Per-board CLI commands below remain
valid; an individual-board launch is only needed when no healthy service already
owns that board.

```console
uv --directory C:\Projects\localswim run --frozen localswim --autopush C:\Projects\localswim-state-store\imageinfo\imageinfo.json
localswim-cli C:\Projects\localswim-state-store\imageinfo\imageinfo.json board show
localswim-cli C:\Projects\localswim-state-store\imageinfo\imageinfo.json board verify
localswim-cli C:\Projects\localswim-state-store\imageinfo\imageinfo.json card next 5 --lane in_progress
localswim-cli C:\Projects\localswim-state-store\imageinfo\imageinfo.json board shutdown
```

When selecting work, consult `card next 5 --lane ready_for_work` only after the
In progress lane has been considered under the precedence above.

Terry authorized board autopush on 2026-10-12. Every imageinfo service launch,
including restarts, must include `--autopush`. Verify the status endpoint's `push`
state and detail rather than assuming synchronization. Confirm the initial snapshot
is committed and pushed to the private state store, and investigate `failed` or `off`
states. Keep board snapshots out of this public repository.
Always launch from the official local source checkout, `C:\Projects\localswim`,
as Terry required on 2026-10-13. Use its frozen uv environment and that working
directory, rather than the installed `localswim.exe` copy. The service derives its
build ID from its loaded module's Git checkout; an installed copy outside Git can
report `unknown`. Verify the status endpoint reports the checkout's actual revision
and `codeStale: false`. Do not hard-code a build label. The clean checkout reported
`d3219c6` when this instruction was recorded; later verified revisions can differ.

For a hidden Windows launch from Codex, set `UV_CACHE_DIR=C:\Temp\localswim-uv-cache`
and `PYTHONIOENCODING=utf-8`, then use `Start-Process` with the uv executable,
arguments `run --frozen localswim --autopush <active-board-path>`,
`-WorkingDirectory 'C:\Projects\localswim'`, `-WindowStyle Hidden` and private
stdout/stderr log paths. First gracefully shut down an existing service and verify
the port is no longer listening; never launch a duplicate.
Restart the service after a machine restart when needed. Whenever it runs, the
JSON board-write monitor **MUST also be running**,
targeted at the active Codex thread (Terry's instruction, 2026-10-10). Verify both
on startup/resume and before board work. Keep the monitor alive between tasks for
the service's lifetime. This is a filesystem watcher, not a scheduled poll.

### Start, retarget or upgrade the monitor

Use the shared `localswim-monitor` command from the official
`C:\Projects\localswim` package, with its optional `monitor` extra. Do not copy
filtering code into this project or launch the retired FGA-local watcher.
The package uses one owner and imageinfo-specific status, target and lock files.
Keep these private runtime paths separate from every other board.

For an existing monitor, preserve its original `threadId` during an upgrade.
Normal explicit retargeting to the active chat is a separate operation. Inspect
status and actual process/listener health; status alone is not liveness proof.

```powershell
if (-not $env:CODEX_THREAD_ID) { throw 'An active Codex thread ID is required.' }
$env:PYTHONIOENCODING = 'utf-8'
$env:UV_CACHE_DIR = 'C:\Temp\localswim-uv-cache'
if (-not $env:LOCALSWIM_BOARD_PORT) { throw 'Set LOCALSWIM_BOARD_PORT from the current verified service endpoint.' }
$imageinfoPort = [int]$env:LOCALSWIM_BOARD_PORT
$imageinfoMonitorArgs = @(
    'run', '--isolated', '--frozen', '--extra', 'monitor', 'localswim-monitor',
    '--board-path', 'C:\Projects\localswim-state-store\imageinfo\imageinfo.json',
    '--board-label', 'imageinfo',
    '--thread-id', $env:CODEX_THREAD_ID,
    '--port', $imageinfoPort,
    '--status-path', 'C:\Temp\imageinfo-localswim-monitor-status.json',
    '--target-path', 'C:\Temp\imageinfo-localswim-monitor-target.json',
    '--lock-path', 'C:\Temp\imageinfo-localswim-monitor.lock'
)
Start-Process -FilePath (Get-Command uv).Source -ArgumentList $imageinfoMonitorArgs -WorkingDirectory 'C:\Projects\localswim' -WindowStyle Hidden -RedirectStandardOutput 'C:\Temp\imageinfo-localswim-monitor.out.log' -RedirectStandardError 'C:\Temp\imageinfo-localswim-monitor.err.log'
```

The isolated frozen runtime avoids resynchronizing an executable held by another
running board. An installed package with the `monitor` extra can invoke
`localswim-monitor` directly with the same explicit arguments.

Use cooperative `--reload` only when the existing status reports
`reloadSupported: true`. Preserve the same board, thread target, port and runtime
paths. The old owner drains its quiet window and releases its lock before the
replacement owns it. For a legacy watcher without reload support, use its
documented graceful board-stop/restart boundary once; never terminate its PID to
force migration. A schema-1 target-file `stopPid` request names the exact owner
and waits until that board service stops. Keep the gateway and unrelated boards
running. Keep the lock file persistent.

After startup/reload, verify the board's `/api/v001/status`, live monitor process,
`state: running`, `actorFilterVersion: 2`, supported reload status and exact thread
target. Restore monitoring before continuing board work if startup fails.

After a 15-second quiet window, the monitor queries sanitized activity metadata
through `localswim-cli`. Suppress a nonempty result only when every event is by
`bot` (or the explicitly configured automation actor). Human, mixed, unknown,
empty, malformed and failed queries still alert. Filesystem write counts and
activity counts are not equivalent and must never be compared for suppression.
For an already queued alert, inspect only its bounded activity metadata first;
proven bot-only activity needs no card inspection, work resumption or further action.
Queued alerts do not establish delivery to a turn that was already active.

Runtime status/target/lock/log files stay private under `C:\Temp`; never commit
card prose, runtime credentials, board snapshots or monitor logs. The monitor
remains running for the service's lifetime, including between tasks.

## Creating another local board

Use localswim's checked Terry-workflow board-description and permissions examples
with `localswim-cli <board-path> board init <description> <permissions>`. Set a
unique project name and unused local port in the initialization description before
initializing. Do not overwrite an existing board or copy another project's private
snapshot as a template.

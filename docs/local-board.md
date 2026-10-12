# Local planning board

The initial imageinfo board uses Terry's seven-lane localswim workflow:

Backlog → Ready For Work → In progress → Ready for review → Completed,
with separate Blocked and Needs Terry lanes. The embedded policy defines the exact
allowed transitions. Bot does not approve its own work into Completed.

Terry's lane definitions, clarified 2026-10-11: Backlog means insufficient scope
or an intentional hold by Terry. Ready For Work means sufficiently scoped, even
when completion depends on other Ready For Work tickets. Record those dependencies
explicitly rather than using Backlog as a dependency queue. In progress also covers
a resumption point explicitly designated by Terry. Blocked records an actual blocker
for started work; Needs Terry records a concrete decision/input/approval request.
Ready for review is the verified/published handoff; Terry alone accepts Completed.
See [AGENTS.md](../AGENTS.md) for the standing triage guidance. #0012 is intentionally
held by Terry and remains Backlog.

The board is stored at `boards/imageinfo.json` in the local checkout and is ignored
by Git. Its initial port is **8795**, giving the local URL
`http://127.0.0.1:8795/`. This address works only on the machine running the service;
it is not a hosted public board. Board data and service credentials must stay out of
the public repository.

## Reuse and lifecycle

Read the board's configured port and check `/api/v001/status` before starting a
service. Reuse a healthy service for that board. With localswim installed, the
commands are:

```console
localswim --autopush boards/imageinfo.json
localswim-cli boards/imageinfo.json board show
localswim-cli boards/imageinfo.json board verify
localswim-cli boards/imageinfo.json card next 5 --lane ready_for_work
localswim-cli boards/imageinfo.json board shutdown
```

Terry authorized board autopush on 2026-10-12. Every imageinfo service launch,
including restarts, must include `--autopush`. Verify the status endpoint's `push`
state and detail rather than assuming synchronization. The current ignored board
cannot synchronize: localswim reports `off` with `the board is ignored by git`.
Enabling synchronization requires an approved private board-storage destination;
do not remove the ignore rule or publish the board to this public repository.
Restart the service after a machine restart when needed. Whenever it runs, the
JSON board-write monitor **MUST also be running**,
targeted at the active Codex thread (Terry's instruction, 2026-10-10). Verify both
on startup/resume and before board work. Keep the monitor alive between tasks for
the service's lifetime. This is a filesystem watcher, not a scheduled poll.

### Start or retarget the monitor

On Terry's current machine, reuse the shared monitor and its locked tooling
environment in `C:\Projects\FGA\architecture-design`. It watches writes without
reading board content, coalesces them behind a 15-second quiet window, suppresses
proven bot-only activity, and queues a bounded next-turn alert to the target chat.
After an alert, inspect activity through `localswim-cli`; never edit the JSON directly.
Queued alerts do not establish delivery to a currently active turn.

Use imageinfo-specific paths. Reinvoking the helper safely retargets its existing
monitor through the shared lock; never use the FGA defaults or another board's paths.
Launch hidden, inherit UTF-8 output, and pass the board's actual current port:

```powershell
if (-not $env:CODEX_THREAD_ID) { throw 'An active Codex thread ID is required.' }
$env:PYTHONIOENCODING = 'utf-8'
$imageinfoPort = 8795 # Verify against this board's current configuration.
$imageinfoMonitorArgs = @(
    'run', '--frozen', 'python', 'scripts/watch_localswim.py',
    '--board-path', 'C:\Projects\imageinfo\boards\imageinfo.json',
    '--board-label', 'imageinfo',
    '--thread-id', $env:CODEX_THREAD_ID,
    '--port', $imageinfoPort,
    '--status-path', 'C:\Temp\imageinfo-localswim-monitor-status.json',
    '--target-path', 'C:\Temp\imageinfo-localswim-monitor-target.json',
    '--lock-path', 'C:\Temp\imageinfo-localswim-monitor.lock'
)
Start-Process -FilePath (Get-Command uv).Source -ArgumentList $imageinfoMonitorArgs -WorkingDirectory 'C:\Projects\FGA\architecture-design' -WindowStyle Hidden -RedirectStandardOutput 'C:\Temp\imageinfo-localswim-monitor.out.log' -RedirectStandardError 'C:\Temp\imageinfo-localswim-monitor.err.log'
```

Verify `/api/v001/status` is healthy, the monitor status JSON says `running`, its
recorded PID is alive, and the target JSON's `threadId` equals the active thread.
If startup fails, inspect the local error log and restore monitoring before
continuing board work. Stop/restart the service and monitor together; do not leave
the service running unmonitored. A machine reboot requires restarting both.

Monitor status/target/lock/log files are transient private machine state under
`C:\Temp`; do not commit them. Service logs remain under ignored `boards/`.
This shared operational Python tooling does not choose imageinfo's product language.

Card mutations go through the supported CLI and the live service, preserving
authorization, revision checks, and history. Never edit a running board's JSON.
Public requirements and roadmap documents provide the portable project plan;
private board comments and local state are not published.

## Creating another local board

Use localswim's checked Terry-workflow board-description and permissions examples
with `localswim-cli <board-path> board init <description> <permissions>`. Set a
unique project name and unused local port in the initialization description before
initializing. Do not overwrite an existing board or copy another project's private
snapshot as a template.

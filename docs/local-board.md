# Local planning board

The initial imageinfo board uses Terry's seven-lane localswim workflow:

Backlog → Ready For Work → In progress → Ready for review → Completed,
with separate Blocked and Needs Terry lanes. The embedded policy defines the exact
allowed transitions. Bot does not approve its own work into Completed.

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
localswim boards/imageinfo.json
localswim-cli boards/imageinfo.json board show
localswim-cli boards/imageinfo.json board verify
localswim-cli boards/imageinfo.json card next 5 --lane ready_for_work
localswim-cli boards/imageinfo.json board shutdown
```

The initial service runs without board autopush. There is no automatic startup or
scheduled monitor configured by this project setup. Restart the service after a
machine restart when needed. When launching a background process on Windows, use
a hidden window and keep output/error logs under ignored `boards/`.

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

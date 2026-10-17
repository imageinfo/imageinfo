"""Opt-in host controller for the exact preflighted disposable #0174 fixture.

Creates no disks, changes no host devices, and never returns protocol failures.
Only the six fresh authored images named in the private preflight are attached.
"""
import argparse
import hashlib
import http.server
import json
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "0022-ordinary-output"))
from windows_guest import Qmp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("worker", type=pathlib.Path)
    parser.add_argument("--resume-unused-cells", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    expected = pathlib.Path("/var/tmp/imageinfo-windows-eval-20261014/native-errors-0174-20261017")
    if root != expected:
        raise ValueError("Only the independently preflighted fresh disposable fixture is allowed")
    preflight = json.loads((root / "preflight.private.json").read_text())
    cells = preflight["cells"]
    if len(cells) != 6 or preflight["hostDisksExposed"] or preflight["sourceOriginalsExposed"]:
        raise ValueError("Invalid fixture binding")
    capture = root / "captures"
    capture.mkdir(exist_ok=args.resume_unused_cells)
    lock = threading.RLock()
    state = {"active": None, "armed": None, "published": False, "faultAt": None, "attempted": False}
    worker = args.worker.read_bytes()
    meta = {"workerSha256": hashlib.sha256(worker).hexdigest(), "cells": cells}

    def log(kind, value):
        with (capture / "controller.private.jsonl").open("a") as f:
            f.write(json.dumps({"time": time.time(), "kind": kind, "value": value}) + "\n")

    def call(command, arguments=None):
        qmp = Qmp(root)
        try:
            value = qmp.call(command, arguments)
        finally:
            qmp.close()
        log("qmp", {"command": command, "arguments": arguments, "return": value})
        return value

    prior_records = [json.loads(line) for line in (capture / "controller.private.jsonl").read_text().splitlines()] if (capture / "controller.private.jsonl").exists() else []
    attempted_cells = {record["value"]["cell"] for record in prior_records if record["kind"] == "fault-armed"}
    existing = {node["node-name"]: node for node in call("query-named-block-nodes")}
    for index, cell in enumerate(cells):
        disk = pathlib.Path(cell["disk"]).resolve()
        if disk.parent != root or disk.suffix != ".raw" or disk.stat().st_size != 134217728:
            raise ValueError("Unexpected disk")
        prefix = "i174" + str(index)
        cell["node"] = prefix
        if args.resume_unused_cells and cell["cell"] in attempted_cells and not (capture / (cell["cell"] + ".private.json")).exists():
            cell["retainedDetached"] = True
            continue
        if prefix in existing:
            if existing[prefix]["image"]["filename"] != str(disk) or existing[prefix]["children"] != [{"node-name": prefix + "file", "child": "file"}]:
                raise ValueError("Existing node is not the exact clean prepared scratch image")
            continue
        call("blockdev-add", {"driver": "file", "node-name": prefix + "file", "filename": str(disk), "cache": {"direct": False, "no-flush": False}})
        call("blockdev-add", {"driver": "raw", "node-name": prefix, "file": prefix + "file"})
        for mode, event, iotype, code in [("read", "read_aio", "read", 5), ("write", "write_aio", "write", 28), ("flush", "flush_to_disk", "flush", 5)]:
            rule = {"event": event, "iotype": iotype, "errno": code, "once": True}
            if mode == "read":
                # Offline ntfscluster: LCN 16768, 4096-byte clusters, partition
                # LBA 2048. This sector is 8 MiB into authored source data only.
                rule["sector"] = 2048 + 16768 * 8 + 16384
            call("blockdev-add", {"driver": "blkdebug", "node-name": prefix + mode, "image": prefix + "file", "inject-error": [rule]})
        call("device_add", {"driver": "usb-storage", "id": prefix + "usb", "drive": prefix, "serial": "IMAGEINFO0174" + str(index), "write-cache": "on", "rerror": "report", "werror": "report"})
    log("configuration", call("query-block"))
    log("nodes", call("query-named-block-nodes"))
    meta["cells"] = cells
    binding_path = capture / "bindings.private.json"
    if binding_path.exists():
        old = json.loads(binding_path.read_text())
        if old["workerSha256"] != meta["workerSha256"]:
            raise ValueError("Resume cannot change the actual worker")
        binding_path.rename(capture / ("bindings-before-unused-resume-" + str(time.time_ns()) + ".private.json"))
    binding_path.write_text(json.dumps({**meta, "controllerSha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), "guestScriptSha256": hashlib.sha256(pathlib.Path(__file__).with_name("guest.ps1").read_bytes()).hexdigest()}, indent=2))
    if args.resume_unused_cells:
        meta = {**meta, "cells": [c for c in cells if not (capture / (c["cell"] + ".private.json")).exists() and c["cell"] not in attempted_cells]}

    def clear(reason):
        if state["armed"]:
            cell = next(c for c in cells if c["cell"] == state["active"])
            options = {"options": [{"driver": "raw", "node-name": cell["node"], "file": cell["node"] + "file"}]}
            try:
                call("blockdev-reopen", options)
            except RuntimeError as error:
                # A once-only backend flush error can be returned to QEMU's own
                # drain instead of a guest API. Retain it separately, then make
                # one bounded filter-removal attempt; never retry the worker.
                log("filter-removal-error", {"cell": state["active"], "error": str(error)})
                call("blockdev-reopen", options)
            log("fault-cleared", {"reason": reason, "mode": state["armed"], "cell": state["active"]})
            state["armed"] = None
            log("blockstats", call("query-blockstats"))

    def expiry():
        while True:
            time.sleep(1)
            with lock:
                if state["armed"] and time.monotonic() - state["faultAt"] >= 60:
                    clear("60-second backend fault ceiling")

    threading.Thread(target=expiry, daemon=True).start()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            files = {"/worker.exe": worker, "/guest.ps1": pathlib.Path(__file__).with_name("guest.ps1").read_bytes(), "/meta": json.dumps(meta).encode()}
            if self.path not in files:
                self.send_error(404)
                return
            data = files[self.path]
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "application/json" if self.path == "/meta" else "application/octet-stream")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4 * 1024 * 1024:
                self.send_error(400)
                return
            value = json.loads(self.rfile.read(length))
            with lock:
                log(self.path, value)
                if self.path == "/start":
                    clear("new cell")
                    state.update(active=value["cell"], published=False, attempted=False)
                    log("start-blockstats", call("query-blockstats"))
                elif self.path == "/event":
                    if value["cell"] != state["active"]:
                        raise ValueError("Wrong active cell")
                    event = value["event"]
                    label = event.get("barrier")
                    mode = None
                    cellname = value["cell"]
                    if (cellname, label) == ("source-read", "preflight"):
                        mode = "read"
                    elif (cellname, label) == ("staged-write", "create-Candidate"):
                        mode = "write"
                    elif (cellname, label) == ("candidate-flush", "file-Candidate"):
                        mode = "flush"
                    elif cellname == "installed-root-flush" and label == "root-flush" and state["published"]:
                        mode = "flush"
                    elif (cellname, label) == ("receipt-flush", "file-Receipt"):
                        mode = "flush"
                    if mode and not state["armed"] and not state["attempted"]:
                        cell = next(c for c in cells if c["cell"] == cellname)
                        call("blockdev-reopen", {"options": [{"driver": "raw", "node-name": cell["node"], "file": cell["node"] + mode}]})
                        state.update(armed=mode, faultAt=time.monotonic(), attempted=True)
                        log("fault-armed", {"cell": cellname, "mode": mode, "barrier": label, "sequence": event["sequence"]})
                    if event.get("operation"):
                        if event["operation"] == "publish" and event["success"]:
                            state["published"] = True
                        clear("native operation returned")
                elif self.path == "/clear":
                    clear("worker exit or deadline")
                elif self.path == "/result":
                    (capture / (value["cell"] + ".private.json")).write_text(json.dumps(value, indent=2))
                elif self.path in ("/finished", "/failed"):
                    clear("campaign ended")
                    (capture / "finished.private.json").write_text(json.dumps(value, indent=2))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

    http.server.ThreadingHTTPServer(("127.0.0.1", 18724), Handler).serve_forever()


if __name__ == "__main__":
    main()

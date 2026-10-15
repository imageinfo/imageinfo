"""Finite native Windows original-retention observations on fresh authored markers.

The independent read-only observer is shared with #0093 and explicitly hashed.
No saved event or JSON input grants restore, cleanup or publication authority.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import queue
import stat
import subprocess
import tempfile
import threading

REPO = Path(__file__).resolve().parents[2]
OBSERVER = REPO / "experiments/0093-conditional-replacement/qualify.py"
spec = importlib.util.spec_from_file_location("retention_readonly_observer", OBSERVER)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
require, save, sha, snapshot = observer.require, observer.save, observer.sha, observer.snapshot
OLD, NEW, FOREIGN, OTHER = b"OLD094\n", b"NEW094\n", b"BAD094\n", b"OTHER094\n"
GATES = ("ready", "retention-created", "retention-written", "retention-synced", "precommit")
AUTHORITY_FLAGS = ("productionReplacementAllowed", "restoreAllowed", "cleanupAllowed", "committed")


def perform(action, root):
    """Only fixed actors against fixtures this invocation just created."""
    target, candidate, original = (root / name for name in
                                   ("target.bin", "candidate.bin", "retained-original.bin"))
    try:
        if action in ("original-foreign", "original-same-bytes"):
            with original.open("xb") as stream:
                stream.write(FOREIGN if action == "original-foreign" else OLD)
        elif action == "original-directory":
            original.mkdir()
            (original / "foreign.marker").write_bytes(FOREIGN)
        elif action in ("original-target-alias", "original-candidate-alias"):
            os.link(target if action == "original-target-alias" else candidate, original)
        elif action.endswith("-write"):
            path = {"target-write": target, "candidate-write": candidate,
                    "original-write": original}[action]
            with path.open("r+b") as stream:
                stream.write(FOREIGN)
        elif action.endswith("-rename"):
            path = {"target-rename": target, "candidate-rename": candidate,
                    "original-rename": original, "root-rename": root}[action]
            path.rename(path.with_name(path.name + "-displaced"))
        elif action.endswith("-time"):
            path = original if action == "original-time" else target
            before = path.stat()
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        elif action == "original-readonly":
            os.chmod(original, stat.S_IREAD)
        elif action == "original-stream":
            with Path(str(original) + ":foreign").open("xb") as stream:
                stream.write(FOREIGN)
        else:
            raise ValueError("unknown fixed actor")
        return {"action": action, "succeeded": True, "osError": None}
    except OSError as error:
        return {"action": action, "succeeded": False,
                "osError": getattr(error, "winerror", None), "errno": error.errno}


def files_only(state):
    return {name: value for name, value in state.items() if name != "."}


def negative_admissions(binary, scratch):
    cases = []
    for name, mode, reused in (("unknown-mode", "restore", False),
                               ("json-authority-mode", '{"committed":true,"restoreAllowed":true}', False),
                               ("reused-stale-context", "no-backup", True)):
        root = scratch / ("negative-" + name)
        captures = scratch / ("negative-" + name + "-capture")
        captures.mkdir()
        if reused:
            root.mkdir()
            (root / "target.bin").write_bytes(OLD)
            (root / "retained-original.bin").write_bytes(OLD)
            save(root / "retention-context.json", {"committed": True, "restoreAllowed": True,
                                                    "cleanupAllowed": True, "owned": True})
        before = snapshot(root, captures, "before") if reused else None
        result = subprocess.run([str(binary), str(root), mode], input=b"", capture_output=True,
                                timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        require(result.returncode != 0 and not result.stdout
                and len(result.stderr) <= 65536, "invalid/stale input acquired live protocol")
        after = snapshot(root, captures, "after") if reused else None
        require(before == after and (reused or not root.exists()), "admission refusal changed marker state")
        save(captures / "observations.private.json", {"before": before, "after": after,
                                                        "exitCode": result.returncode})
        with (captures / "stderr.private").open("xb") as stream:
            stream.write(result.stderr)
        cases.append({"id": name, "refusedBeforeProtocol": True, "actualEntriesPreserved": True})
    return cases


def execute(binary, scratch, case_id, mode, gate=None, action=None, kill=False):
    root, captures = scratch / case_id, scratch / (case_id + "-capture")
    captures.mkdir()
    argv = [str(binary), str(root), mode]
    save(captures / "argv.private.json", argv)
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    messages, stderr, events = queue.Queue(), bytearray(), []

    def read_stdout():
        total = 0
        while True:
            line = process.stdout.readline(16385)
            if not line:
                break
            total += len(line)
            if len(line) > 16384 or total > 131072:
                process.kill()
                messages.put(ValueError("worker event bound exceeded"))
                break
            messages.put(line)
        messages.put(None)

    def read_stderr():
        while True:
            block = process.stderr.read(4096)
            if not block:
                break
            if len(stderr) + len(block) > 65536:
                process.kill()
                break
            stderr.extend(block)

    readers = [threading.Thread(target=f, daemon=True) for f in (read_stdout, read_stderr)]
    for reader in readers:
        reader.start()
    timer = threading.Timer(120, lambda: process.kill() if process.poll() is None else None)
    timer.start()
    baseline = before = after = actor = result = None
    killed = False
    try:
        while True:
            line = messages.get(timeout=30)
            if line is None:
                break
            if isinstance(line, Exception):
                raise line
            require(len(events) < 8, "worker event count exceeded")
            event = json.loads(line)
            events.append(event)
            name = event["event"]
            require(name in GATES + ("result",), "unexpected worker event")
            require(all(event.get(flag) is False for flag in AUTHORITY_FLAGS)
                    and event.get("enabledProfiles") == 0, "unexpected event authority claim")
            require(event.get("noBackupRequested") == (mode == "no-backup"),
                    "wrong fixed mode observation")
            if name == "result":
                result = event
            if name == "ready":
                baseline = snapshot(root, captures, "ready")
                require((root / "target.bin").read_bytes() == OLD
                        and (root / "candidate.bin").read_bytes() == NEW
                        and (root / "unrelated.marker").read_bytes() == OTHER,
                        "initial authored markers differ")
                require("retained-original.bin" not in baseline, "retention already existed at ready")
            if name == gate:
                if action:
                    actor = perform(action, root)
                before = snapshot(root, captures, name + "-actor-or-stop")
                if kill:
                    process.kill()  # Only this exact owned child, waiting at a fixed gate.
                    process.wait(timeout=10)
                    killed = True
                    after = snapshot(root, captures, "after-kill")
                    break
            if name == "result":
                after = snapshot(root, captures, "result")
                process.stdin.write(b"exit\n")
            else:
                process.stdin.write(b"continue\n")
            process.stdin.flush()
        code = process.wait(timeout=10)
        for reader in readers:
            reader.join(timeout=2)
        require(not stderr, "unexpected worker stderr")
        require(baseline is not None and after is not None, "missing actual fixture observations")
        require(baseline["."]["identity"] == after["."]["identity"],
                "fresh root directory identity changed")
        current = before or baseline
        for leaf in ("target.bin", "candidate.bin", "unrelated.marker"):
            require(current[leaf] == after[leaf], "worker changed retained current/input entry")
        require((root / "target.bin").read_bytes() == OLD, "original target default bytes lost")
        require((root / "candidate.bin").read_bytes() == NEW, "candidate default bytes changed")
        require(baseline["unrelated.marker"] == after["unrelated.marker"], "unrelated entry changed")
        if killed:
            require(files_only(before) == files_only(after), "owned process kill changed fixture entries")
        else:
            require(code == 0 and result is not None, "worker failed unexpectedly")
            require(all(result.get(flag) is False for flag in AUTHORITY_FLAGS)
                    and result.get("enabledProfiles") == 0, "unexpected authority claim")
            require(result.get("renameSucceeded") is False, "strong guarded replacement unexpectedly succeeded")
            # Refusal may create its own bounded retention artifact, but it must
            # never change/delete pre-existing current, foreign or unrelated entries.
            for leaf, value in files_only(current).items():
                require(after.get(leaf) == value, "refusal changed an existing entry")
        if actor and action in ("target-write", "candidate-write", "original-write",
                                "target-rename", "candidate-rename", "original-rename", "root-rename"):
            require(actor["succeeded"] is False, "actor bypassed continuous byte/name hold")
        if action in ("original-foreign", "original-same-bytes", "original-directory",
                      "original-target-alias", "original-candidate-alias"):
            require(actor["succeeded"] and result and not result.get("renameAttempted"),
                    "occupied retained-original name did not refuse before replacement")
            require(result["original"].get("matchesRetainedOriginal") is not True,
                    "foreign retained name acquired owned custody")
        # No-backup has no early disposal permission: actual retained entries
        # survive both normal child exit and every owned process interruption.
        post_exit = snapshot(root, captures, "after-exit")
        require(after["."]["identity"] == post_exit["."]["identity"],
                "exit changed root directory identity")
        require(files_only(after) == files_only(post_exit), "exit removed or changed retained artifacts")
        retained = after.get("retained-original.bin")
        retained_bytes = None
        if retained and retained["kind"] == "file":
            retained_bytes = (root / "retained-original.bin").read_bytes()
        if not action and (not killed or gate in ("retention-written", "retention-synced", "precommit", "result")):
            require(retained_bytes == OLD, "complete original copy absent or wrong")
        if killed and gate == "retention-created":
            require(retained_bytes == b"", "created interruption should retain incomplete empty copy")
        if killed and gate == "ready":
            require(retained is None, "ready interruption unexpectedly created copy")
        if not action:
            last = events[-1]
            require(last["target"].get("matchesOriginalTarget") is True,
                    "worker lost actual original target identity")
            require(last["state"] == ("retained-current" if gate in ("ready", "retention-created")
                                      else "retained-current-and-original"),
                    "worker original/current classification differs from actual bounded state")
            if retained is not None:
                require(last["original"].get("matchesRetainedOriginal") is True,
                        "worker lost actual created retention identity")
        save(captures / "observations.private.json", {
            "id": case_id, "mode": mode, "gate": gate, "actor": actor,
            "events": events, "baseline": baseline, "before": before,
            "after": after, "postExit": post_exit, "exitCode": code})
        return {"id": case_id, "mode": mode, "gate": gate, "actor": actor,
                "ownedProcessKilled": killed, "originalTargetRetained": True,
                "candidateRetained": True, "unrelatedEntryRetained": True,
                "existingEntriesPreserved": True, "artifactsRetainedAfterExit": True,
                "retainedOriginalState": "absent" if retained is None else
                    "directory" if retained["kind"] == "directory" else
                    "complete-original-bytes" if retained_bytes == OLD else
                    "incomplete-empty" if retained_bytes == b"" else "foreign-bytes",
                "retainedCopyHasDistinctIdentity": None if retained is None else
                    retained["identity"] != baseline["target.bin"]["identity"],
                "renameAttempted": None if result is None else result.get("renameAttempted"),
                "renameSucceeded": False if result is None else result.get("renameSucceeded"),
                "refusalCode": None if result is None else result.get("refusalCode"),
                "osError": None if result is None else result.get("osError"),
                "productionReplacementAllowed": False, "committed": False}
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        for reader in readers:
            reader.join(timeout=2)
        save(captures / "events.private.json", events)
        with (captures / "stderr.private").open("xb") as stream:
            stream.write(stderr)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def run(binary, parent):
    binary, parent = Path(binary).resolve(), Path(parent).resolve()
    require(os.name == "nt", "native Windows required; no simulated success")
    require(parent.is_relative_to(REPO / ".local"), "fresh private fixtures must stay under .local")
    parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="retention-094-", dir=parent))
    sources = [*sorted(Path(__file__).parent.glob("*.py")), OBSERVER,
               *sorted((REPO / "experiments/0094-original-retention/src").glob("*.rs")),
               REPO / "experiments/0094-original-retention/Cargo.toml",
               REPO / "experiments/0094-original-retention/Cargo.lock"]
    identities = {"workerSha256": sha(binary), "pythonVersion": platform.python_version(),
                  "sources": {p.relative_to(REPO).as_posix(): sha(p) for p in sources}}
    save(scratch / "identities-before.private.json", identities)
    cases = []
    for mode in ("keep", "no-backup"):
        cases.append(execute(binary, scratch, "baseline-" + mode, mode))
        for gate in GATES + ("result",):
            cases.append(execute(binary, scratch, "kill-" + mode + "-" + gate, mode, gate, kill=True))
    for action in ("original-foreign", "original-same-bytes", "original-directory",
                   "original-target-alias", "original-candidate-alias", "target-write",
                   "candidate-write", "target-rename", "candidate-rename", "root-rename", "target-time"):
        cases.append(execute(binary, scratch, "ready-" + action, "no-backup", "ready", action))
    for action in ("original-write", "original-rename", "original-time", "original-readonly", "original-stream"):
        cases.append(execute(binary, scratch, "written-" + action, "no-backup", "retention-written", action))
    for gate in ("retention-synced", "precommit"):
        cases.append(execute(binary, scratch, gate + "-original-time", "no-backup", gate, "original-time"))
    admissions = negative_admissions(binary, scratch)
    require(sha(binary) == identities["workerSha256"]
            and all(sha(REPO / name) == digest for name, digest in identities["sources"].items()),
            "qualification source or worker changed during run")
    summary = {"schemaVersion": 1, "observedOn": "2026-10-15", "platform": platform.platform(),
               "identities": identities, "caseCount": len(cases), "cases": cases,
               "admissionRefusalCount": len(admissions), "admissionRefusals": admissions,
               "conditionalReplacementQualified": False, "restoreAllowed": False,
               "productionReplacementAllowed": False, "committed": False, "enabledProfiles": 0,
               "scope": "Fresh authored native markers; retained original bytes and held identities; owned process interruption only",
               "missing": ["conditional expected-target replacement", "full property coverage",
                           "full ancestor exclusion", "durability", "fresh guarded restore",
                           "automatic durable custody", "production storage profile"]}
    save(scratch / "summary.private.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--output", required=True, help="fresh sanitized derived summary")
    args = parser.parse_args()
    require(not Path(args.output).exists(), "derived summary destination must be fresh")
    save(args.output, run(args.binary, args.parent))

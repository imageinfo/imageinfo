"""Finite native fresh-name restore observations on newly owned authored markers.

The imported observer is read-only. Saved events and snapshots are evidence,
never authority for restore, publication, cleanup or replay.
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OBSERVER = REPO / "experiments/0093-conditional-replacement/qualify.py"
spec = importlib.util.spec_from_file_location("restore_readonly_observer", OBSERVER)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
require, save, sha, snapshot = observer.require, observer.save, observer.sha, observer.snapshot
NATIVE_OBSERVER = REPO / "experiments/0100-receipt-timestamps/native.py"
native_spec = importlib.util.spec_from_file_location("restore_native_readonly_observer", NATIVE_OBSERVER)
native_observer = importlib.util.module_from_spec(native_spec)
native_spec.loader.exec_module(native_observer)
_native = None


def shared_sha(path):
    """Existing reviewed reader shares DELETE with the creator-held candidate."""
    global _native
    if _native is None:
        _native = native_observer.Native()
    held = _native.open(path)
    try:
        return _native.observe(path, held)["sha256"]
    finally:
        _native.close(held)


# #0093's CRT hash open does not share DELETE. Only replace its read-only file
# hash operation; retain its independent namespace/security/stream observations.
observer.sha = shared_sha
ORIGINAL, LATER, OTHER = b"OLD108\n", b"LATER108\n", b"OTHER108\n"
ORIGINAL_NAME, CURRENT, UNRELATED = "retained-original.marker", "current.marker", "unrelated.marker"
CANDIDATE, DESTINATION = "restored-candidate.marker", "restored.marker"
GATES = ("captured", "guarded", "authorize-restore", "candidate-created", "candidate-synced", "prepublish", "published")
FLAGS = ("committed", "productionPublicationAllowed", "repairAllowed")


def files_only(state):
    return {name: value for name, value in state.items() if name != "."}


class Child:
    """Own just the fresh marker worker; bounded capture and exact controls."""
    def __init__(self, binary, root, mode):
        self.process = subprocess.Popen([str(binary), str(root), mode], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
        self.messages, self.stderr, self.events = queue.Queue(), bytearray(), []
        self.readers = [threading.Thread(target=f, daemon=True)
                        for f in (self._stdout, self._stderr)]
        for reader in self.readers:
            reader.start()
        self.timer = threading.Timer(120, self._kill_if_live)
        self.timer.start()

    def _kill_if_live(self):
        if self.process.poll() is None:
            self.process.kill()

    def _stdout(self):
        total = 0
        while True:
            line = self.process.stdout.readline(16385)
            if not line:
                break
            total += len(line)
            if len(line) > 16384 or total > 262144:
                self._kill_if_live()
                self.messages.put(ValueError("worker output bound exceeded"))
                break
            self.messages.put(line)
        self.messages.put(None)

    def _stderr(self):
        while True:
            block = self.process.stderr.read(4096)
            if not block:
                break
            if len(self.stderr) + len(block) > 65536:
                self._kill_if_live()
                break
            self.stderr.extend(block)

    def next(self):
        line = self.messages.get(timeout=30)
        if isinstance(line, Exception):
            raise line
        if line is None:
            return None
        require(len(self.events) < 32, "worker event count bound exceeded")
        event = json.loads(line)
        self.events.append(event)
        return event

    def send(self, choice="continue"):
        self.process.stdin.write((choice + "\n").encode())
        self.process.stdin.flush()

    def finish(self, captures):
        self.timer.cancel()
        self._kill_if_live()
        self.process.wait(timeout=10)
        for reader in self.readers:
            reader.join(timeout=2)
        save(captures / "events.private.json", self.events)
        with (captures / "stderr.private").open("xb") as stream:
            stream.write(self.stderr)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def perform(action, root):
    """Only fixed actors against the marker root this invocation just created."""
    try:
        operand, operation = action.rsplit(":", 1)
        path = root if operand == "root" else root / operand
        if operation in ("foreign", "same-bytes", "directory"):
            if operation == "directory":
                path.mkdir()
                (path / "foreign.marker").write_bytes(b"FOREIGN108\n")
            else:
                with path.open("xb") as stream:
                    stream.write(ORIGINAL if operation == "same-bytes" else b"FOREIGN108\n")
        elif operation == "write":
            with path.open("r+b") as stream:
                stream.write(b"FOREIGN108\n")
        elif operation == "rename":
            path.rename(path.with_name(path.name + "-displaced"))
        elif operation == "time":
            before = path.stat()
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        elif operation == "readonly":
            os.chmod(path, stat.S_IREAD)
        elif operation == "link":
            os.link(path, root / (path.name + "-alias"))
        elif operation == "stream":
            with Path(str(path) + ":foreign").open("xb") as stream:
                stream.write(b"ADS108\n")
        else:
            raise ValueError("unknown fixed marker actor")
        return {"action": action, "succeeded": True, "osError": None}
    except OSError as error:
        return {"action": action, "succeeded": False,
                "osError": getattr(error, "winerror", None), "errno": error.errno}


def execute(binary, scratch, case_id, mode="fresh-restore", gate=None, action=None, control=None):
    root, captures = scratch / case_id, scratch / (case_id + "-capture")
    captures.mkdir()
    child = Child(binary, root, mode)
    baseline = preservation = before_stop = result = actor = None
    killed = cancelled = False
    candidate_identity = None
    try:
        while True:
            event = child.next()
            if event is None:
                break
            require(all(event.get(flag, False) is False for flag in FLAGS), "worker claimed authority")
            name = event.get("barrier")
            if name:
                require(name in GATES, "unexpected restore barrier")
                if name == "captured":
                    baseline = snapshot(root, captures, "captured")
                    require((root / CURRENT).read_bytes() == LATER, "later current fixture differs")
                    require((root / UNRELATED).read_bytes() == OTHER, "unrelated fixture differs")
                if name == gate and action:
                    actor = perform(action, root)
                    preservation = snapshot(root, captures, "after-actor")
                if name == "prepublish":
                    preservation = snapshot(root, captures, "prepublish")
                    candidate_identity = preservation[CANDIDATE]["identity"]
                if name == gate and control:
                    if control != "crlf":
                        before_stop = snapshot(root, captures, "before-stop")
                    if control == "kill":
                        child.process.kill()  # Only this owned worker waiting at a fixed barrier.
                        child.process.wait(timeout=10)
                        killed = True
                        break
                    if control in ("eof-continue", "eof-authorization"):
                        child.process.stdin.write(b"continue" if control == "eof-continue" else b"restore-fresh")
                        child.process.stdin.close()
                    elif control == "eof":
                        child.process.stdin.close()
                    elif control == "crlf":
                        child.process.stdin.write(b"restore-fresh\r\n")
                        child.process.stdin.flush()
                    else:
                        child.send(control)
                    cancelled = control != "crlf"
                else:
                    child.send("restore-fresh" if name == "authorize-restore" else "continue")
            else:
                require(result is None, "duplicate restore result")
                result = event
        code = child.process.wait(timeout=10)
        for reader in child.readers:
            reader.join(timeout=2)
        require(baseline is not None, "worker did not capture an actual fixture")
        after = snapshot(root, captures, "after-exit")
        require(after["."]["identity"] == baseline["."]["identity"], "root identity changed")
        require(after[UNRELATED] == baseline[UNRELATED], "unrelated marker changed")
        require((root / CURRENT).read_bytes() == LATER or mode == "fresh-restore-stale-current",
                "later-edited current default bytes changed")
        if mode != "fresh-restore-stale-current":
            require(after[CURRENT] == (preservation or baseline)[CURRENT], "current version changed")
        if before_stop is not None:
            require(files_only(before_stop) == files_only(after), "stop changed retained artifacts")
        success = result is not None and result.get("outcome") == "restored-copy-observed"
        if success:
            require(code == 0 and not child.stderr and not cancelled and not killed,
                    "success process outcome differs")
            require(mode == "fresh-restore", "negative context acquired publication")
            require(DESTINATION in after and CANDIDATE not in after, "installed namespace differs")
            require((root / DESTINATION).read_bytes() == ORIGINAL, "restored default bytes differ")
            require(after[DESTINATION]["identity"] == candidate_identity, "held candidate identity lost")
            require(after[DESTINATION]["identity"] != after[ORIGINAL_NAME]["identity"]
                    and after[DESTINATION]["identity"] != after[CURRENT]["identity"],
                    "restore moved source or adopted current")
        elif not killed:
            require(result is not None or cancelled, "missing refusal result")
            require(DESTINATION not in after or action and action.startswith(DESTINATION + ":")
                    or mode == "fresh-restore-late-collision",
                    "refusal installed a destination")
        if mode == "fresh-restore-late-collision":
            require(result and result.get("publicationAttempted") is True
                    and result.get("outcome") == "recovery-required"
                    and (root / DESTINATION).read_bytes() == b"WINNER108\n"
                    and (root / CANDIDATE).read_bytes() == ORIGINAL,
                    "actual native no-replace collision did not retain winner/candidate")
        if preservation:
            for leaf, value in files_only(preservation).items():
                if leaf != CANDIDATE:
                    require(after.get(leaf) == value, "worker changed existing/foreign artifact")
        if actor and action.endswith((":write", ":rename")) and gate != "captured":
            require(actor["succeeded"] is False, "actor bypassed strong byte/name holds")
        if actor and actor["succeeded"]:
            require(not success, "successful conflicting actor acquired publication")
        save(captures / "observations.private.json", {
            "id": case_id, "mode": mode, "gate": gate, "actor": actor, "control": control,
            "events": child.events, "baseline": baseline, "preservation": preservation,
            "beforeStop": before_stop, "after": after, "exitCode": code,
            "candidateIdentity": candidate_identity})
        return {"id": case_id, "mode": mode, "gate": gate, "actor": actor, "control": control,
                "ownedProcessKilled": killed, "outcome": None if result is None else result.get("outcome"),
                "publicationAttempted": None if result is None else result.get("publicationAttempted"),
                "restoredCopyObserved": success, "currentTargetPreserved": True,
                "existingForeignEntriesPreserved": True, "allArtifactsRetainedAfterExit": True,
                "committed": False, "productionPublicationAllowed": False, "enabledProfiles": 0}
    finally:
        child.finish(captures)


def source_paths():
    crates = ("0032-windows-publication", "0028-recovery-evidence")
    paths = [HERE / "qualify.py", HERE / "audit.py", OBSERVER, NATIVE_OBSERVER, REPO / "rust-toolchain.toml"]
    for crate in crates:
        folder = REPO / "experiments" / crate
        paths += [folder / "Cargo.toml", folder / "Cargo.lock", *sorted((folder / "src").glob("*.rs"))]
    paths += [REPO / "experiments/0038-staging-cleanup/src" / name
              for name in ("staging.rs", "disposition.rs")]
    return paths


def admission_refusals(binary, scratch):
    cases = []
    for case_id, mode, reused in (("unknown-mode", "fresh-restore-untrusted", False),
                                 ("json-authority-mode", '{"restoreAllowed":true}', False),
                                 ("saved-context-existing-root", "fresh-restore", True)):
        root, captures = scratch / case_id, scratch / (case_id + "-capture")
        captures.mkdir()
        if reused:
            root.mkdir()
            (root / ORIGINAL_NAME).write_bytes(ORIGINAL)
            (root / CURRENT).write_bytes(LATER)
            save(root / "restore-context.json", {"owned": True, "priorActorStopped": True,
                                                 "restoreAllowed": True, "committed": True})
        before = snapshot(root, captures, "before") if reused else None
        process = subprocess.run([str(binary), str(root), mode], input=b"", capture_output=True,
                                 timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        require(len(process.stdout) <= 16384 and len(process.stderr) <= 65536,
                "admission output exceeded bound")
        events = [json.loads(line) for line in process.stdout.splitlines()]
        require(not any(event.get("barrier") for event in events), "saved/invalid input acquired live protocol")
        require(not any(event.get("outcome") == "restored-copy-observed" for event in events),
                "saved/invalid input acquired restoration")
        after = snapshot(root, captures, "after") if reused else None
        require(before == after and (reused or not root.exists()), "admission refusal changed fixture")
        save(captures / "observations.private.json", {"before": before, "after": after,
                                                     "exitCode": process.returncode, "events": events})
        with (captures / "stderr.private").open("xb") as stream:
            stream.write(process.stderr)
        cases.append({"id": case_id, "refusedBeforeLiveProtocol": True, "existingEntriesPreserved": True})
    return cases


def run(binary, parent):
    binary, parent = Path(binary).resolve(), Path(parent).resolve()
    require(os.name == "nt", "actual native Windows required")
    require(parent.is_relative_to(REPO / ".local"), "private fixtures must remain under .local")
    parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="restore108-", dir=parent))
    paths = source_paths()
    identities = {"workerSha256": sha(binary), "pythonVersion": platform.python_version(),
                  "sources": {p.relative_to(REPO).as_posix(): sha(p) for p in paths}}
    save(scratch / "identities-before.private.json", identities)
    cases = [execute(binary, scratch, "baseline"),
             execute(binary, scratch, "crlf-authorization", gate="authorize-restore", control="crlf")]
    for case_id, gate, control in (("truncated-continue", "captured", "eof-continue"),
                                   ("truncated-authorization", "authorize-restore", "eof-authorization"),
                                   ("ordinary-continue-not-authority", "authorize-restore", "continue"),
                                   ("json-not-authority", "authorize-restore", '{"restoreAllowed":true}')):
        cases.append(execute(binary, scratch, case_id, gate=gate, control=control))
    for suffix in ("stale-context", "wrong-root", "foreign-original", "same-byte-original",
                   "corrupt-original", "stale-current", "wrong-security", "late-collision"):
        cases.append(execute(binary, scratch, suffix, "fresh-restore-" + suffix))
    for gate in GATES:
        cases.append(execute(binary, scratch, "kill-" + gate, gate=gate, control="kill"))
    for gate in GATES[:-1]:
        for control in ("cancel", "eof"):
            cases.append(execute(binary, scratch, control + "-" + gate, gate=gate, control=control))
    for gate in ("captured", "prepublish"):
        for kind in ("foreign", "same-bytes", "directory"):
            cases.append(execute(binary, scratch, gate + "-destination-" + kind,
                                 gate=gate, action=DESTINATION + ":" + kind))
    for leaf, short in ((ORIGINAL_NAME, "original"), (CURRENT, "current")):
        for operation in ("write", "rename", "time", "readonly", "link", "stream"):
            cases.append(execute(binary, scratch, "guarded-" + short + "-" + operation,
                                 gate="guarded", action=leaf + ":" + operation))
    for leaf, short in ((CANDIDATE, "candidate"), ("root", "root")):
        for operation in (("write", "rename", "time", "readonly", "link", "stream")
                          if leaf == CANDIDATE else ("rename",)):
            cases.append(execute(binary, scratch, "synced-" + short + "-" + operation,
                                 gate="candidate-synced", action=leaf + ":" + operation))
    admissions = admission_refusals(binary, scratch)
    require(sha(binary) == identities["workerSha256"]
            and all(sha(REPO / name) == value for name, value in identities["sources"].items()),
            "worker or source changed during qualification")
    summary = {"schemaVersion": 1, "observedOn": "2026-10-15", "platform": platform.platform(),
               "identities": identities, "caseCount": len(cases), "cases": cases,
               "admissionRefusalCount": len(admissions), "admissionRefusals": admissions,
               "committed": False, "productionPublicationAllowed": False, "enabledProfiles": 0,
               "scope": "Fresh typed caller-owned authored markers; absolute no-replace publication; process termination only",
               "missing": ["external #0094 context import", "occupied-name restoration", "durable authority",
                           "full property backup", "namespace persistence", "production storage profile"]}
    save(scratch / "summary.private.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    require(not Path(args.output).exists(), "derived summary must be fresh")
    save(args.output, run(args.binary, args.parent))

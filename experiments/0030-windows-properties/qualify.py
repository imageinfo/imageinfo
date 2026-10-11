"""Supervise owned Windows marker cases; retain every scratch artifact/capture."""
import argparse
import json
import os
from pathlib import Path
import platform
import queue
import subprocess
import tempfile
import threading

HERE = Path(__file__).resolve().parent
BARRIERS = ["private-root-created", "candidate-flushed", "prepared-record-flushed",
            "intent-record-flushed", "before-publish", "validated-before-publish", "published",
            "output-file-flushed", "observation-record-flushed"]
MARKER = b"0" * 65536


def run(parent, guard=None):
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="imageinfo-properties-", dir=parent))
    if os.name != "nt":
        assert not list(scratch.iterdir())
        return {"schemaVersion": 1, "platform": platform.system(), "cases": [
            {"id": "unsupported-platform", "workerInvoked": False,
             "workerArtifacts": 0}], "enabledProfiles": 0,
             "productionPublicationAllowed": False}
    powershell = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    assert guard and Path(guard).is_file(), "Build the reviewed #0029 Windows guard first"
    guard = str(Path(guard).resolve())
    cases = []

    def actor(script, path):
        # Paths travel through the environment, never through executable code.
        env = dict(os.environ, IMAGEINFO_PROPERTY_ACTOR_PATH=str(path))
        result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command",
                                 "$ErrorActionPreference='Stop'; " + script], env=env,
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError("Owned property actor failed: " + result.stderr[:256])

    def execute(name, sharing="delete-share", intervention=None, stop=None, command="continue",
                operand=None, hold_parent=False):
        capture = scratch / (name + "-captures")
        capture.mkdir()
        root = scratch / name
        if operand is not None:
            root = operand
        argv = [powershell, "-NoProfile", "-NonInteractive", "-File", str(HERE / "worker.ps1"),
                "-Root", str(root), "-Sharing", sharing]
        (capture / "argv.json").write_text(json.dumps(argv), encoding="utf-8")
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        lines = queue.Queue()

        def read_lines():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()
        observed, controls, first_identity, first_times, guard_process = [], [], None, None, None
        try:
            while True:
                line = lines.get(timeout=30)
                if line is None:
                    break
                event = json.loads(line)
                observed.append(event)
                if "barrier" not in event:
                    continue
                barrier = event["barrier"]
                if barrier == "private-root-created" and hold_parent:
                    guard_argv = [guard, "hold-source", str(root / "parent-anchor.record")]
                    guard_process = subprocess.Popen(guard_argv, stdin=subprocess.PIPE,
                                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    guard_lines = queue.Queue()
                    threading.Thread(target=lambda: guard_lines.put(guard_process.stdout.readline()), daemon=True).start()
                    guard_first = guard_lines.get(timeout=30)
                    assert json.loads(guard_first)["barrier"] == "guard-held"
                    (capture / "guard-argv.json").write_text(json.dumps(guard_argv), encoding="utf-8")
                    (capture / "guard-first.jsonl").write_text(guard_first, encoding="utf-8")
                if barrier == "candidate-flushed":
                    stat = (root / "candidate.bin").stat()
                    first_identity = (stat.st_dev, stat.st_ino)
                    first_times = (stat.st_ctime_ns, stat.st_mtime_ns)
                if intervention:
                    intervention(barrier, root)
                if barrier == stop and command == "kill":
                    process.kill()  # Only this explicitly owned research child.
                    break
                reply = command if barrier == stop else "continue"
                controls.append(reply)
                process.stdin.write(reply + "\n")
                process.stdin.flush()
            process.wait(timeout=30)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
            reader.join(timeout=5)
            if guard_process:
                try:
                    guard_out, guard_err = guard_process.communicate("release\n", timeout=30)
                finally:
                    if guard_process.poll() is None:
                        guard_process.kill()
                        guard_process.wait(timeout=30)
                (capture / "guard-final.jsonl").write_text(guard_out, encoding="utf-8")
                (capture / "guard-stdin.txt").write_text("release\n", encoding="utf-8")
                assert guard_process.returncode == 0 and not guard_err
                assert json.loads(guard_out)["objectUnchanged"]
        stderr = process.stderr.read()
        (capture / "stdout.jsonl").write_text("\n".join(json.dumps(e) for e in observed) + "\n", encoding="utf-8")
        (capture / "stdin.txt").write_text("\n".join(controls) + "\n", encoding="utf-8")
        (capture / "stderr.txt").write_text(stderr, encoding="utf-8")
        assert not stderr, stderr[:256]
        for event in observed:
            assert event["productionPublicationAllowed"] is False
        final = observed[-1] if observed and "outcome" in observed[-1] else None
        if final:
            assert final["committed"] is False and final["namespaceAcknowledged"] is False
            assert process.returncode in (5, 130)
        else:
            assert command == "kill" and process.returncode != 0
        output = root / "output.bin"
        facts = {"id": name, "barriers": [e["barrier"] for e in observed if "barrier" in e],
                 "outputExists": output.exists(), "exitCode": process.returncode,
                 "outcome": final["outcome"] if final else "killed-no-outcome",
                 "diagnostic": final.get("diagnostic") if final else None,
                 "hresultLowWord": final.get("hresultLowWord") if final else None}
        if output.exists() and first_identity:
            stat = output.stat()
            facts["pathObservedIdentityMatchesStage"] = (stat.st_dev, stat.st_ino) == first_identity
            facts["completeMarkerVisible"] = output.read_bytes() == MARKER
            facts["postCloseTimesMatchStageSnapshot"] = (stat.st_ctime_ns, stat.st_mtime_ns) == first_times
        cases.append(facts)
        return root, facts

    _, strict = execute("strict-publication", sharing="strict")
    assert not strict["outputExists"] and strict["hresultLowWord"] == 32
    root, published = execute("delete-share-publication")
    assert published["barriers"] == BARRIERS and published["completeMarkerVisible"]
    assert published["pathObservedIdentityMatchesStage"]
    assert json.loads((root / "observation.record").read_text())["committed"] is False
    _, facts = execute("held-ancestors-publication", hold_parent=True)
    assert not facts["outputExists"] and facts["hresultLowWord"] == 32

    def collision(barrier, root):
        if barrier == "before-publish":
            (root / "output.bin").write_bytes(b"unrelated-winner")
    root, facts = execute("racing-destination", intervention=collision)
    assert (root / "output.bin").read_bytes() == b"unrelated-winner"
    assert (root / "candidate.bin").read_bytes() == MARKER
    assert facts["outcome"] == "recovery-required"

    for phase in ("before-publish", "published"):
        def writes(barrier, root, phase=phase):
            if barrier == phase:
                path = root / ("candidate.bin" if phase == "before-publish" else "output.bin")
                try:
                    path.write_bytes(b"poison")
                except OSError as error:
                    assert error.errno == 13
                else:
                    raise AssertionError("Unrelated content writer was allowed")
        _, facts = execute("write-refused-" + phase, intervention=writes)
        assert facts["completeMarkerVisible"]

    mutations = {
        "timestamp": None,
        "readonly": "[IO.File]::SetAttributes($env:IMAGEINFO_PROPERTY_ACTOR_PATH,[IO.FileAttributes]::ReadOnly)",
        "acl": "$p=$env:IMAGEINFO_PROPERTY_ACTOR_PATH; $s=[IO.File]::GetAccessControl($p); "
               "$r=[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),"
               "[Security.AccessControl.FileSystemRights]::Read,[Security.AccessControl.AccessControlType]::Allow); "
               "$s.AddAccessRule($r); [IO.File]::SetAccessControl($p,$s)",
        "stream": "python-stream",
    }
    for name, script in mutations.items():
        for phase in ("before-publish", "published"):
            def change(barrier, root, phase=phase, script=script):
                if barrier == phase:
                    path = root / ("candidate.bin" if phase == "before-publish" else "output.bin")
                    if script is None:
                        os.utime(path, (1000000000, 1000000000))
                    elif script == "python-stream":
                        Path(str(path) + ":extra").write_bytes(b"marker-only")
                    else:
                        actor(script, path)
            _, facts = execute(name + "-" + phase, intervention=change)
            assert facts["outputExists"] == (phase == "published")
            assert facts["diagnostic"] in ("PROPERTY_OR_CONTENT_DRIFT", "PROPERTY_ATTRIBUTES", "PROPERTY_ACL", "PROPERTY_STREAMS")

    def rename(barrier, root):
        if barrier == "before-publish":
            (root / "candidate.bin").rename(root / "moved-candidate.bin")
    root, facts = execute("delete-sharing-allows-rename", intervention=rename)
    assert not facts["outputExists"] and (root / "moved-candidate.bin").read_bytes() == MARKER

    def parent_rename(barrier, root):
        if barrier == "before-publish":
            try:
                root.rename(root.with_name(root.name + "-moved"))
            except OSError as error:
                assert error.winerror in (5, 32)
    root, facts = execute("unheld-parent-rename", intervention=parent_rename)
    facts["ordinaryParentRenameRefused"] = root.exists()
    if root.exists():
        assert facts["completeMarkerVisible"]
    else:
        assert not facts["outputExists"]
        assert (root.with_name(root.name + "-moved") / "candidate.bin").read_bytes() == MARKER

    def late_substitute(barrier, root):
        if barrier == "validated-before-publish":
            (root / "candidate.bin").rename(root / "held-candidate.bin")
            (root / "candidate.bin").write_bytes(b"foreign-late-candidate")
    root, facts = execute("late-named-stage-substitution", intervention=late_substitute)
    assert facts["outputExists"] and not facts["completeMarkerVisible"]
    assert not facts["pathObservedIdentityMatchesStage"]
    assert (root / "held-candidate.bin").read_bytes() == MARKER
    assert (root / "output.bin").read_bytes() == b"foreign-late-candidate"
    assert facts["outcome"] == "recovery-required" and facts["diagnostic"] != "NAMESPACE_ACK_UNVERIFIED"
    def matched_substitute(barrier, root):
        if barrier == "validated-before-publish":
            (root / "candidate.bin").rename(root / "held-candidate.bin")
            script = "$p=$env:IMAGEINFO_PROPERTY_ACTOR_PATH; $old=[IO.Path]::Combine([IO.Path]::GetDirectoryName($p),'held-candidate.bin'); " \
                     "$s=[IO.File]::GetAccessControl($old); $created=[IO.File]::GetCreationTimeUtc($old); $written=[IO.File]::GetLastWriteTimeUtc($old); " \
                     "$f=[IO.FileStream]::new($p,[IO.FileMode]::CreateNew,[Security.AccessControl.FileSystemRights]::Write,[IO.FileShare]::None,4096,[IO.FileOptions]::None,$s); " \
                     "try {$b=[byte[]]::new(65536); for($i=0;$i -lt $b.Length;$i++){$b[$i]=49}; $f.Write($b,0,$b.Length); $f.Flush($true)} finally {$f.Dispose()}; " \
                     "[IO.File]::SetCreationTimeUtc($p,$created); [IO.File]::SetLastWriteTimeUtc($p,$written)"
            actor(script, root / "candidate.bin")
    root, facts = execute("late-property-matched-substitution", intervention=matched_substitute)
    assert facts["outputExists"] and not facts["completeMarkerVisible"]
    assert not facts["pathObservedIdentityMatchesStage"]
    assert facts["diagnostic"] == "INSTALLED_CONTENT_DRIFT"
    assert (root / "held-candidate.bin").read_bytes() == MARKER
    def guarded_late_substitute(barrier, root):
        if barrier == "validated-before-publish":
            try:
                (root / "candidate.bin").rename(root / "held-candidate.bin")
            except OSError as error:
                assert error.winerror == 32
            else:
                raise AssertionError("Ancestor-held stage rename unexpectedly allowed")
    root, facts = execute("held-ancestors-late-substitution", intervention=guarded_late_substitute, hold_parent=True)
    assert not facts["outputExists"] and facts["hresultLowWord"] == 32
    assert (root / "candidate.bin").read_bytes() == MARKER

    _, facts = execute("held-ancestors-parent-rename", intervention=parent_rename, hold_parent=True)
    assert not facts["outputExists"] and facts["hresultLowWord"] == 32

    for barrier in BARRIERS:
        for command in ("fail", "kill"):
            root, facts = execute(command + "-" + barrier, stop=barrier, command=command)
            assert facts["outputExists"] == (BARRIERS.index(barrier) >= BARRIERS.index("published"))
            if facts["outputExists"]:
                assert facts["completeMarkerVisible"] and facts["pathObservedIdentityMatchesStage"]
            if (root / "candidate.bin").exists():
                assert (root / "candidate.bin").read_bytes() == MARKER
    _, facts = execute("cancel-before-publish", stop="before-publish", command="cancel")
    assert not facts["outputExists"] and facts["exitCode"] == 130
    _, facts = execute("cancel-after-publish", stop="published", command="cancel")
    assert facts["outputExists"] and facts["exitCode"] == 5

    existing = scratch / "preexisting-root"
    existing.mkdir()
    (existing / "foreign.bin").write_bytes(b"retain-me")
    _, facts = execute("preexisting-root", operand=existing)
    assert facts["diagnostic"] == "ROOT_EXISTS" and list(existing.iterdir()) == [existing / "foreign.bin"]
    for name, operand in [("relative-path", Path("relative-unsupported")),
                          ("unc-path", Path(r"\\localhost\unverified\root")),
                          ("stream-path", Path(str(scratch / "colon") + ":extra"))]:
        _, facts = execute(name, operand=operand)
        assert facts["diagnostic"] == "PATH_UNVERIFIED" and not facts["barriers"]

    report = {"schemaVersion": 1, "platform": platform.platform(), "cases": cases,
              "caseCount": len(cases), "enabledProfiles": 0, "productionPublicationAllowed": False,
              "namespaceAcknowledged": False, "OSCrashRuns": 0, "powerLossRuns": 0,
              "data": "authored 64 KiB marker; no private RAW files", "storage": "fixed local NTFS",
              "retention": "all owned scratch/captures retained; no cleanup or repair"}
    first_events = [json.loads(line) for line in (scratch / "delete-share-publication-captures/stdout.jsonl").read_text(encoding="utf-8").splitlines()]
    report["runtime"] = first_events[0]["runtime"]
    (scratch / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--guard", help="Reviewed #0029 binary, required on Windows")
    args = parser.parse_args()
    print(json.dumps(run(args.parent, args.guard), indent=2))

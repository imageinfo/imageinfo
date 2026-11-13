"""Authored result evidence and refusal controls without a guest or QMP."""

import base64
import copy
from contextlib import nullcontext
import http.client
import os
from pathlib import Path, PureWindowsPath
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import console_result as result


def context(attempt):
    owner = {"pid": 501}
    return {
        "schema": "imageinfo-0219-console-context-v1", "attempt": str(attempt),
        "unit": "authored_unit", "case": "persistent-write-error", "control": r"C:\I219Authored",
        "guest_launcher": r"C:\authored_unit-launch.ps1", "launcher_uri": "http://10.0.2.2:18739/launch.ps1",
        "launcher_sha256": "1" * 64, "config_sha256": "2" * 64, "owner": owner,
        "owner_sha256": result.digest(result.encode(owner)), "boot_ms": 1234, "result_port": 18749,
        "request": {"bindings": {"plan_sha256": "3" * 64}, "volume_plan_sha256": "4" * 64},
        "request_sha256": "5" * 64, "bootstrap_sha256": "6" * 64, "python_sha256": "7" * 64,
        "collector_sha256": "8" * 64, "driver_pid": 501, "vm_pid": 502,
        "deadline_monotonic_ns": time.monotonic_ns() + 60000000000,
    }


def screen_fixture(attempt, data):
    screen = attempt / "console-screen.ppm"
    image = b"P6\n1 1\n255\n\x01\x02\x03"
    screen.write_bytes(image)
    row = {**result.binding(data), "schema": "imageinfo-0219-console-screen-v1",
           "screen": str(screen), "screen_sha256": result.digest(image)}
    (attempt / "console-screen.json").write_bytes(result.encode(row))
    return row


def capture_fixture(data):
    readiness = {"administrator": False, "mediumIntegrity": True, "manufacturer": "QEMU"}
    files = {
        "result.json": result.encode({"schema": "imageinfo-0219-bootstrap-v1", "collectorPid": 101,
                                      "collectorExitConfirmed": True, "collectorExitCode": 0, "failed": False,
                                      "productionAdmission": False, "rawMutationAdmission": False,
                                      "readiness": readiness}),
        "pid.json": result.encode({"schema": "imageinfo-0219-bootstrap-pid-v1", "collectorPid": 101}),
        "start.json": result.encode({"schema": "imageinfo-0219-bootstrap-start-v1",
                                     "caller": "explicit-current-owning-parent", "readiness": readiness,
                                     "bootstrapSha256": data["bootstrap_sha256"], "pythonSha256": data["python_sha256"],
                                     "collectorSha256": data["collector_sha256"], "requestSha256": data["request_sha256"],
                                     "diagnosticPlanSha256": data["request"]["bindings"]["plan_sha256"],
                                     "volumePlanSha256": data["request"]["volume_plan_sha256"]}),
        "runtime.json": result.encode({"schema": "imageinfo-0219-python-runtime-v1", "exit_confirmed": True,
                                       "exit_code": 0, "failed": False, "executable_sha256": data["python_sha256"],
                                       "expected_version": "3.14.7"}),
        "stdout.txt": b"", "stderr.txt": b"",
    }
    captures = [capture_entry(data, name, content) for name, content in files.items()]
    value = {**result.binding(data), "schema": "imageinfo-0219-console-result-v2", "captures": captures,
             "screen_sha256": data["screen_sha256"], "launcher_sha256": data["launcher_sha256"],
             "ordinary_user": True, "launch_invoked": True, "boot_before_ms": 1234, "boot_after_ms": 1234,
             "operator_error": None, "inspection_error": None, "collector_pid": 101,
             "pid_query_completed": True, "pid_present": False}
    return value, files


def capture_entry(data, name, content):
    return {"name": name, "path": str(PureWindowsPath(data["control"]) / "bootstrap-capture" / name),
            "bytes": len(content), "sha256": result.digest(content), "base64": base64.b64encode(content).decode()}


class ResultTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.attempt = Path(temporary.name)
        self.data = context(self.attempt)
        (self.attempt / "console-context.json").write_bytes(result.encode(self.data))
        self.screen = screen_fixture(self.attempt, self.data)

    def test_preparation_binds_context_screen_and_command(self):
        with patch.object(result, "verify_current_files"):
            record = result.prepare(self.data)
            with self.assertRaises(FileExistsError):
                result.prepare(self.data)
        observed, typed, prepared_sha = result.load_preparation(self.data)
        self.assertEqual(observed, record)
        self.assertEqual(observed["screen_sha256"], self.screen["screen_sha256"])
        self.assertEqual(observed["context_sha256"], result.digest(result.encode(self.data)))
        self.assertEqual(observed["typed_sha256"], result.digest(typed.encode()))
        self.assertEqual(len(prepared_sha), 64)
        Path(self.screen["screen"]).write_bytes(b"different authored screen")
        with self.assertRaisesRegex(ValueError, "screen bytes differ"):
            result.load_preparation(self.data)

    def test_result_refuses_absence_only_replayed_and_partial_evidence(self):
        bound = {**self.data, "screen_sha256": self.screen["screen_sha256"]}
        value, files = capture_fixture(bound)
        self.assertEqual(result.audit_capture(value, bound), files)
        for key, changed in (("screen_sha256", "f" * 64), ("owner_sha256", "f" * 64), ("boot_after_ms", 1235),
                             ("pid_present", True), ("pid_query_completed", False), ("collector_pid", 102),
                             ("captures", value["captures"][:-1]), ("launch_invoked", False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                result.audit_capture({**value, key: changed}, bound)
        altered = copy.deepcopy(value)
        result_capture = result.decode(files["result.json"])
        result_capture["collectorExitConfirmed"] = False
        altered["captures"][0] = capture_entry(bound, "result.json", result.encode(result_capture))
        with self.assertRaisesRegex(ValueError, "owned collector exit"):
            result.audit_capture(altered, bound)

    def test_acknowledged_input_must_bind_actual_preparation(self):
        record, _, _ = result.preparation(self.data)
        prepared_sha = result.digest(result.encode(record))
        path = self.attempt / "console-input-complete.json"
        with self.assertRaises(ValueError):
            result.require_completed_input(self.data, record, prepared_sha)
        row = result.readiness_record(self.data, record, prepared_sha)
        del row["result_port"]
        row["schema"] = "imageinfo-0219-console-input-complete-v1"
        path.write_bytes(result.encode(row))
        result.require_completed_input(self.data, record, prepared_sha)
        path.write_bytes(result.encode({**row, "prepared_sha256": "f" * 64}))
        with self.assertRaisesRegex(ValueError, "input binding differs"):
            result.require_completed_input(self.data, record, prepared_sha)

    @unittest.skipUnless(os.name == "posix", "Linux proc descriptor semantics")
    def test_proc_metadata_refuses_changed_process(self):
        root = self.attempt
        proc = root / "501"
        proc.mkdir()
        exe = root / "expected-executable"
        exe.write_bytes(b"authored executable bytes")
        (proc / "exe").symlink_to(exe)
        argv = [str(exe), "authored argument"]
        fields = b"501 (authored ) process) S " + b"0 " * 18
        metadata = {"stat": fields + b"99 0\n", "cmdline": b"\0".join(os.fsencode(x) for x in argv) + b"\0",
                    "status": b"Uid:\t1000\t1000\t1000\t1000\n"}
        for name, content in metadata.items():
            (proc / name).write_bytes(content)
        result.verify_process(501, 99, str(exe), argv, root, executable_sha256=result.digest(exe.read_bytes()))
        for name, content in (("stat", fields + b"100 0\n"), ("cmdline", b"different\0"),
                              ("status", b"Uid:\t1000\t1000\t0\t1000\n")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                (proc / name).write_bytes(content)
                try:
                    result.verify_process(501, 99, str(exe), argv, root)
                finally:
                    (proc / name).write_bytes(metadata[name])
        with self.assertRaisesRegex(ValueError, "executable differs"):
            result.verify_process(501, 99, str(root / "other-executable"), argv, root)

    def test_operator_script_parses_without_execution(self):
        import shutil

        parser = shutil.which("pwsh") or shutil.which("powershell")
        if parser is None:
            self.skipTest("PowerShell parser unavailable")
        _, script, _ = result.preparation(self.data)
        text = base64.b64encode(script).decode("ascii")
        command = ("$s=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + text + "'));"
                   "$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseInput($s,[ref]$t,[ref]$e)"
                   "|Out-Null;if($e.Count){$e|Out-String|Write-Error;exit 1}")
        completed = subprocess.run([parser, "-NoProfile", "-NonInteractive", "-Command", command],
                                   capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        self.assertIn(b"owner_sha256='" + self.data["owner_sha256"].encode() + b"'", script)
        self.assertIn(b"screen_sha256='" + self.screen["screen_sha256"].encode() + b"'", script)

    def test_compact_fetch_checks_download_before_exclusive_guest_file_creation(self):
        _, _, typed = result.preparation(self.data)
        fetch = base64.b64decode(typed.rsplit(" ", 1)[1], validate=True).decode("utf-16le")
        self.assertLess(fetch.index(".RawContentStream.ToArray()"), fetch.index("throw 'Pin'"))
        self.assertLess(fetch.index("throw 'Pin'"), fetch.index("[IO.File]::Open($p,'CreateNew')"))
        self.assertIn("$ErrorActionPreference='Stop'", fetch)

    def test_real_bounded_http_observer_rejects_early_and_partial_result(self):
        for case in ("success", "before-input", "ack-race", "stale-ack", "partial", "wrong-route"):
            with self.subTest(case=case):
                attempt = self.attempt / case
                attempt.mkdir()
                data = context(attempt)
                with socket.socket() as available:
                    available.bind(("127.0.0.1", 0))
                    data["result_port"] = available.getsockname()[1]
                (attempt / "console-context.json").write_bytes(result.encode(data))
                screen = screen_fixture(attempt, data)
                directory = attempt / "console-preparation"
                outcomes = []

                def run_observer():
                    try:
                        outcomes.append(result.observe(data, approved_context_sha256=record["context_sha256"],
                                                       approved_prepared_sha256=prepared_sha,
                                                       parent_screen_sha256=screen["screen_sha256"],
                                                       parent_confirmed_idle_console=True))
                    except (OSError, ValueError) as exc:
                        outcomes.append(exc)

                def write_artifact(parent, name, raw, **kwargs):
                    result.write(parent / name, raw)

                with (patch.object(result, "root_inspector"), patch.object(result, "verify_current_files"),
                      patch.object(result, "verify_live_processes"),
                      patch.object(result, "result_directory", side_effect=nullcontext),
                      patch.object(result, "write_result", side_effect=write_artifact),
                      patch.object(result, "INPUT_ACK_WAIT", 0.25)):
                    record = result.prepare(data)
                    prepared_sha = result.digest(result.encode(record))
                    thread = threading.Thread(target=run_observer, daemon=True)
                    thread.start()
                    wait_until = time.monotonic() + 5
                    while not (directory / "result-ready.json").exists() and thread.is_alive() and time.monotonic() < wait_until:
                        time.sleep(0.01)
                    self.assertTrue((directory / "result-ready.json").exists(), outcomes)
                    def publish_input():
                        marker = result.readiness_record(data, record, prepared_sha)
                        marker.pop("result_port")
                        marker["schema"] = "imageinfo-0219-console-input-complete-v1"
                        if case == "stale-ack":
                            marker["prepared_sha256"] = "a" * 64
                        pending = attempt / "input.pending"
                        pending.write_bytes(result.encode(marker))
                        pending.rename(attempt / "console-input-complete.json")

                    if case not in ("before-input", "ack-race"):
                        publish_input()
                    capture, _ = capture_fixture({**data, "screen_sha256": screen["screen_sha256"]})
                    body = result.encode(capture)
                    port = data["result_port"]
                    route = "/result/" + data["unit"]
                    if case in ("before-input", "ack-race", "stale-ack"):
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                        try:
                            connection.request("GET", record["operator_route"])
                            if case == "ack-race":
                                self.assertFalse((attempt / "console-input-complete.json").exists())
                                with self.assertRaises(TimeoutError):
                                    connection.sock.settimeout(0.05)
                                    connection.sock.recv(1)
                                publish_input()
                                connection.sock.settimeout(5)
                            response = connection.getresponse()
                            if case == "ack-race":
                                self.assertEqual(response.status, 200)
                                self.assertEqual(result.digest(response.read()), record["operator_sha256"])
                                connection.request("POST", route, body)
                                response = connection.getresponse()
                                self.assertEqual(response.status, 200)
                            else:
                                self.assertEqual(response.status, 409)
                            response.read()
                        finally:
                            connection.close()
                    elif case == "partial":
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                        try:
                            connection.request("GET", record["operator_route"])
                            response = connection.getresponse()
                            self.assertEqual(response.status, 200)
                            response.read()
                        finally:
                            connection.close()
                        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
                            client.sendall(f"POST {route} HTTP/1.0\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body[:10])
                            client.shutdown(socket.SHUT_WR)
                            self.assertIn(b"400", client.recv(1024).split(b"\r\n", 1)[0])
                    else:
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                        try:
                            connection.request("GET", record["operator_route"])
                            response = connection.getresponse()
                            self.assertEqual(response.status, 200)
                            self.assertEqual(result.digest(response.read()), record["operator_sha256"])
                            connection.request("POST", route if case != "wrong-route" else route + "-old", body)
                            response = connection.getresponse()
                            self.assertEqual(response.status, 200 if case == "success" else 400)
                            response.read()
                        finally:
                            connection.close()
                    thread.join(5)
                    self.assertFalse(thread.is_alive())
                self.assertEqual(len(outcomes), 1)
                if case in ("success", "ack-race"):
                    observed = outcomes[0]
                    self.assertFalse(observed["driver_stdin_written"])
                    self.assertNotIn("stdin_token_for_parent", observed)
                    self.assertEqual(result.digest(Path(observed["audit"]).read_bytes()), observed["audit_sha256"])
                    self.assertEqual(result.digest(Path(observed["capture"]).read_bytes()), observed["capture_sha256"])
                else:
                    self.assertIsInstance(outcomes[0], (ValueError, OSError))
                    self.assertTrue((directory / "inspection-failure.json").is_file())
                    self.assertFalse((directory / "inspection-audit.json").exists())
                    with patch.object(result, "read_result_marker", side_effect=result.read):
                        with self.assertRaisesRegex(ValueError, "observer already refused"):
                            result.load_readiness(data, record, prepared_sha)


if __name__ == "__main__":
    unittest.main()

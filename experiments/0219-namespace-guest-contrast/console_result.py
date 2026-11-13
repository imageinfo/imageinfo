"""Prepare and observe one current console attempt without console control."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import http.server
import json
import os
from pathlib import Path, PureWindowsPath
import re
import socket
import stat
import threading
import time


CAPTURES = ('result.json', 'pid.json', 'start.json', 'runtime.json', 'stdout.txt', 'stderr.txt')
MAX_CAPTURE = 262144
MAX_POST = 2097152
MAX_SCREEN = 16777216
INPUT_ACK_WAIT = 4.5
HEX = re.compile(r"[0-9a-f]{64}\Z")
UNIT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    value = {}
    for key, item in items:
        need(key not in value, "duplicate JSON field")
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError("invalid JSON constant: " + value)


def decode(raw):
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def read(path, bound=1048576):
    path = Path(path)
    need(path.is_absolute() and not path.is_symlink() and path.is_file(), "absolute plain file required")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        need(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "plain file required")
        raw = stream.read(bound + 1)
    need(len(raw) <= bound, "input byte bound")
    return raw


def write(path, raw):
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def ps(value):
    need(type(value) is str and not any(ch in value for ch in "\r\n\x00"), "single-line PowerShell literal required")
    return "'" + value.replace("'", "''") + "'"


def operator_script(data):
    # All paths/routes below are fixed, reviewed current-cell values. The result
    # inspector reads only six bootstrap captures and one exact process ID.
    control = ps(data['control'])
    unit = ps(data['unit'])
    boot = str(data['boot_ms'])
    launcher = ps(data['guest_launcher'])
    pin = ps(data['launcher_sha256'])
    cfg = ps(data['config_sha256'])
    template = """$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$unit219=UNIT
$control219=CONTROL
$expectedBoot219=[Int64]BOOT
$record219=[ordered]@{schema='imageinfo-0219-console-result-v2';unit=$unit219;config_sha256=CONFIG;owner_sha256=OWNER;screen_sha256=SCREEN;launcher_sha256=PIN;boot_before_ms=$null;boot_after_ms=$null;ordinary_user=$false;launch_invoked=$false;operator_error=$null;inspection_error=$null;collector_pid=$null;pid_query_completed=$false;pid_present=$null;captures=@()}
function Boot219 {
 $os219=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
 return ([DateTimeOffset]$os219.LastBootUpTime.ToUniversalTime()).ToUnixTimeMilliseconds()
}
function Capture219([string]$Name) {
 $p219=Join-Path (Join-Path $control219 'bootstrap-capture') $Name
 $i219=Get-Item -LiteralPath $p219 -Force -ErrorAction Stop
 if($i219.PSIsContainer -or ($i219.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $i219.Length -gt 262144){throw 'Capture is not a bounded plain file'}
 $b219=[IO.File]::ReadAllBytes($p219)
 if($b219.Length -gt 262144){throw 'Capture changed beyond bound'}
 $h219=[Security.Cryptography.SHA256]::Create()
 try{$s219=([BitConverter]::ToString($h219.ComputeHash($b219))).Replace('-','').ToLowerInvariant()}finally{$h219.Dispose()}
 $record219.captures+=,[ordered]@{name=$Name;path=$p219;bytes=$b219.Length;sha256=$s219;base64=[Convert]::ToBase64String($b219)}
 return ,$b219
}
try {
 $machine219=Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
 $principal219=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if($machine219.Manufacturer -ne 'QEMU' -or $machine219.Model -notmatch 'Q35' -or $principal219.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Ordinary QEMU guest required'}
 $record219.ordinary_user=$true
 $record219.boot_before_ms=Boot219
 if($record219.boot_before_ms -ne $expectedBoot219){throw 'Guest boot changed before launch'}
 $launcher219=LAUNCHER
 if(Test-Path -LiteralPath $launcher219){throw 'Retain prior launcher; no replay'}
 Invoke-WebRequest URI -UseBasicParsing -TimeoutSec 15 -OutFile $launcher219
 if((Get-FileHash -LiteralPath $launcher219 -Algorithm SHA256).Hash.ToLowerInvariant() -cne PIN){throw 'Actual driver launcher pin mismatch'}
 $record219.launch_invoked=$true
 & $launcher219
} catch {$record219.operator_error=$_.Exception.Message}
finally {
 try {
  $record219.boot_after_ms=Boot219
  if($record219.boot_after_ms -ne $expectedBoot219){throw 'Guest boot changed after launch'}
  $rawResult219=Capture219 'result.json'
  $rawPid219=Capture219 'pid.json'
  $null=Capture219 'start.json';$null=Capture219 'runtime.json';$null=Capture219 'stdout.txt';$null=Capture219 'stderr.txt'
  $utf219=New-Object Text.UTF8Encoding($false,$true)
  $result219=$utf219.GetString($rawResult219) | ConvertFrom-Json
  $pidRecord219=$utf219.GetString($rawPid219) | ConvertFrom-Json
  if($null -eq $result219.collectorPid -or $result219.collectorPid -lt 1 -or $result219.collectorPid -gt 4294967295 -or $pidRecord219.collectorPid -ne $result219.collectorPid){throw 'Exact collector PID capture missing'}
  $record219.collector_pid=[Int64]$result219.collectorPid
  $process219=@(Get-CimInstance Win32_Process -Filter ('ProcessId='+$record219.collector_pid) -ErrorAction Stop)
  $record219.pid_query_completed=$true
  $record219.pid_present=($process219.Count -ne 0)
 } catch {$record219.inspection_error=$_.Exception.Message}
 $body219=[Text.Encoding]::UTF8.GetBytes(($record219 | ConvertTo-Json -Depth 24 -Compress))
 if($body219.Length -gt 2097152){throw 'Inspection POST exceeds bound'}
 $null=Invoke-RestMethod POSTURI -Method Post -ContentType 'application/json' -Body $body219 -TimeoutSec 15
}
"""
    values = dict(POSTURI=ps(data["post_uri"]), LAUNCHER=launcher, CONTROL=control,
                  CONFIG=cfg, OWNER=ps(data["owner_sha256"]), SCREEN=ps(data["screen_sha256"]),
                  UNIT=unit, BOOT=boot, URI=ps(data["launcher_uri"]), PIN=pin)
    return re.sub(r"\b(?:POSTURI|LAUNCHER|CONTROL|CONFIG|OWNER|SCREEN|UNIT|BOOT|URI|PIN)\b",
                  lambda match: values[match.group()], template).encode()



def read_context(data):
    attempt = Path(data["attempt"])
    need(attempt.is_absolute() and not attempt.is_symlink() and attempt.is_dir(),
         "current attempt directory required")
    raw = read(attempt / "console-context.json")
    need(data.get("schema") == "imageinfo-0219-console-context-v1" and raw == encode(data),
         "current runner context changed")
    return digest(raw)


def binding(data):
    need(type(data["unit"]) is str and UNIT.fullmatch(data["unit"]), "invalid console unit")
    for key in ("config_sha256", "owner_sha256"):
        need(type(data[key]) is str and HEX.fullmatch(data[key]), "invalid console digest: " + key)
    return {key: data[key] for key in ("unit", "config_sha256", "owner_sha256")}


def current_screen(data):
    attempt = Path(data["attempt"])
    row = decode(read(attempt / "console-screen.json"))
    need(type(row) is dict and row.get("schema") == "imageinfo-0219-console-screen-v1"
         and all(row.get(key) == value for key, value in binding(data).items()),
         "current owner screen binding differs")
    screen = Path(row["screen"])
    need(screen == attempt / "console-screen.ppm" and screen.resolve(strict=True).parent == attempt.resolve(strict=True),
         "screen must be a plain file inside the current attempt")
    raw = read(screen, MAX_SCREEN)
    need(bool(raw) and digest(raw) == row["screen_sha256"], "current screen bytes differ")
    return {key: row[key] for key in ("screen", "screen_sha256")}


def verified_inputs(data):
    raw = read(data["bindings"])
    need(digest(raw) == data["config_sha256"], "approved driver config bytes differ")
    config = decode(raw)
    inputs = {}
    for key in ("plan", "freeze", "review", "payload_zip", "payload_pins", "bootstrap", "readiness_capture"):
        limit = 67108864 if key == "payload_zip" else 1048576
        inputs[key] = read(config[key], limit)
        need(digest(inputs[key]) == config["input_sha256"][key], "approved input bytes changed: " + key)
    plan = decode(inputs["plan"])
    frozen = decode(inputs["freeze"])
    need(data["checked_snapshot"] == {"checked": {"plan": plan, "freeze": frozen}},
         "approved inspection snapshot differs")
    root = Path(frozen["root"]).resolve(strict=True)
    need(root == Path(config["source_root"]).resolve(strict=True), "approved source root differs")
    for entry in frozen["sources"]:
        target = (root / entry["path"]).resolve(strict=True)
        need(target.is_relative_to(root), "source path escapes approved root")
        verify_file(entry, target, 4194304)
    for entry in [frozen["worker"], *frozen["inputs"].values()]:
        verify_file(entry, entry["path"], 268435456 if entry is frozen["worker"] else 1048576)
    return config, plan, inputs


def verify_file(entry, path, bound):
    raw = read(path, bound)
    need(len(raw) == entry["bytes"] and digest(raw) == entry["sha256"], "approved file bytes changed")


def verify_current_files(data):
    config, plan, inputs = verified_inputs(data)
    planned_owner = plan["console_owner"]
    owner = data["owner"]
    need(all(owner.get(key) == planned_owner[key] for key in ("runtime", "code_sha256", "sources"))
         and digest(encode(owner)) == data["owner_sha256"], "current reviewed owner binding differs")
    source_root = Path(config["owner_source_root"])
    owner_sources = ("owner_entry.py", "host_runner.py", "console_transport.py", "console_result.py")
    need(set(owner["sources"]) == set(owner_sources) and data["driver"] == str(source_root / "host_runner.py"),
         "current reviewed owner inventory differs")
    for name in owner_sources:
        need(digest(read(source_root / name, 4194304)) == owner["sources"][name], "current owner source changed: " + name)
    case = data["case"]
    cell = next(item for item in config["cells"] if item["case"] == case)
    selected = next(item for item in plan["cases"] if item["case"] == case)
    attempt = Path(config["pair_root"]) / cell["attempt_name"]
    need(attempt == Path(data["attempt"]) and selected["unit"] == data["unit"]
         and cell["guest_control_directory"] == data["control"] and config["result_port"] == data["result_port"]
         and config["port"] != data["result_port"],
         "current reviewed attempt or port differs")
    disk_entry = data["checked_snapshot"]["checked"]["freeze"]["inputs"]["disk_configuration"]
    disk_raw = read(disk_entry["path"])
    need(disk_entry["path"] == plan["freeze_inputs"]["disk_configuration"]
         and digest(disk_raw) == disk_entry["sha256"], "current disk configuration differs")
    disk = decode(disk_raw)
    launch = disk["capture_bindings"]["launch"]
    launch_raw = read(launch["path"])
    need(digest(launch_raw) == launch["sha256"]
         and decode(launch_raw)["launch"]["argv"] == data["vm_argv"]
         and selected.get("identities", plan["identities"])["guest"]["vm_pid"] == data["vm_pid"]
         and config["vm_start_ticks"] == data["vm_start_ticks"]
         and str(Path(data["vm_argv"][0]).resolve(strict=True)) == data["vm_executable"]
         and data["qmp_socket"] == config["qmp_socket"], "current reviewed VM launch binding differs")
    readiness = decode(inputs["readiness_capture"])
    boot = re.fullmatch(r"/Date\(([0-9]+)\)/", readiness["os"]["LastBootUpTime"])
    need(boot and int(boot[1]) == data["boot_ms"], "current reviewed boot differs")
    request_raw = read(attempt / "request.json", MAX_CAPTURE)
    request = decode(request_raw)
    need(request == data["request"] and digest(request_raw) == data["request_sha256"]
         and request["unit"] == data["unit"] and request["case"] == case
         and request["bindings"]["plan_sha256"] == digest(inputs["plan"])
         and request["bindings"]["freeze_sha256"] == digest(inputs["freeze"]), "actual guest request differs")
    payload = PureWindowsPath(config["guest_stage_directory"]) / "payload"
    pins = request["reviewed_files"]
    for source in ("bootstrap", "python", "collector"):
        need(data[source + "_sha256"] == pins[str(payload / config["guest_" + source + "_relative"])],
             "current reviewed guest file differs: " + source)
    need(data["bootstrap_sha256"] == digest(inputs["bootstrap"]), "actual bootstrap pin differs")
    launcher = read(attempt / "launcher.ps1")
    need(digest(launcher) == data["launcher_sha256"]
         and data["launcher_uri"] == f"http://10.0.2.2:{config['port']}/launch.ps1"
         and data["guest_launcher"] == str(PureWindowsPath(data["control"]).parent / (data["unit"] + "-launch.ps1")),
         "current launcher bytes or binding differs")
    ledger = read(attempt / "host.jsonl", 16777216)
    need(ledger.endswith(b"\n"), "current host journal has a partial line")
    rows = [decode(line) for line in ledger.splitlines()]
    assets = [row["value"] for row in rows if row["kind"] == "http-assets"]
    resident = [row["value"] for row in rows if row["kind"] == "resident"]
    need(len(assets) == len(resident) == 1 and not any(row["kind"] == "guest-event" for row in rows),
         "one current controller with no guest event required")
    need(assets[0]["port"] == config["port"] and
         assets[0]["assets"]["/launch.ps1"] == {"bytes": len(launcher), "sha256": digest(launcher)}
         and resident[0]["pid"] == data["driver_pid"] == data["owner"]["pid"], "actual controller/asset binding differs")
    if case == "no-error":
        first = Path(config["pair_root"]) / config["cells"][0]["attempt_name"]
        first_unit = plan["cases"][0]["unit"]
        prior = decode(read(first / "audit.json"))
        confirmation = decode(read(first / "collector-exit-confirmation.json"))
        need(prior.get("passed") is True and prior.get("case") == "persistent-write-error" and prior.get("unit") == first_unit
             and prior.get("plan_sha256") == digest(inputs["plan"]) and prior.get("freeze_sha256") == digest(inputs["freeze"])
             and confirmation.get("unit") == first_unit and confirmation.get("collector_exit_confirmed") is True
             and type(confirmation.get("collector_exit_code")) is int and confirmation["collector_exit_code"] == 0,
             "first cell actual collector confirmation/audit missing")


def preparation(data):
    context_sha256 = read_context(data)
    screen = current_screen(data)
    port = data["result_port"]
    need(type(port) is int and 1024 <= port <= 65535, "separate finite result port required")
    route = "/" + data["unit"] + "-operator.ps1"
    post_route = f"http://10.0.2.2:{port}/result/{data['unit']}"
    script = operator_script({**data, **screen, "post_uri": post_route})
    guest_operator = ps("C:\\I219-" + data["unit"] + "-operator.ps1")
    operator_uri = ps(f"http://10.0.2.2:{port}{route}")
    script_pin = digest(script)
    fetch = (f"$ErrorActionPreference='Stop';$p={guest_operator};"
             f"$b=(Invoke-WebRequest {operator_uri} -UseBasicParsing -TimeoutSec 15).RawContentStream.ToArray();"
             "$h=[Security.Cryptography.SHA256]::Create();try{$s=[BitConverter]::ToString($h.ComputeHash($b)).Replace('-','')}"
             f"finally{{$h.Dispose()}};if($s -ine {ps(script_pin)}){{throw 'Pin'}};"
             "$f=[IO.File]::Open($p,'CreateNew');try{$f.Write($b,0,$b.Length)}finally{$f.Dispose()};& $p")
    typed = ("powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand "
             + base64.b64encode(fetch.encode("utf-16le")).decode("ascii"))
    need(len(typed) <= 1800 and re.fullmatch(r"[A-Za-z0-9 ./+=-]+", typed),
         "compact bounded console command required")
    record = {**binding(data), **screen, "schema": "imageinfo-0219-console-preparation-v2",
              "context_sha256": context_sha256, "owner": data["owner"], "result_port": port,
              "operator_sha256": script_pin, "operator_route": route, "typed_sha256": digest(typed.encode()),
              "key_count": len(typed), "importable_authority": False}
    return record, script, typed


def prepare(data):
    verify_current_files(data)
    record, script, typed = preparation(data)
    directory = Path(data["attempt"]) / "console-preparation"
    directory.mkdir(exist_ok=False)
    write(directory / "operator.ps1", script)
    write(directory / "typed-command.txt", typed.encode() + b"\n")
    write(directory / "prepared.json", encode(record))
    return record


def load_preparation(data):
    expected, script, typed = preparation(data)
    directory = Path(data["attempt"]) / "console-preparation"
    need(not directory.is_symlink(), "current preparation directory required")
    raw = read(directory / "prepared.json")
    need(raw == encode(expected) and read(directory / "operator.ps1") == script
         and read(directory / "typed-command.txt", 16384) == typed.encode() + b"\n", "prepared source or current binding differs")
    return expected, typed, digest(raw)


def readiness_record(data, prepared, prepared_sha256):
    return {**binding(data), "schema": "imageinfo-0219-console-result-ready-v1",
            "screen_sha256": prepared["screen_sha256"], "prepared_sha256": prepared_sha256,
            "typed_sha256": prepared["typed_sha256"], "result_port": data["result_port"]}


def load_readiness(data, prepared, prepared_sha256):
    directory = Path(data["attempt"]) / "console-preparation"
    row = decode(read_result_marker(directory / "result-ready.json"))
    need(row == readiness_record(data, prepared, prepared_sha256), "current result readiness differs")
    need(not os.path.lexists(directory / "inspection-failure.json"), "current result observer already refused")
    return row


def load_result_audit(data, prepared, prepared_sha256):
    directory = Path(data["attempt"]) / "console-preparation"
    audit = decode(read_result_marker(directory / "inspection-audit.json"))
    expected = readiness_record(data, prepared, prepared_sha256)
    expected["schema"] = "imageinfo-0219-console-result-audit-v1"
    need(all(audit.get(key) == value for key, value in expected.items())
         and audit.get("passed") is True and audit.get("eligible_for_explicit_parent_confirmation") is True
         and audit.get("actual_boot_ms") == data["boot_ms"]
         and type(audit.get("collector_pid")) is int and 0 < audit["collector_pid"] < 2**32
         and type(audit.get("capture_sha256")) is str and HEX.fullmatch(audit["capture_sha256"])
         and audit.get("driver_stdin_written") is False, "current successful collector inspection required")
    return audit

def root_inspector():
    need(os.name == "posix" and os.geteuid() == 0, "root /proc inspector required")


def read_result_marker(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_mode & 0o022 == 0,
             "root-owned result marker required")
        raw = stream.read(MAX_CAPTURE + 1)
    need(len(raw) <= MAX_CAPTURE, "result marker bound")
    return raw


def process_ticks(raw, pid):
    # Linux comm may contain spaces and parentheses. Start time is stat field 22.
    head, separator, tail = raw.rpartition(b") ")
    fields = tail.split()
    need(separator and head.startswith(str(pid).encode() + b" (") and len(fields) >= 20
         and fields[0] not in (b"X", b"Z") and fields[19].isdigit(), "current live process stat required")
    return int(fields[19])


def read_process_entry(directory, name, limit=65536):
    with os.fdopen(os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory), "rb") as stream:
        need(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "plain proc entry required")
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, "process metadata bound")
    return raw


def verify_process(pid, start_ticks, executable, argv, proc_root=Path("/proc"), *, executable_sha256=None):
    need(type(pid) is int and pid > 0 and type(start_ticks) is int and start_ticks > 0
         and type(executable) is str and Path(executable).is_absolute()
         and type(argv) is list and argv and all(type(item) is str and "\x00" not in item for item in argv),
         "complete expected live process binding required")
    directory = os.open(proc_root / str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        need(process_ticks(read_process_entry(directory, "stat"), pid) == start_ticks, "current process start ticks differ")
        need(os.readlink("exe", dir_fd=directory) == executable, "current process executable differs")
        if executable_sha256 is not None:
            with os.fdopen(os.open("exe", os.O_RDONLY | os.O_NONBLOCK, dir_fd=directory), "rb") as stream:
                info = os.fstat(stream.fileno())
                need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 268435456,
                     "current interpreter binary bound")
                raw = stream.read(info.st_size + 1)
            need(len(raw) == info.st_size and digest(raw) == executable_sha256,
                 "current process interpreter bytes differ")
        actual = read_process_entry(directory, "cmdline")
        need(actual == b"\0".join(os.fsencode(item) for item in argv) + b"\0", "current process argv differs")
        uids = [line.split()[1:] for line in read_process_entry(directory, "status").splitlines()
                if line.startswith(b"Uid:")]
        need(uids == [[b"1000"] * 4], "current ordinary process owner differs")
        need(process_ticks(read_process_entry(directory, "stat"), pid) == start_ticks,
             "process changed during correspondence checks")
    finally:
        os.close(directory)


def verify_live_processes(data):
    owner = data["owner"]
    need(digest(encode(owner)) == data["owner_sha256"] and owner["uid"] == 1000
         and owner["pid"] == data["driver_pid"] != data["vm_pid"],
         "current loaded owner binding differs")
    need(data["driver"] in owner["argv"] and data["bindings"] in owner["argv"],
         "current owning runner entry point differs")
    verify_process(owner["pid"], owner["start_ticks"], owner["runtime"]["executable"], owner["argv"],
                   executable_sha256=owner["runtime"]["executable_sha256"])
    pidfile = Path(data["qmp_socket"]).parent / "qemu.pid"
    need(int(read(pidfile, 64)) == data["vm_pid"], "current VM PID file differs")
    verify_process(data["vm_pid"], data["vm_start_ticks"], data["vm_executable"], data["vm_argv"])


def audit_capture(value, data):
    need(type(value) is dict and value.get("schema") == "imageinfo-0219-console-result-v2"
         and all(value.get(key) == data[key] for key in (*binding(data), "launcher_sha256", "screen_sha256")),
         "inspection correspondence differs")
    items = value.get("captures")
    need(type(items) is list and len(items) == len(CAPTURES), "inspection capture denominator differs")
    files = {}
    for item in items:
        need(type(item) is dict, "inspection capture must be an object")
        name = item.get("name")
        need(name in CAPTURES and name not in files, "unknown or duplicate capture")
        raw = base64.b64decode(item["base64"], validate=True)
        need(base64.b64encode(raw).decode("ascii") == item["base64"] and len(raw) <= MAX_CAPTURE
             and type(item["bytes"]) is int and len(raw) == item["bytes"] and digest(raw) == item["sha256"]
             and item["path"] == str(PureWindowsPath(data["control"]) / "bootstrap-capture" / name),
             "actual capture byte/path binding differs")
        files[name] = raw
    need(value["ordinary_user"] is True and value["launch_invoked"] is True
         and type(value["boot_before_ms"]) is int and type(value["boot_after_ms"]) is int
         and value["boot_before_ms"] == value["boot_after_ms"] == data["boot_ms"]
         and value["operator_error"] is None and value["inspection_error"] is None,
         "launch, boot or inspection incomplete")
    result, pid, start, runtime = (decode(files[name]) for name in CAPTURES[:4])
    for record, schema in ((result, "imageinfo-0219-bootstrap-v1"), (pid, "imageinfo-0219-bootstrap-pid-v1"),
                           (start, "imageinfo-0219-bootstrap-start-v1"), (runtime, "imageinfo-0219-python-runtime-v1")):
        need(type(record) is dict and record.get("schema") == schema, "actual bootstrap capture schema differs")
    actual_pid = result.get("collectorPid")
    need(type(actual_pid) is int and 0 < actual_pid < 2**32 and type(pid.get("collectorPid")) is int
         and type(value["collector_pid"]) is int and pid["collectorPid"] == value["collector_pid"] == actual_pid
         and result.get("collectorExitConfirmed") is True and type(result.get("collectorExitCode")) is int
         and result["collectorExitCode"] == 0 and result.get("failed") is False
         and value["pid_query_completed"] is True and value["pid_present"] is False,
         "owned collector exit and current PID absence required")
    request = data["request"]
    need(start.get("requestSha256") == data["request_sha256"]
         and start.get("diagnosticPlanSha256") == request["bindings"]["plan_sha256"]
         and start.get("volumePlanSha256") == request["volume_plan_sha256"], "actual bootstrap request/plan binding differs")
    for key in ("python", "collector", "bootstrap"):
        need(start.get(key + "Sha256") == data[key + "_sha256"], "actual bootstrap source/runtime pin differs")
    need(runtime.get("exit_confirmed") is True and type(runtime.get("exit_code")) is int and runtime["exit_code"] == 0
         and runtime.get("failed") is False and runtime.get("executable_sha256") == data["python_sha256"]
         and runtime.get("expected_version") == "3.14.7", "actual runtime child did not exit successfully")
    for capture in (start, result):
        readiness = capture.get("readiness", {})
        need(readiness.get("manufacturer") == "QEMU" and readiness.get("administrator") is False
             and readiness.get("mediumIntegrity") is True, "actual bootstrap ordinary-user capture differs")
    need(start.get("caller") == "explicit-current-owning-parent" and result.get("productionAdmission") is False
         and result.get("rawMutationAdmission") is False, "actual caller/admission limits differ")
    return files


def require_completed_input(data, prepared, prepared_sha256, *, wait_until=None):
    marker = Path(data["attempt"]) / "console-input-complete.json"
    while True:
        try:
            marker.lstat()
            raw = read(marker)
            break
        except FileNotFoundError:
            remaining = 0 if wait_until is None else wait_until - time.monotonic()
            need(remaining > 0, "current acknowledged input marker absent or expired")
            time.sleep(min(0.025, remaining))
    row = decode(raw)
    expected = readiness_record(data, prepared, prepared_sha256)
    del expected["result_port"]
    expected["schema"] = "imageinfo-0219-console-input-complete-v1"
    need(row == expected, "current acknowledged input binding differs")
    need(wait_until is None or time.monotonic() < wait_until, "current acknowledged input marker expired")


def write_result(directory_fd, name, content, *, runner_readable=False):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    pending = name + ".pending"
    descriptor = os.open(pending, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            if runner_readable:
                os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        os.link(pending, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd, follow_symlinks=False)
    finally:
        os.unlink(pending, dir_fd=directory_fd)


@contextmanager
def result_directory(path):
    directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield directory_fd
    finally:
        os.close(directory_fd)


def observe(data, *, approved_context_sha256, approved_prepared_sha256, parent_screen_sha256,
            parent_confirmed_idle_console):
    root_inspector()
    need(parent_confirmed_idle_console is True, "current parent must confirm an observed idle ordinary console")
    need(read_context(data) == approved_context_sha256, "approved current context bytes differ")
    verify_current_files(data)
    prepared, _, prepared_sha256 = load_preparation(data)
    need(prepared_sha256 == approved_prepared_sha256 and prepared["screen_sha256"] == parent_screen_sha256,
         "current parent approved preparation/screen differs")
    verify_live_processes(data)
    script = operator_script({**data, "screen_sha256": prepared["screen_sha256"],
                              "post_uri": f"http://10.0.2.2:{data['result_port']}/result/{data['unit']}"})
    need(digest(script) == prepared["operator_sha256"], "current operator source differs")
    directory = Path(data["attempt"]) / "console-preparation"
    with result_directory(directory) as directory_fd:
        return serve_result(data, prepared, prepared_sha256, script, directory_fd)


def serve_result(data, prepared, prepared_sha256, script, directory_fd):
    ready = readiness_record(data, prepared, prepared_sha256)
    deadline = time.monotonic() + 480
    capture = None
    failure = None
    requests = 0
    operator_sent = False
    failure_retained = False

    def retain_failure(exc):
        nonlocal failure, failure_retained
        if failure_retained:
            return
        failure = exc
        failure_record = {**ready, "schema": "imageinfo-0219-console-result-audit-v1", "passed": False,
                          "error_type": type(exc).__name__, "retry_allowed": False, "driver_stdin_written": False}
        write_result(directory_fd, "inspection-failure.json", encode(failure_record), runner_readable=True)
        failure_retained = True

    class ResultHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def setup(self):
            nonlocal requests
            super().setup()
            requests += 1
            if requests > 8:
                retain_failure(ValueError("inspection request bound"))
            self.connection_deadline = min(time.monotonic() + 5, deadline)
            wait = max(0, self.connection_deadline - time.monotonic())
            self.connection.settimeout(wait)

            def expire():
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            self.timer = threading.Timer(wait, expire)
            self.timer.daemon = True
            self.timer.start()

        def finish(self):
            self.timer.cancel()
            super().finish()

        def reply(self, status, body):
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True

        def do_GET(self):
            nonlocal operator_sent
            if failure is not None:
                self.reply(429, b"bounded endpoint\n")
                return
            if self.path != prepared["operator_route"]:
                self.reply(404, b"unknown\n")
                return
            try:
                need(not operator_sent, "replayed operator download")
                ack_deadline = min(time.monotonic() + INPUT_ACK_WAIT, self.connection_deadline,
                                   data["deadline_monotonic_ns"] / 1_000_000_000)
                require_completed_input(data, prepared, prepared_sha256, wait_until=ack_deadline)
                self.reply(200, script)
                operator_sent = True
            except (ValueError, KeyError, OSError) as exc:
                retain_failure(exc)
                try:
                    self.reply(409, b"refused\n")
                except OSError:
                    pass

        def do_POST(self):
            nonlocal capture
            try:
                need(failure is None, "inspection request bound")
                lengths = self.headers.get_all("Content-Length", [])
                need(self.path == "/result/" + data["unit"] and operator_sent and capture is None
                     and len(lengths) == 1 and lengths[0].isascii() and lengths[0].isdigit()
                     and len(lengths[0]) <= len(str(MAX_POST)) and self.headers.get("Transfer-Encoding") is None,
                     "wrong or replayed result route/framing")
                length = int(lengths[0])
                need(0 < length <= MAX_POST and time.monotonic() < deadline, "inspection byte/deadline bound")
                require_completed_input(data, prepared, prepared_sha256)
                raw = self.rfile.read(length)
                need(len(raw) == length and time.monotonic() < deadline, "partial or expired inspection body")
                write_result(directory_fd, "inspection-capture.json", raw)
                capture = (decode(raw), digest(raw))
                self.reply(200, b"{}\n")
            except (ValueError, KeyError, OSError) as exc:
                retain_failure(exc)
                try:
                    self.reply(400, b"refused\n")
                except OSError:
                    pass

    try:
        need(time.monotonic_ns() < data["deadline_monotonic_ns"], "runner readiness deadline expired")
        with http.server.HTTPServer(("127.0.0.1", data["result_port"]), ResultHandler) as server:
            need(time.monotonic_ns() < data["deadline_monotonic_ns"], "runner readiness deadline expired")
            intent = {**ready, "schema": "imageinfo-0219-console-result-intent-v1", "driver_pid": data["driver_pid"],
                      "vm_pid": data["vm_pid"], "parent_confirmed_idle_console": True,
                      "driver_stdin_written": False}
            write_result(directory_fd, "inspection-intent.json", encode(intent))
            write_result(directory_fd, "result-ready.json", encode(ready), runner_readable=True)
            while capture is None and failure is None:
                remaining = deadline - time.monotonic()
                need(remaining > 0, "inspection deadline expired; collector exit remains unknown")
                server.timeout = min(0.1, remaining)
                server.handle_request()
        if failure is not None:
            raise failure
        value, capture_sha256 = capture
        files = audit_capture(value, {**data, "screen_sha256": prepared["screen_sha256"]})
        for name, raw in files.items():
            write_result(directory_fd, "bootstrap-" + name, raw)
        audit = {**ready, "schema": "imageinfo-0219-console-result-audit-v1", "passed": True,
                 "capture_sha256": capture_sha256, "eligible_for_explicit_parent_confirmation": True,
                 "actual_boot_ms": data["boot_ms"], "collector_pid": value["collector_pid"], "driver_stdin_written": False}
        write_result(directory_fd, "inspection-audit.json", encode(audit), runner_readable=True)
        directory = Path(data["attempt"]) / "console-preparation"
        return {"status": "actual-bootstrap-and-PID-inspected", "driver_stdin_written": False,
                "capture": str(directory / "inspection-capture.json"), "capture_sha256": capture_sha256,
                "audit": str(directory / "inspection-audit.json"), "audit_sha256": digest(encode(audit))}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        retain_failure(exc)
        raise

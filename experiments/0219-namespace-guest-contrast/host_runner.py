"""Maintained current-parent runner for the two-cell namespace guest contrast."""
from __future__ import annotations
import argparse
import base64
import builtins
import hashlib
import importlib.util
import marshal
import platform
import types
import json
import os
from pathlib import Path, PureWindowsPath
import re
import secrets
import socket
import struct
import sys
import time

CASES = ("persistent-write-error", "no-error")
FLAGS = ("committed", "production_profile_admitted", "raw_admitted", "authority_importable")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_JSON = 1048576
OWNER_MODULES = ('host_runner.py', 'console_transport.py', 'console_result.py')
OWNER_SOURCES = (*OWNER_MODULES, 'owner_entry.py')
EXPERIMENT = 'experiments/0219-namespace-guest-contrast'
CORE_MODULES = tuple(f'{folder}/{name}.py' for folder, names in (
    (EXPERIMENT, ('freeze', 'audit', 'host_controller', 'protocol')),
    ('experiments/0218-namespace-observer', ('freeze', 'audit', 'protocol')),
) for name in names)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def read(path, bound=MAX_JSON):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "absolute plain input required")
    with path.open("rb") as stream:
        data = stream.read(bound + 1)
    require(len(data) <= bound, "input byte bound")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def new_file(path, data):
    # A failed/partial output is retained. No overwrite, replay, or retry.
    with Path(path).open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def new_json(path, value):
    new_file(path, encode(value))


def load(name, path, raw, *, import_module=builtins.__import__, attrs=None):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__dict__.update(attrs or {})
    module.__dict__['__builtins__'] = dict(vars(builtins), __import__=import_module)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def capture_core(root, frozen):
    pins = {row['path']: row['sha256'] for row in frozen['sources']}
    captured = {}
    for relative in CORE_MODULES:
        path = root / relative
        raw = read(path, 4 * MAX_JSON)
        require(digest(raw) == pins.get(relative), 'core Python source changed: ' + relative)
        captured[path] = raw
    external = frozen['inputs']['controller_source']
    controller_path = Path(external['path']).resolve(strict=True)
    controller = read(controller_path)
    require(controller == captured[root / EXPERIMENT / 'host_controller.py']
            and digest(controller) == external['sha256'], 'controller source pin changed')
    # The unchanged core uses explicit spec loaders for its local imports.
    # Give those modules only the already captured, named dependency bytes.
    class CapturedLoader:
        def __init__(self, path):
            self.path = path

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.__dict__['__builtins__'] = dict(vars(builtins), __import__=import_core)
            exec(compile(captured[self.path], str(self.path), 'exec', dont_inherit=True), module.__dict__)

    def spec_from_file_location(name, location):
        path = Path(location).resolve(strict=True)
        require(path in captured, 'unbound frozen core import')
        return importlib.util.spec_from_file_location(name, path, loader=CapturedLoader(path))

    def import_core(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'importlib.util' and level == 0:
            require(not fromlist, 'unbound frozen core import form')
            return types.SimpleNamespace(util=types.SimpleNamespace(
                spec_from_file_location=spec_from_file_location,
                module_from_spec=importlib.util.module_from_spec))
        return import_standard(name, globals, locals, fromlist, level)

    def core_module(filename, attrs=None):
        path = root / EXPERIMENT / filename
        return load('imageinfo_frozen_' + filename[:-3], path, captured[path], import_module=import_core, attrs=attrs)

    host = core_module('host_controller.py', {
        '__resident_source_sha256__': digest(controller), '__resident_source_bytes_count__': len(controller),
        '__file__': str(controller_path),
    })
    return core_module('freeze.py'), core_module('audit.py'), host, {**captured, controller_path: controller}


def import_standard(name, globals=None, locals=None, fromlist=(), level=0):
    require(level == 0 and name.partition('.')[0] in sys.stdlib_module_names, 'unbound owner import: ' + name)
    return builtins.__import__(name, globals, locals, fromlist, level)


def runtime_identity():
    executable = Path('/proc/self/exe').resolve(strict=True) if os.name == 'posix' else Path(sys.executable).resolve(strict=True)
    return {'implementation': sys.implementation.name, 'version': platform.python_version(),
            'cache_tag': sys.implementation.cache_tag, 'platform': sys.platform, 'executable': str(executable),
            'executable_sha256': digest(read(executable, 128 * MAX_JSON)), 'optimize': sys.flags.optimize,
            'marshal_version': marshal.version}


def process_identity():
    raw = read('/proc/self/cmdline', 65536)
    require(raw.endswith(b'\0'), 'current runner argv framing')
    stat = read('/proc/self/stat', 4096)
    ticks = int(stat.rsplit(b') ', 1)[1].split()[19])
    return {'pid': os.getpid(), 'argv': [os.fsdecode(arg) for arg in raw[:-1].split(b'\0')],
            'start_ticks': ticks, 'uid': os.geteuid()}


def code_value(value):
    if isinstance(value, types.CodeType):
        return ['code', value.co_name, value.co_qualname, value.co_argcount, value.co_posonlyargcount,
                value.co_kwonlyargcount, value.co_nlocals, value.co_stacksize, value.co_flags,
                value.co_code.hex(), value.co_names, value.co_varnames, value.co_freevars, value.co_cellvars,
                value.co_firstlineno, value.co_linetable.hex(), value.co_exceptiontable.hex(),
                [code_value(item) for item in value.co_consts]]
    if isinstance(value, tuple):
        return ['tuple', [code_value(item) for item in value]]
    if isinstance(value, frozenset):
        return ['frozenset', sorted((code_value(item) for item in value), key=encode)]
    if isinstance(value, bytes):
        return ['bytes', value.hex()]
    return [type(value).__name__, repr(value)]


def live_entries(modules):
    objects, values = {}, {}

    def function(label, value):
        depth = 0
        while isinstance(value, types.FunctionType):
            require(depth < 8, 'owner decorator chain bound')
            objects[label] = value
            values[label] = code_value(value.__code__)
            for name, cell in zip(value.__code__.co_freevars, value.__closure__ or ()):
                captured = cell.cell_contents
                if isinstance(captured, types.FunctionType) and captured is not getattr(value, '__wrapped__', None):
                    function(label + ':closure:' + name, captured)
            value = getattr(value, '__wrapped__', None)
            label += ':wrapped'
            depth += 1

    for filename, module in sorted(modules.items()):
        objects[filename] = module
        for name, value in sorted(vars(module).items()):
            if getattr(value, '__module__', None) != module.__name__:
                continue
            label = filename + ':' + name
            if isinstance(value, type):
                objects[label] = value
                for member, method in sorted(vars(value).items()):
                    if isinstance(method, (staticmethod, classmethod)):
                        method = method.__func__
                    if isinstance(method, types.FunctionType):
                        function(label + '.' + member, method)
            elif isinstance(value, types.FunctionType):
                function(label, value)
    return objects, digest(encode(values))


class Attestation:
    def __init__(self, root, expected, modules):
        self.root, self.expected, self.modules = root, expected, modules
        self.objects, code_sha = live_entries(modules)
        self.owner = {'schema': 'imageinfo-0219-console-owner-v1', **process_identity(),
                      'sources': dict(expected['sources']), 'runtime': runtime_identity(), 'code_sha256': code_sha,
                      'modules': {filename: module.__name__ for filename, module in modules.items()}}
        self.sha256 = digest(encode(self.owner))
        self.core = {}
        self.revalidate()

    def revalidate(self):
        objects, code_sha = live_entries(self.modules)
        require(objects.keys() == self.objects.keys() and all(value is self.objects[key] for key, value in objects.items())
                and code_sha == self.owner['code_sha256'], 'loaded owner callable or code changed')
        require(runtime_identity() == self.owner['runtime'] == self.expected['runtime']
                and all(self.owner[key] == value for key, value in process_identity().items()),
                'current owner runtime or process changed')
        require(code_sha == self.expected['code_sha256'] and digest(encode(self.owner)) == self.sha256,
                'loaded owner does not match reviewed code/binding')
        for name, sha in self.owner['sources'].items():
            require(digest(read(self.root / name, 4 * MAX_JSON)) == sha, 'loaded owner source changed: ' + name)
        for path, raw in self.core.items():
            require(read(path, 4 * MAX_JSON) == raw, 'loaded frozen core source changed')


def winpath(value):
    require(type(value) is str and PureWindowsPath(value).is_absolute()
            and '..' not in PureWindowsPath(value).parts and not any(c in value for c in '\r\n\x00\"'),
            "canonical absolute Windows guest path required")
    return value


def ps(value):
    require(type(value) is str and not any(c in value for c in '\r\n\x00'), "single-line PowerShell literal required")
    return "'" + value.replace("'", "''") + "'"


def unknowns(value, path="config"):
    if value is None or (type(value) is str and (not value or value.startswith("UNKNOWN"))):
        return [path]
    if type(value) is dict:
        return [p for key, item in value.items() for p in unknowns(item, path + "." + key)]
    if type(value) is list:
        return [p for index, item in enumerate(value) for p in unknowns(item, path + "." + str(index))]
    return []


def bind_audited_inputs(raw, inputs):
    require(all(inputs.get(key + "_sha256") == digest(raw[key]) for key in ("plan", "freeze", "review")),
            "auditor reread selected different captured plan/freeze/review bytes")


def owner_spec(config, plan):
    root = Path(config['owner_source_root'])
    require(root.is_absolute() and root == root.resolve(strict=True), 'canonical maintained owner source directory required')
    expected = plan['console_owner']
    require(type(expected) is dict and set(expected) == {'sources', 'runtime', 'code_sha256'}
            and type(expected['sources']) is dict and set(expected['sources']) == set(OWNER_SOURCES)
            and all(type(sha) is str and HEX.fullmatch(sha) for sha in (*expected['sources'].values(), expected['code_sha256']))
            and type(expected['runtime']) is dict, 'exact reviewed owner sources, code and runtime required')
    return root, expected


def inspect(config_path, *, expected_raw=None):
    config_raw = read(config_path)
    require(expected_raw is None or config_raw == expected_raw,
            "driver config changed between current-parent approval and inspection")
    config = decode(config_raw)
    require(type(config) is dict and config.get("schema") == "imageinfo-0219-sole-owner-driver-v2", "driver config schema")
    require(not unknowns(config), "unknown factual input: " + ", ".join(unknowns(config)))
    required = {"schema", "source_root", "plan", "freeze", "review", "qmp_socket", "pair_root", "port",
                "payload_zip", "payload_pins", "bootstrap", "guest_stage_directory", "guest_python_relative",
                "guest_collector_relative", "guest_bootstrap_relative", "guest_python_version", "readiness_capture",
                "cells", "input_sha256", "owner_source_root", "result_port", "vm_start_ticks"}
    require(set(config) == required, "driver fields differ")
    require(type(config["port"]) is int and 1024 <= config["port"] <= 65535, "HTTP port bound")
    require(type(config['result_port']) is int and 1024 <= config['result_port'] <= 65535
            and config['result_port'] != config['port'], 'separate finite result HTTP port required')
    require(type(config['vm_start_ticks']) is int and config['vm_start_ticks'] > 0, 'reviewed VM start ticks required')
    require(type(config["input_sha256"]) is dict, "exact private input hashes required")
    file_keys = ("plan", "freeze", "review", "payload_zip", "payload_pins", "bootstrap", "readiness_capture")
    require(set(config["input_sha256"]) == set(file_keys), "private input hash denominator")
    raw = {}
    for key in file_keys:
        raw[key] = read(config[key], 64 * 1048576 if key == "payload_zip" else MAX_JSON)
        require(HEX.fullmatch(config["input_sha256"][key]) is not None
                and digest(raw[key]) == config["input_sha256"][key], "private input changed: " + key)
    readiness = decode(raw["readiness_capture"])
    require(readiness.get("schema") == "imageinfo-0219-readiness-capture-v1" and readiness.get("success") is True
            and all(readiness.get(k) is False for k in ("diagnosticExecuted", "sourceMoved", "faultArmed")),
            "actual successful readiness capture required")
    source_root = Path(config['source_root'])
    require(source_root.is_absolute() and source_root == source_root.resolve(strict=True)
            and source_root.is_dir(), 'canonical immutable published source root required')
    directory = source_root / "experiments/0219-namespace-guest-contrast"
    frozen = decode(raw['freeze'])
    freezer, auditor, host, core = capture_core(source_root, frozen)
    checked = freezer.verify_manifest(frozen)
    inputs = auditor.audit_inputs(config["plan"], config["freeze"], config["review"])
    bind_audited_inputs(raw, inputs)
    require(Path(checked["freeze"]["root"]) == source_root.resolve(), "source root differs from freeze")
    plan = checked["plan"]
    owner_spec(config, plan)
    require(plan.get("parent_transport") == "bounded-http-current-parent-v1", "reviewed HTTP parent transport required")
    require(checked["plan_sha256"] == digest(raw["plan"]), "selected plan differs")
    require(type(config["cells"]) is list and len(config["cells"]) == 2, "two fixed cell slots required")
    stage = winpath(config["guest_stage_directory"])
    require(PureWindowsPath(stage).drive.casefold() == 'c:', "portable payload staging on guest system disk only")
    pins = decode(raw["payload_pins"])
    require(type(pins) is dict and 2 <= len(pins) <= 10000, "fixed payload entry pins required")
    import zipfile
    import io
    with zipfile.ZipFile(io.BytesIO(raw["payload_zip"])) as archive:
        names = archive.namelist()
        require(len(names) == len(set(n.casefold() for n in names)) and set(names) == set(pins), "payload entry denominator/alias")
        require(sum(v.file_size for v in archive.infolist()) <= 536870912, "expanded payload bound")
        for item in archive.infolist():
            name = item.filename
            require(re.fullmatch(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*", name)
                    and not any(p in ('.', '..') for p in name.split('/'))
                    and (item.external_attr >> 16) & 61440 in (0, 32768)
                    and not item.external_attr & 1024 and item.file_size <= 134217728,
                    "plain bounded payload entry required")
            require(type(pins[name]) is str and HEX.fullmatch(pins[name]) and digest(archive.read(item)) == pins[name], "payload entry pin")
    guest_payload = PureWindowsPath(stage) / 'payload'
    for field in ("guest_python_relative", "guest_collector_relative", "guest_bootstrap_relative"):
        require(config[field] in pins, "missing selected payload entry: " + field)
    guest_files = {str(guest_payload.joinpath(*name.split('/'))): sha for name, sha in pins.items()}
    expected_files = plan["resident_expected"]["guest"]["files"]
    require(all(guest_files.get(path) == sha for path, sha in expected_files.items()), "guest file inventory differs from payload")
    require(guest_files[str(guest_payload / config["guest_python_relative"])] == expected_files.get(str(guest_payload / config["guest_python_relative"])), "Python payload not resident pinned")
    require(config["guest_python_version"] == "3.14.7", "reviewed portable release required")
    require(str(guest_payload / config["guest_collector_relative"]) in expected_files, "collector not resident pinned")
    require(str(guest_payload / config["guest_bootstrap_relative"]) in expected_files, "bootstrap not resident pinned")
    frozen_sources = {item["path"]: item["sha256"] for item in checked["freeze"]["sources"]}
    for relative, sha in pins.items():
        if relative.startswith("experiments/"):
            require(frozen_sources.get(relative) == sha, "guest source differs from frozen published source")
    require(raw["bootstrap"] == (directory / 'guest_bootstrap.ps1').read_bytes(), "bootstrap differs from frozen source")
    require(b"DiagnosticPlanSha256" in raw["bootstrap"],
            "reviewed bootstrap diagnostic-plan/volume-plan hash separation missing; no execution")
    # Volume plans are factual output of parent-reviewed readiness correlation.
    roots, units, systems = [], [], []
    for index, cell in enumerate(config["cells"]):
        require(type(cell) is dict and set(cell) == {"case", "attempt_name", "guest_control_directory", "volume_plan"}, "cell fields")
        selected = plan["cases"][index]
        require(cell["case"] == CASES[index] == selected["case"], "fixed ordered cases")
        require(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cell["attempt_name"]), "bounded local attempt name")
        control = winpath(cell["guest_control_directory"])
        require(PureWindowsPath(control).drive.casefold() == 'c:'
                and PureWindowsPath(control).parent == PureWindowsPath('C:\\'),
                "fresh control directory must be a direct child of guest C root")
        volume = cell["volume_plan"]
        require(volume == selected.get("volume_plan") and digest(encode(volume)) == selected.get("volume_plan_sha256"),
                "reviewed cell selection content/bytes differ from driver config")
        actual = readiness["cells"][index]
        require(actual["cell"] == ("persistent-write-error", "no-error-control")[index]
                and actual["volume"]["FileSystemLabel"] == volume["label"]
                and actual["volume"]["UniqueId"] == volume["volume_unique_id"]
                and actual["disk"]["Number"] == volume["disk_number"]
                and actual["partition"]["PartitionNumber"] == volume["partition_number"]
                and actual["disk"]["SerialNumber"].strip() == volume["device_serial"]
                and int(actual["cimLogical"]["VolumeSerialNumber"].replace("-", ""),16) == int(volume["volume_serial"].replace("-", ""),16)
                and actual["source"]["path"] == str(PureWindowsPath(volume["root"]).parent / "source.bin"),
                "volume plan differs from actual retained readiness")
        required_volume = {"unit", "fixture_relative", "min_disk_bytes", "max_disk_bytes", "label", "bus_type",
                           "device_serial", "volume_serial", "volume_unique_id", "disk_number", "partition_number", "root"}
        require(type(volume) is dict and set(volume) == required_volume, "complete factual volume plan required")
        require(volume["unit"] == selected["unit"] and volume["root"] == selected["root"], "cell unit/root mismatch")
        identities = selected.get("identities", plan["identities"])
        require(volume["device_serial"] == identities["disk"]["device_serial"]
                and volume["volume_serial"] == identities["volume"]["volume_serial"], "volume/controller binding mismatch")
        require(PureWindowsPath(volume["root"]).parent == PureWindowsPath(PureWindowsPath(volume["root"]).anchor)
                and PureWindowsPath(volume["root"]).name == volume["fixture_relative"], "actual offline source at volume root required")
        require(type(volume["disk_number"]) is int and volume["disk_number"] >= 0
                and type(volume["partition_number"]) is int and volume["partition_number"] >= 1
                and volume["bus_type"] == 'USB' and volume["min_disk_bytes"] == volume["max_disk_bytes"] == 134217728,
                "exact prepared USB disk geometry required")
        roots.append(volume["root"].casefold()); units.append(volume["unit"]); systems.append(control.casefold())
    require(len(set(roots)) == len(set(units)) == len(set(systems)) == 2, "reused cell/root/control identity")
    require(config["cells"][0]["attempt_name"] != config["cells"][1]["attempt_name"], "reused attempt directory")
    require(config["cells"][0]["volume_plan"]["volume_unique_id"] != config["cells"][1]["volume_plan"]["volume_unique_id"]
            and config["cells"][0]["volume_plan"]["disk_number"] != config["cells"][1]["volume_plan"]["disk_number"], "distinct actual disks/volume GUIDs required")
    require(Path(config["pair_root"]).is_absolute() and Path(config["qmp_socket"]).is_absolute(), "absolute private paths required")
    return config, raw, freezer, auditor, checked, inputs, host, core


def launcher(config, cell, request, request_raw, bootstrap_sha, pins_raw, volume_raw, port):
    control = cell["guest_control_directory"]
    stage = config["guest_stage_directory"]
    payload = PureWindowsPath(stage) / 'payload'
    # New download directory, exact finite GET allowlist, no IEX or generic exec.
    lines = ["$ErrorActionPreference='Stop'", "$ProgressPreference='SilentlyContinue'",
             "$control219=" + ps(control),
             "if(Test-Path -LiteralPath $control219){throw 'Retain prior control directory; no replay'}",
             "$null=New-Item -ItemType Directory -Path $control219",
             "$b219=Join-Path $control219 'bootstrap.ps1'",
             "Invoke-WebRequest " + ps(f"http://10.0.2.2:{port}/bootstrap.ps1") + " -UseBasicParsing -TimeoutSec 15 -OutFile $b219",
             "if((Get-FileHash -LiteralPath $b219 -Algorithm SHA256).Hash.ToLowerInvariant() -cne " + ps(bootstrap_sha) + "){throw 'Bootstrap pin'}",
             ". $b219"]
    for name, content in (("pins.json", pins_raw), ("request.json", request_raw), ("volume.json", volume_raw)):
        lines += ["$f219=Join-Path $control219 " + ps(name),
                  "$h219=[IO.File]::Open($f219,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)",
                  "try{$x219=[Convert]::FromBase64String(" + ps(base64.b64encode(content).decode()) + ");$h219.Write($x219,0,$x219.Length);$h219.Flush($true)}finally{$h219.Dispose()}"]
    # First cell stages the one payload. Second only verifies exact existing files;
    # code is never downloaded/changed while its first collector is alive.
    if cell["case"] == CASES[0]:
        lines += ["$null=Stage-Namespace219Payload -AssetUri " + ps(f"http://10.0.2.2:{port}/payload.zip")
                  + " -ArchiveSha256 " + ps(config["input_sha256"]["payload_zip"])
                  + " -EntryPinsPath (Join-Path $control219 'pins.json') -EntryPinsSha256 " + ps(digest(pins_raw))
                  + " -StageDirectory " + ps(stage)]
    else:
        lines += ["$pins219=Read-Namespace219PinnedJson (Join-Path $control219 'pins.json') " + ps(digest(pins_raw)),
                  "foreach($p219 in $pins219.PSObject.Properties){Assert-Namespace219PinnedFile (Join-Path " + ps(str(payload)) + " $p219.Name.Replace('/','\\')) $p219.Value}"]
    # The defining script path must match Invoke's pin; use the downloaded exact
    # bootstrap, not a separately named identical file in payload.
    lines += ["$r219=Invoke-Namespace219GuestCollector -PythonPath " + ps(str(payload / config["guest_python_relative"]))
              + " -PythonSha256 " + ps(decode(pins_raw)[config["guest_python_relative"]])
              + " -ExpectedPythonVersion " + ps(config["guest_python_version"])
              + " -CollectorPath " + ps(str(payload / config["guest_collector_relative"]))
              + " -CollectorSha256 " + ps(decode(pins_raw)[config["guest_collector_relative"]])
              + " -RequestPath (Join-Path $control219 'request.json') -RequestSha256 " + ps(digest(request_raw))
              + " -BootstrapPath $b219 -BootstrapSha256 " + ps(bootstrap_sha)
              + " -Endpoint " + ps(f"http://10.0.2.2:{port}/event/{request['unit']}")
              + " -VolumePlanPath (Join-Path $control219 'volume.json') -VolumePlanSha256 " + ps(digest(volume_raw))
              + " -DiagnosticPlanSha256 " + ps(request["bindings"]["plan_sha256"])
              + " -CaptureDirectory (Join-Path $control219 'bootstrap-capture') -DeadlineSeconds 300 -CurrentOwningParent",
              "if($r219.failed -or -not $r219.collectorExitConfirmed){throw 'Collector bootstrap partial; retain captures'}",
              "Write-Output 'IMAGEINFO219_COLLECTOR_CONFIRMED_EXIT'" ]
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8')


def artifact_manifest(attempt, auditor):
    exports = [row["value"] for row in [decode(line) for line in (attempt / 'host.jsonl').read_bytes().splitlines()]
               if row["kind"] == 'http-export']
    require(len(exports) == 1, "one retained export manifest required")
    exported = {item["guest_path"]: item for item in exports[0]["files"]}
    cell = auditor.audit_guest(attempt)
    entries = []
    for name, snapshot in sorted(cell["final"]["paths"].items(), key=lambda item: item[1]["path"]):
        if name == 'preparedSource' or snapshot["status"] != 'ok':
            continue
        item = exported.get(snapshot["path"])
        require(item is not None, "actual final artifact missing from export")
        entries.append({"guest_path": item["guest_path"], "path": item['name'],
                        "bytes": item["bytes"], "sha256": item["sha256"]})
    new_json(attempt / 'artifacts.json', {"schema": "imageinfo-0219-artifacts-v1", "entries": entries})


def confirm_collector_exit(transport, result, context, attempt, ready):
    unit = context['unit']
    deadline = time.monotonic() + 120
    prepared, _, prepared_sha = result.load_preparation(context)
    require(prepared_sha == ready['prepared_sha256'], 'result preparation changed after input')
    audit_path = attempt / 'console-preparation' / 'inspection-audit.json'
    while not audit_path.is_file():
        require(time.monotonic() < deadline, 'current actual console result inspection deadline')
        require(not (audit_path.parent / 'inspection-failure.json').exists(), 'root result inspection refused')
        time.sleep(.05)
    audit = result.load_result_audit(context, prepared, prepared_sha)
    challenge = secrets.token_hex(16)
    capture_sha = audit['capture_sha256']
    token = f'collector-exit-confirmed {unit} 0 {capture_sha} {challenge}'
    print(json.dumps({"requires_current_parent_observation": "actual bootstrap result and confirmed collector exit",
                      "stdin_token": token, "deadline_seconds": 120}), flush=True)
    require(transport.read_line(sys.stdin, deadline) == (token + '\n').encode(),
            'exact live current-parent collector-exit observation required')
    require(result.load_result_audit(context, prepared, prepared_sha) == audit, 'console result inspection changed')
    new_json(attempt / 'collector-exit-confirmation.json', {"unit": unit, "collector_exit_confirmed": True,
             "collector_exit_code": 0, "observation_basis": "live-current-parent-read-bootstrap-result",
             "monotonic_ns": time.monotonic_ns(), "importable_authority": False,
             'owner_sha256': ready['owner_sha256'], 'screen_sha256': ready['screen_sha256'],
             'capture_sha256': capture_sha, 'challenge_sha256': digest(challenge.encode())})


def qmp_platform():
    return sys.platform == 'linux' and os.geteuid() == 1000


def reviewed_vm(config, checked, selected):
    plan = checked['plan']
    disk_pin = checked['freeze']['inputs']['disk_configuration']
    disk_raw = read(disk_pin['path'])
    require(digest(disk_raw) == disk_pin['sha256'], 'frozen disk configuration changed')
    launch_pin = decode(disk_raw)['capture_bindings']['launch']
    launch_raw = read(launch_pin['path'])
    require(digest(launch_raw) == launch_pin['sha256'], 'reviewed launch capture changed')
    argv = decode(launch_raw)['launch']['argv']
    vm_executable = Path(argv[0])
    require(vm_executable.is_absolute() and vm_executable.resolve(strict=True).name == 'qemu-system-x86_64',
            'exact QEMU executable required')
    vm_executable = vm_executable.resolve(strict=True)
    identities = selected.get('identities', plan['identities'])
    socket_path = Path(config['qmp_socket'])
    require(socket_path.is_absolute() and socket_path == socket_path.resolve(strict=True) and ',' not in str(socket_path)
            and argv.count('-qmp') == 1 and argv.count('-pidfile') == 1
            and argv[argv.index('-qmp') + 1].split(',')[0] == 'unix:' + str(socket_path),
            'reviewed VM argv does not select the exact QMP socket')
    pidfile = Path(argv[argv.index('-pidfile') + 1])
    require(pidfile == socket_path.parent / 'qemu.pid' and not pidfile.is_symlink()
            and int(read(pidfile, 64)) == identities['guest']['vm_pid'], 'reviewed live VM pidfile differs')
    return {'vm_pid': identities['guest']['vm_pid'], 'vm_argv': argv, 'vm_executable': str(vm_executable),
            'vm_start_ticks': config['vm_start_ticks'], 'qmp_socket': config['qmp_socket']}


def verify_qmp_peer(channel, vm):
    size = struct.calcsize('3i')
    pid, uid, _ = struct.unpack('3i', channel.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size))
    require(pid == vm['vm_pid'] and uid == 1000, 'connected QMP peer PID or UID differs')
    proc = Path('/proc') / str(pid)
    raw = read(proc / 'stat', 4096)
    require(int(raw.rsplit(b') ', 1)[1].split()[19]) == vm['vm_start_ticks'], 'connected QMP peer start ticks differ')


def console_context(config_path, config, config_sha, raw, attempt, checked, selected, request, request_raw, script, owner, deadline, vm):
    plan = checked['plan']
    readiness = decode(raw['readiness_capture'])
    boot = re.fullmatch(r'/Date\(([0-9]+)\)/', readiness['os']['LastBootUpTime'])
    require(boot is not None, 'actual boot timestamp required')
    pins = request['reviewed_files']
    payload = PureWindowsPath(config['guest_stage_directory']) / 'payload'
    control = str(PureWindowsPath(request['attempt_dir']).parent)
    bootstrap_sha = config['input_sha256']['bootstrap']
    require(pins[str(payload / config['guest_bootstrap_relative'])] == bootstrap_sha,
            'downloaded bootstrap and reviewed payload bootstrap pins differ')
    return {'schema': 'imageinfo-0219-console-context-v1', 'bindings': str(config_path),
            'driver': str(owner.root / 'host_runner.py'), 'owner': owner.owner, 'owner_sha256': owner.sha256,
            'driver_pid': owner.owner['pid'], **vm,
            'config_sha256': config_sha, 'checked_snapshot': {'checked': {
                'plan': plan, 'freeze': checked['freeze']}}, 'attempt': str(attempt), 'unit': selected['unit'],
            'case': selected['case'], 'control': control, 'request': request, 'request_sha256': digest(request_raw),
            'launcher_uri': f"http://10.0.2.2:{config['port']}/launch.ps1", 'launcher_sha256': digest(script),
            'guest_launcher': str(PureWindowsPath(control).parent / (selected['unit'] + '-launch.ps1')),
            'result_port': config['result_port'], 'post_uri': f"http://10.0.2.2:{config['result_port']}/result/{selected['unit']}",
            'deadline_monotonic_ns': int(deadline * 1_000_000_000), 'boot_ms': int(boot.group(1)),
            'bootstrap_sha256': bootstrap_sha, 'python_sha256': pins[str(payload / config['guest_python_relative'])],
            'collector_sha256': pins[str(payload / config['guest_collector_relative'])]}


def console_handoff(transport, result, phase, owner, context, attempt, check_peer):
    unit = context['unit']
    exact_context = encode(context)
    new_file(attempt / 'console-context.json', exact_context)

    def revalidate():
        owner.revalidate()
        check_peer()
        require(read(attempt / 'console-context.json') == exact_context
                and digest(read(context['bindings'])) == context['config_sha256']
                and digest(read(attempt / 'launcher.ps1')) == context['launcher_sha256']
                and digest(read(attempt / 'request.json')) == context['request_sha256'],
                'current owner context or immutable attempt files changed')

    endpoint = phase.endpoint
    endpoint.start()
    inspect_token = 'inspect-console ' + unit
    print(json.dumps({'phase': 'await-inspect', 'current_cell': context['case'], 'unit': unit,
                      'stdin_token': inspect_token, 'deadline_monotonic_ns': context['deadline_monotonic_ns']}), flush=True)
    require(transport.read_line(sys.stdin, phase.deadline) == (inspect_token + '\n').encode(),
            'exact live parent inspect-console instruction required')
    screen = attempt / 'console-screen.ppm'
    screen_sha = phase.inspect(screen, revalidate)
    binding = {key: context[key] for key in ('unit', 'config_sha256', 'owner_sha256')}
    screen_record = {'schema': 'imageinfo-0219-console-screen-v1', **binding,
                     'screen': str(screen), 'screen_sha256': screen_sha}
    new_json(attempt / 'console-screen.json', screen_record)
    phase.record({'kind': 'screen-retained', **screen_record})
    print(json.dumps({'phase': 'await-launch', 'context': str(attempt / 'console-context.json'),
                      'context_sha256': digest(exact_context), **screen_record}), flush=True)
    instruction = transport.read_line(sys.stdin, phase.deadline)

    def check_launch(*, check_only=False):
        revalidate()
        if check_only:
            return None
        require(decode(read(attempt / 'console-screen.json')) == screen_record
                and transport.screen_digest(screen) == screen_sha, 'current console screen changed')
        prepared, typed, prepared_sha = result.load_preparation(context)
        result.load_readiness(context, prepared, prepared_sha)
        token = 'launch-console ' + ' '.join((unit, context['config_sha256'], prepared_sha, owner.sha256, screen_sha))
        require(instruction == (token + '\n').encode(), 'exact live parent launch-console instruction required')
        require(prepared['typed_sha256'] == digest(typed.encode()), 'pinned console command changed')
        ready.update(schema='imageinfo-0219-console-result-ready-v1', **binding, screen_sha256=screen_sha,
                     prepared_sha256=prepared_sha, typed_sha256=prepared['typed_sha256'], result_port=context['result_port'])
        return typed

    def complete():
        completion = {key: value for key, value in ready.items() if key not in ('schema', 'result_port')}
        phase.record({'kind': 'input-complete', **completion, 'guest_success_established': False})
        pending = attempt / 'console-input-complete.pending'
        new_json(pending, {'schema': 'imageinfo-0219-console-input-complete-v1', **completion})
        os.link(pending, attempt / 'console-input-complete.json')
        pending.unlink()

    ready = {}
    phase.launch(check_launch, complete)
    return ready


def run(config_path, *, reviewer, approved_sha256, modules):
    config_raw = read(config_path)
    require(digest(config_raw) == approved_sha256, "explicit current-parent config hash differs")
    require(qmp_platform(), 'QMP driver requires reviewed Linux interpreter and ordinary uid1000')
    config, raw, freezer, auditor, checked, inputs, host, core = inspect(config_path, expected_raw=config_raw)
    # Construct the decision from this invocation, never deserialize an approval.
    decision = freezer.ParentDecision(inputs['plan_sha256'], inputs['freeze_sha256'], reviewer)
    current = freezer.verify_current(config['plan'], config['freeze'], parent_decision=decision)
    require(current['plan'] == checked['plan'] and current['freeze'] == checked['freeze'], 'current decision selected changed core inputs')
    root, expected_owner = owner_spec(config, checked['plan'])
    owner = Attestation(root, expected_owner, modules)
    owner.core = core
    owner.revalidate()
    transport, result_helper = modules['console_transport.py'], modules['console_result.py']
    require(str(root / 'host_runner.py') in owner.owner['argv'], 'ordinary owner must invoke the maintained runner by absolute path')
    pair = Path(config['pair_root'])
    pair.mkdir(exist_ok=False)
    new_file(pair / 'driver-config.json', config_raw)
    new_json(pair / 'slots.json', [{"case": cell['case'], "attempt_name": cell['attempt_name'], "status": 'planned'} for cell in config['cells']])
    # All attempted cells, including failures before worker start, enter one
    # retained denominator. An unsafe/partial first cell stops the fixed scope.
    with (pair / 'attempts.jsonl').open('xb') as denominator:
        for index, cell in enumerate(config['cells']):
            selected = checked['plan']['cases'][index]
            attempt = pair / cell['attempt_name']
            row = {"seq": index + 1, "case": cell['case'], "unit": selected['unit'], "attempt_dir": attempt.name}
            denominator.write(encode(row).replace(b'\n', b'') + b'\n'); denominator.flush(); os.fsync(denominator.fileno())
            attempt.mkdir(exist_ok=False)
            run_cell(config_path, approved_sha256, config, raw, checked, inputs, host, auditor, owner, transport, result_helper,
                     cell, selected, attempt)
    result = auditor.audit_pair(pair / config['cells'][0]['attempt_name'], pair / config['cells'][1]['attempt_name'], config['plan'], config['freeze'], config['review'])
    new_json(pair / 'pair-audit.json', result)
    return {"status":"two-worker-cells-audited", "pair_root":str(pair), "attempts":2,
            "collector_bootstrap_exit":"current-parent-confirmed", **{flag:False for flag in FLAGS}}


def append(ledger, value):
    ledger.write(json.dumps(value, separators=(',', ':'), allow_nan=False).encode() + b'\n')
    ledger.flush()
    os.fsync(ledger.fileno())


def run_cell(config_path, config_sha, config, raw, checked, inputs, host, auditor, owner, transport, result_helper,
             cell, selected, attempt):
    channel = endpoint = controller = phase = ready = None
    identity = {'unit': selected['unit'], 'config_sha256': config_sha, 'owner_sha256': owner.sha256}
    with (attempt / 'host.jsonl').open('xb') as ledger, (attempt / 'console-owner.jsonl').open('xb') as owner_ledger:
        def record_owner(row):
            append(owner_ledger, {**identity, 'monotonic_ns': time.monotonic_ns(), **row})

        def cleanup():
            issues = {}
            if endpoint is not None and not endpoint.stop.is_set():
                try:
                    endpoint.cancel('driver ended before confirmed final')
                except BaseException as error:
                    issues['cancellation'] = {'type': type(error).__name__, 'message': str(error)[:2048]}
            for label, resource in (('endpoint', endpoint), ('channel', channel)):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as error:
                        issues[label] = {'type': type(error).__name__, 'message': str(error)[:2048]}
            return issues

        try:
            owner.revalidate()
            require(digest(read(config_path)) == config_sha, 'approved config changed before attempt effects')
            record_owner({'kind': 'owner-bound', 'owner': owner.owner})
            plan = checked['plan']
            identities = selected.get('identities', plan['identities'])
            binding = host.Binding(**identities['disk'], **identities['volume'],
                                   unit=selected['unit'], case=cell['case'], root=selected['root'])
            vm = reviewed_vm(config, checked, selected)
            channel = host.JsonSocketChannel(config['qmp_socket'], timeout=5)
            verify_qmp_peer(channel, vm)
            owned = transport.OwnedChannel(channel)
            class CurrentController(host.Controller):
                def cancel(self, reason):
                    with owned.cancellation():
                        return super().cancel(reason)

                def accept(self, event):
                    require(phase is not None and phase.phase == 'input-acknowledged',
                            'guest event arrived outside acknowledged console input phase')
                    return super().accept(event)

            controller = CurrentController(host.QmpChannel(owned.call), binding, lambda value: append(ledger, value),
                plan_sha256=inputs['plan_sha256'], controller_epoch=plan['resident_expected']['controller'][cell['case']]['controller_epoch'])
            observed = controller.resident()
            require(observed.get('pid') == owner.owner['pid'] and all(observed.get(key) == value for key, value in
                    plan['resident_expected']['controller'][cell['case']].items()), 'actual resident controller expectation differs')
            control = PureWindowsPath(cell['guest_control_directory'])
            resident = plan['resident_expected']['guest']
            volume = encode(cell['volume_plan'])
            request = {'unit': selected['unit'], 'case': cell['case'], 'fixture_root': selected['root'],
                       'attempt_dir': str(control / 'attempt'), 'argv': plan['argv'],
                       'worker_test_name': plan['worker_test_name'], 'bounds': plan['bounds'],
                       'parent_gate_seconds': 5, 'volume_binding_path': str(control / 'volume-binding.json'),
                       'volume_plan': cell['volume_plan'], 'volume_plan_sha256': digest(volume),
                       'bindings': {'plan_sha256': inputs['plan_sha256'], 'freeze_sha256': inputs['freeze_sha256'],
                                    'worker_sha256': checked['worker_sha256']},
                       'observer_python': {key: value for key, value in resident.items() if key != 'files'},
                       'reviewed_files': resident['files'], 'require_export': True}
            request_raw = encode(request)
            script = launcher(config, cell, request, request_raw, digest(raw['bootstrap']), raw['payload_pins'], volume, config['port'])
            new_file(attempt / 'launcher.ps1', script)
            new_file(attempt / 'request.json', request_raw)
            exports = ('source.bin', 'old-source.bin', 'candidate.bin', 'output.bin', 'prepared.record', 'intent.record',
                       'observation.record', 'receipt.record', 'stdout.bin', 'stderr.bin', 'events.jsonl', 'transcript.jsonl',
                       'result.json', 'guest-transcript.jsonl', 'guest.json', 'volume-binding.json')
            captures = ('stdout.bin', 'stderr.bin', 'events.jsonl', 'transcript.jsonl', 'result.json', 'guest-transcript.jsonl',
                        'guest.json', 'volume-binding.json')
            controller.prepare()
            class CurrentAssets(dict):
                def __contains__(self, name):
                    return phase is not None and phase.phase == 'input-acknowledged' and super().__contains__(name)

            endpoint = host.HttpEndpoint(controller, {'/bootstrap.ps1': raw['bootstrap'], '/payload.zip': raw['payload_zip'], '/launch.ps1': script},
                port=config['port'], timeout=300, artifacts={name: (16 if name.endswith('.bin') else 4) * MAX_JSON for name in exports},
                artifact_sink=lambda name, data: new_file(attempt / name, data), required_files=captures, require_export=True, export_timeout=120)
            endpoint.assets = CurrentAssets(endpoint.assets)
            owned.endpoint = endpoint
            context = console_context(config_path, config, config_sha, raw, attempt, checked, selected, request, request_raw, script, owner,
                                      endpoint.deadline, vm)
            require(context['config_sha256'] == identity['config_sha256'], 'driver config changed after owner journal binding')
            cases = [{**item, 'identities': item.get('identities', plan['identities'])} for item in plan['cases']]
            phase = transport.ConsolePhase(owned, endpoint, cases, record_owner, host._blkdebug_rules)
            ready = console_handoff(transport, result_helper, phase, owner, context, attempt, lambda: verify_qmp_peer(channel, vm))
            endpoint.wait()
            require(endpoint.exit_confirmed and endpoint.export_complete, 'confirmed worker exit/export required')
            issues = cleanup()
            endpoint = channel = None
            require(not issues, 'terminal resource close failed: ' + str(issues))
            artifact_manifest(attempt, auditor)
            confirm_collector_exit(transport, result_helper, context, attempt, ready)
            new_json(attempt / 'audit.json', auditor.audit(attempt, config['plan'], config['freeze'], config['review']))
            record_owner({'kind': 'terminal', 'status': 'audited', 'screen_sha256': ready['screen_sha256']})
            new_json(attempt / 'driver-result.json', {'status': 'worker-exited-exported-audited', **ready, **identity,
                     'schema': 'imageinfo-0219-sole-owner-driver-result-v1', 'collector_bootstrap_exit': 'current-parent-confirmed',
                     **{flag: False for flag in FLAGS}})
        except BaseException as exc:
            issues = cleanup()
            progress = None if phase is None else {'phase': phase.phase, 'journaled': phase.journaled, 'attempted': phase.attempted,
                'acknowledged': phase.acknowledged, 'channel_poisoned': phase.owner.channel.failed}
            terminal = {'status': 'partial-refused', **identity, 'type': type(exc).__name__, 'message': str(exc)[:8192],
                        'input_progress': progress, 'cleanup_errors': issues, 'retry': False,
                        'resident': None if controller is None else controller.resident(), **{flag: False for flag in FLAGS}}
            new_json(attempt / 'driver-failure.json', terminal)
            record_owner({'kind': 'terminal', **terminal})
            raise


def load_owner_modules(root, expected):
    captured = {filename: read(root / filename, 4 * MAX_JSON) for filename in OWNER_SOURCES}
    hashes = {filename: digest(raw) for filename, raw in captured.items()}
    require(expected is None or hashes == expected['sources'], 'reviewed owner source bytes differ before compile')
    return {filename: load('imageinfo_owner_' + filename[:-3], root / filename, captured[filename],
                           import_module=import_standard) for filename in OWNER_MODULES}, hashes


def run_result_mode(args, config, expected, modules):
    config_path = Path(args.bindings)
    context_path = Path(args.context)
    context_raw = read(context_path)
    require(digest(context_raw) == args.approved_context_sha256, 'explicit current context digest differs')
    context = decode(context_raw)
    require(context.get('schema') == 'imageinfo-0219-console-context-v1'
            and context['bindings'] == str(config_path)
            and context['config_sha256'] == args.approved_bindings_sha256
            and context['result_port'] == config['result_port']
            and context_path == Path(context['attempt']) / 'console-context.json'
            and any(context_path.parent == Path(config['pair_root']) / cell['attempt_name'] for cell in config['cells'])
            and digest(encode(context['owner'])) == context['owner_sha256']
            and all(context['owner'].get(key) == value for key, value in expected.items()),
            'current owner context differs from reviewed config and source')
    require(live_entries(modules)[1] == expected['code_sha256'] and runtime_identity() == expected['runtime'],
            'result helper code/runtime differs from reviewed owner inventory')
    result = modules['console_result.py']
    if args.mode == 'prepare-console':
        require(qmp_platform(), 'file-only preparation requires the ordinary uid1000')
        return result.prepare(context)
    return result.observe(context, approved_context_sha256=args.approved_context_sha256,
                          approved_prepared_sha256=args.approved_prepared_sha256,
                          parent_screen_sha256=args.parent_screen_sha256,
                          parent_confirmed_idle_console=args.parent_confirmed_idle_console)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('owner-inventory', 'inspect', 'run', 'prepare-console', 'observe-console'))
    parser.add_argument('--bindings')
    parser.add_argument('--approved-bindings-sha256')
    parser.add_argument('--approve-current-parent', action='store_true')
    parser.add_argument('--reviewer')
    parser.add_argument('--context')
    parser.add_argument('--approved-context-sha256')
    parser.add_argument('--approved-prepared-sha256')
    parser.add_argument('--parent-screen-sha256')
    parser.add_argument('--parent-confirmed-idle-console', action='store_true')
    args = parser.parse_args()
    # This checkpoint has authored integration coverage only. Keep every
    # operation mode unavailable until the exact authored two-cell acceptance
    # and independent review are complete.
    require(args.mode in ('owner-inventory', 'inspect'), 'checkpoint permits inventory and read-only inspection only')
    root = Path(__file__).resolve().parent
    if args.mode == 'owner-inventory':
        # Candidate review data only; no config, process, network or attempt.
        modules, hashes = load_owner_modules(root, None)
        output = {'sources': hashes, 'runtime': runtime_identity(), 'code_sha256': live_entries(modules)[1]}
    else:
        require(args.bindings and args.approved_bindings_sha256, 'explicit config path and digest required')
        config_raw = read(args.bindings)
        require(digest(config_raw) == args.approved_bindings_sha256, 'approved config bytes differ')
        config = decode(config_raw)
        plan_raw = read(config['plan'])
        require(digest(plan_raw) == config['input_sha256']['plan'], 'reviewed plan bytes differ')
        selected_root, expected = owner_spec(config, decode(plan_raw))
        require(root == selected_root, 'invoked runner must be from the exact reviewed owner source directory')
        require(sys.flags.isolated and sys.flags.no_site and len(sys.orig_argv) >= 7
                and sys.orig_argv[1:6] == ['-I', '-S', str(root / 'owner_entry.py'),
                                         str(root / 'host_runner.py'), expected['sources']['host_runner.py']]
                and globals().get('__captured_entry_sha256__') == expected['sources']['host_runner.py'],
                'isolated verified owner bootstrap required for config-bound invocation')
        modules, _ = load_owner_modules(root, expected)
        runner = modules['host_runner.py']
        _, _, _, _, checked, _, _, _ = runner.inspect(args.bindings, expected_raw=config_raw)
        require(runner.live_entries(modules)[1] == expected['code_sha256'] and runner.runtime_identity() == expected['runtime'],
                'loaded owner code/runtime differs from reviewed inventory')
        output = {'status': 'factual-inputs-validated-only', 'bindings_sha256': digest(config_raw),
                  'plan_sha256': checked['plan_sha256'], 'case_order': list(CASES), 'execution': False}
    print(json.dumps(output, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()

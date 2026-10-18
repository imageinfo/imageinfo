"""Opt-in current-parent QMP/QGA coordinator for exactly one #0219 cell.

Import performs no connection or guest action. Callers retain every record, own
the emulator, and supply the independently reviewed current plan. Records are
observations, never restart authority or storage/profile admission.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import http.server
import importlib.util
import json
import marshal
import os
from pathlib import Path
import platform
import re
import socket
import socketserver
import sys
import threading
import time
import types
import uuid

_spec = importlib.util.spec_from_file_location("namespace_219_host_protocol", Path(__file__).with_name("protocol.py"))
protocol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protocol)

MAX_REPLY_BYTES = 4 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
CHUNK_BYTES = 65536
MAX_POLLS = 1200
RULE = {"event": "write_aio", "iotype": "write", "errno": 28, "once": False}


class HostError(ValueError):
    """Attempt is partial/refused; no worker or transport replay is implied."""


def _require(condition, message):
    if not condition:
        raise HostError(message)


def _bounded(value, limit=MAX_REPLY_BYTES):
    try:
        data = json.dumps(value, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise HostError("non-JSON transport value") from exc
    _require(len(data) <= limit, "transport value exceeds bound")
    return deepcopy(value)


def _path(value):
    _require(type(value) is str and 0 < len(value) <= 1024
             and all(ord(c) >= 32 for c in value), "invalid guest path")
    return value


def _normalized_code(code):
    return code.replace(co_filename="host_controller.py", co_consts=tuple(
        _normalized_code(v) if isinstance(v, types.CodeType) else v for v in code.co_consts))


def resident_code_sha256():
    """Hash resident code objects, never reread editable source as loaded code."""
    entries = []
    for name, value in sorted(globals().items()):
        if isinstance(value, types.FunctionType) and value.__module__ == __name__:
            entries.append((name, _normalized_code(value.__code__)))
        elif isinstance(value, type) and value.__module__ == __name__:
            for key, method in sorted(vars(value).items()):
                if isinstance(method, (staticmethod, classmethod)):
                    method = method.__func__
                if isinstance(method, types.FunctionType):
                    entries.append((name + "." + key, _normalized_code(method.__code__)))
    # Imported protocol code is separately frozen; its loaded function objects
    # are bound too so changing a module on disk cannot certify an older import.
    for label, module in (("protocol", protocol), ("worker_protocol", protocol.worker_protocol)):
        for name, value in sorted(vars(module).items()):
            if isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
                entries.append((label + "." + name, _normalized_code(value.__code__)))
            elif isinstance(value, type) and value.__module__ == module.__name__:
                for key, method in sorted(vars(value).items()):
                    if isinstance(method, (staticmethod, classmethod)):
                        method = method.__func__
                    if isinstance(method, types.FunctionType):
                        entries.append((label + "." + name + "." + key, _normalized_code(method.__code__)))
    return hashlib.sha256(marshal.dumps((entries, RULE, MAX_REPLY_BYTES, MAX_FILE_BYTES, CHUNK_BYTES,
                                        protocol.STAGES, protocol.COMMANDS))).hexdigest()


def _blkdebug_rules(filename, binding, expected_rule):
    """Decode only the two equivalent finite rule readback representations.

    QEMU may flatten array index zero into dotted option names. Absence of all
    injection fields denotes the empty control, never the required error rule.
    Raw node/child/file/device checks remain independent in Controller._graph.
    """
    _require(type(filename) is str and filename.startswith("json:"), "missing blkdebug JSON")
    try:
        raw = filename[5:].encode("utf-8")
        _require(len(raw) + 5 <= 65536, "bounded blkdebug JSON")
        config = json.loads(raw.decode("utf-8"), object_pairs_hook=protocol.worker_protocol._pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(HostError("nonfinite blkdebug JSON")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HostError("invalid/duplicate blkdebug JSON") from exc
    _require(type(config) is dict and config.get("driver") == "blkdebug", "wrong blkdebug driver")
    metadata = {"driver", "image", "node-name"}
    if "node-name" in config:
        _require(config["node-name"] == binding.filter_node, "blkdebug node identity differs")
    if "image" in config:
        image = config["image"]
        _require(image == binding.file_node or (type(image) is dict and set(image) == {"driver", "filename"}
                 and image["driver"] == "file" and image["filename"] == binding.disk_path),
                 "blkdebug image/path differs")
    option_keys = set(config) - metadata
    fields = {"event", "iotype", "errno", "once"}
    dotted = {"inject-error.0." + key for key in fields}
    if option_keys == {"inject-error"}:
        rules = config["inject-error"]
        _require(type(rules) is list and len(rules) <= 1, "extra/malformed nested injection rules")
    elif option_keys == dotted:
        rules = [{key: config["inject-error.0." + key] for key in fields}]
    elif not option_keys:
        rules = []
    else:
        raise HostError("mixed/missing/unknown injection fields or indices")
    for rule in rules:
        _require(type(rule) is dict and set(rule) == fields and type(rule["event"]) is str
                 and type(rule["iotype"]) is str and type(rule["errno"]) is int and type(rule["once"]) is bool,
                 "inexact rule fields/types; sector narrowing unsupported")
        _require(rule == RULE, "readback is not the exact persistent whole-volume rule")
    _require(expected_rule is None or (type(expected_rule) is dict and set(expected_rule) == fields
             and type(expected_rule["event"]) is str and type(expected_rule["iotype"]) is str
             and type(expected_rule["errno"]) is int and type(expected_rule["once"]) is bool and expected_rule == RULE),
             "unsupported expected rule")
    _require(rules == ([] if expected_rule is None else [RULE]), "missing/extra rule for selected error/control cell")
    return deepcopy(rules)


class JsonSocketChannel:
    """Explicit bounded local QEMU socket adapter; never constructed on import."""
    def __init__(self, path, *, mode="qmp", timeout=5, clock=time.monotonic):
        _require(mode in ("qmp", "qga") and 0 < timeout <= 10, "invalid socket mode/bound")
        self.timeout, self.clock = timeout, clock
        self._buffer, self.failed = bytearray(), False
        self.sock = socket.socket(socket.AF_UNIX)
        self.sequence = 0
        deadline = self.clock() + self.timeout
        try:
            self._remaining(deadline)
            self.sock.connect(str(path))
            if mode == "qmp":
                _require("QMP" in self._read(deadline), "missing QMP greeting")
                self.call("qmp_capabilities", deadline=deadline)
            else:
                token = uuid.uuid4().int & ((1 << 52) - 1)
                _require(self.call("guest-sync", {"id": token}, deadline=deadline) == token, "QGA sync mismatch")
        except Exception:
            self.failed = True
            self.close()
            raise

    def _remaining(self, deadline):
        remaining = deadline - self.clock()
        _require(not self.failed and remaining > 0, "QEMU absolute call deadline or poisoned channel")
        self.sock.settimeout(remaining)
        return remaining

    def _read(self, deadline=None):
        deadline = self.clock() + self.timeout if deadline is None else deadline
        while b"\n" not in self._buffer:
            self._remaining(deadline)
            _require(len(self._buffer) < MAX_REPLY_BYTES, "bounded socket reply failure")
            chunk = self.sock.recv(min(CHUNK_BYTES, MAX_REPLY_BYTES - len(self._buffer)))
            # Recheck after each recv as well: a fake, buffered or delayed
            # transport cannot return a complete late response as timely.
            self._remaining(deadline)
            _require(bool(chunk), "QEMU socket EOF before response")
            self._buffer.extend(chunk)
        self._remaining(deadline)
        end = self._buffer.index(b"\n") + 1
        raw = bytes(self._buffer[:end])
        del self._buffer[:end]
        _require(0 < len(raw) <= MAX_REPLY_BYTES, "bounded socket reply failure")
        try:
            value = json.loads(raw, object_pairs_hook=protocol.worker_protocol._pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(HostError("nonfinite reply")))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise HostError("invalid socket JSON") from exc
        _require(type(value) is dict, "socket reply must be object")
        return value

    def call(self, command, arguments=None, *, deadline=None):
        deadline = self.clock() + self.timeout if deadline is None else min(deadline, self.clock() + self.timeout)
        self._remaining(deadline)
        self.sequence += 1
        request = {"execute": command, "id": self.sequence}
        if arguments is not None:
            request["arguments"] = arguments
        _bounded(request)
        raw = json.dumps(request, allow_nan=False).encode() + b"\n"
        try:
            sent = 0
            while sent < len(raw):
                self._remaining(deadline)
                count = self.sock.send(raw[sent:])
                self._remaining(deadline)
                _require(type(count) is int and 0 < count <= len(raw) - sent, "partial/invalid QEMU send")
                sent += count
            # All asynchronous events and the final reply share the same
            # send/read deadline; a stream of timely event lines cannot renew it.
            for _ in range(256):
                value = self._read(deadline)
                if "event" in value:
                    continue
                _require(value.get("id") == self.sequence, "stale/mismatched socket response")
                if "error" in value:
                    raise HostError("QEMU command error: " + json.dumps(value["error"], allow_nan=False))
                _require("return" in value, "missing QEMU return")
                return value["return"]
            raise HostError("too many asynchronous QEMU events")
        except Exception:
            # A timed out/lost reply has unknown application status. Closing
            # prevents a later command from consuming that stale reply. The
            # current parent must retain the failure, never replay this request.
            self.failed = True
            self.close()
            raise

    def close(self):
        self.sock.close()


class QmpChannel:
    """Callable returns the unwrapped QMP return, or raises on actual error."""
    def __init__(self, call):
        self.transport = call

    def call(self, command, arguments=None):
        _require(type(command) is str and command in (
            "query-named-block-nodes", "query-block", "query-blockstats",
            "blockdev-add", "blockdev-reopen", "qom-get"), "unsupported QMP operation")
        _bounded(arguments)
        return _bounded(self.transport(command, arguments))


class QgaChannel:
    """Finite file transfer and process-status calls; errors never become EOF."""
    def __init__(self, call, *, clock=time.monotonic, sleep=time.sleep, cancel=lambda: False):
        self.transport, self.clock, self.sleep, self.cancel = call, clock, sleep, cancel

    def _call(self, command, args):
        _require(not self.cancel(), "QGA cancelled")
        return _bounded(self.transport(command, args))

    def _close(self, handle):
        # Closing a retained handle is still required after cancellation.
        self.transport("guest-file-close", {"handle": handle})

    def _open(self, path, mode):
        value = self._call("guest-file-open", {"path": _path(path), "mode": mode})
        _require(type(value) is int and value >= 0, "invalid QGA file handle")
        return value

    def read_file(self, path, limit=MAX_FILE_BYTES):
        _require(type(limit) is int and 0 < limit <= MAX_FILE_BYTES, "invalid transfer bound")
        handle = self._open(path, "rb")
        data = bytearray()
        try:
            for _ in range(MAX_FILE_BYTES // CHUNK_BYTES + 2):
                requested = min(CHUNK_BYTES, limit - len(data) + 1)
                result = self._call("guest-file-read", {"handle": handle, "count": requested})
                _require(type(result) is dict and type(result.get("count")) is int
                         and 0 <= result["count"] <= requested and type(result.get("eof")) is bool,
                         "invalid QGA read result")
                try:
                    chunk = base64.b64decode(result.get("buf-b64", ""), validate=True)
                except (ValueError, TypeError) as exc:
                    raise HostError("invalid QGA base64") from exc
                _require(len(chunk) == result["count"], "QGA byte/count mismatch")
                data.extend(chunk)
                _require(len(data) <= limit, "QGA file exceeds bound")
                if result["eof"]:
                    return bytes(data)
                _require(bool(chunk), "QGA read made no progress")
            raise HostError("QGA read count exhausted")
        finally:
            self._close(handle)

    def _write(self, path, data, mode):
        _require(type(data) is bytes and len(data) <= MAX_FILE_BYTES, "invalid transfer bytes")
        handle = self._open(path, mode)
        try:
            for offset in range(0, len(data), CHUNK_BYTES):
                chunk = data[offset:offset + CHUNK_BYTES]
                result = self._call("guest-file-write", {"handle": handle,
                    "buf-b64": base64.b64encode(chunk).decode("ascii"), "count": len(chunk)})
                _require(type(result) is dict and type(result.get("count")) is int
                         and result["count"] == len(chunk), "partial QGA write; no replay")
            self._call("guest-file-flush", {"handle": handle})
        finally:
            self._close(handle)

    def write_new(self, path, data):
        """Request C exclusive-create mode; unsupported agents fail, no fallback."""
        return self._write(path, data, "wbx")

    def append(self, path, data):
        _require(len(data) <= protocol.MAX_COMMAND_BYTES, "acknowledgement exceeds bound")
        return self._write(path, data, "ab")

    def launch(self, path, args):
        _require(type(args) is list and len(args) <= 64 and all(type(a) is str and len(a) <= 4096 for a in args), "invalid guest argv")
        result = self._call("guest-exec", {"path": _path(path), "arg": args, "capture-output": True})
        _require(type(result) is dict and type(result.get("pid")) is int and result["pid"] > 0, "invalid QGA pid")
        return result["pid"]

    def wait_exit(self, pid, timeout):
        _require(type(pid) is int and pid > 0 and 0 < timeout <= 300, "invalid process wait bound")
        deadline = self.clock() + timeout
        for _ in range(MAX_POLLS):
            _require(self.clock() < deadline, "guest process deadline")
            result = self._call("guest-exec-status", {"pid": pid})
            _require(type(result) is dict and type(result.get("exited")) is bool, "invalid guest status")
            if result["exited"]:
                _require(type(result.get("exitcode")) is int, "guest exit not confirmed")
                return result
            self.sleep(.05)
        raise HostError("guest process poll bound")


@dataclass(frozen=True)
class Binding:
    unit: str
    case: str
    raw_node: str
    file_node: str
    filter_node: str
    disk_path: str
    device_id: str
    device_serial: str
    volume_serial: str
    root: str

    def __post_init__(self):
        for name, value in asdict(self).items():
            _require(type(value) is str and value and len(value) <= 1024
                     and all(ord(c) >= 32 for c in value), "invalid binding " + name)
        _require(self.case in protocol.CASES and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.unit), "invalid attempt binding")
        nodes = (self.raw_node, self.file_node, self.filter_node)
        _require(len(set(nodes)) == 3 and all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", n) for n in nodes), "invalid graph nodes")


class Controller:
    """One current parent, one prepared disk and one finite operation interval."""
    def __init__(self, qmp, binding, record, *, plan_sha256=None, controller_epoch=None):
        # The current owning parent may preregister a fresh attempt ID before
        # freezing its plan. An ID is correspondence, never imported authority.
        _require(controller_epoch is None or (type(controller_epoch) is str
                 and re.fullmatch(r"[0-9a-f]{32}", controller_epoch)), "invalid controller epoch")
        self.qmp, self.binding, self.record = qmp, binding, record
        self.session = protocol.Session(binding.unit, binding.case)
        self.controller_epoch = uuid.uuid4().hex if controller_epoch is None else controller_epoch
        self.code_sha256 = resident_code_sha256()
        self.state_epoch = 0
        self.state = "new"
        self.plan_sha256 = plan_sha256
        self.rule = deepcopy(RULE) if binding.case == "persistent-write-error" else None
        self._pending = None
        self.record_failures = []
        self.record_failure_count = 0
        self.clear_outcome = None
        self._emit("resident", self.resident())

    def resident(self):
        return {"controller_epoch": self.controller_epoch, "code_sha256": self.code_sha256,
                "source_sha256": globals().get("__resident_source_sha256__"),
                "source_bytes": globals().get("__resident_source_bytes_count__"), "pid": os.getpid(),
                "python": {"implementation": platform.python_implementation(), "version": platform.python_version(),
                           "cache_tag": sys.implementation.cache_tag},
                "state_epoch": self.state_epoch, "state": self.state,
                "binding": asdict(self.binding), "rule": deepcopy(self.rule), "plan_sha256": self.plan_sha256,
                "record_failure_count": self.record_failure_count,
                "record_failures": deepcopy(self.record_failures), "clear_outcome": deepcopy(self.clear_outcome)}

    def _emit(self, kind, value):
        try:
            self.record({"kind": kind, "controller_epoch": self.controller_epoch,
                         "state_epoch": self.state_epoch, "monotonic_ns": time.monotonic_ns(),
                         "value": _bounded(value)})
        except BaseException as exc:
            # This bounded emergency state is in memory, not a substitute for
            # the failed retained ledger. It lets the current parent preserve
            # exactly which records were lost and refuse a complete outcome.
            self.record_failure_count += 1
            if len(self.record_failures) < 32:
                self.record_failures.append({"kind": kind, "state_epoch": self.state_epoch,
                    "type": type(exc).__name__, "message": str(exc)[:2048]})
            raise

    def _check_code(self):
        _require(resident_code_sha256() == self.code_sha256, "resident controller changed")
        _require(self.rule == (RULE if self.binding.case == "persistent-write-error" else None),
                 "current-parent rule state changed")

    def _call(self, name, args=None):
        self._check_code()
        try:
            value = self.qmp.call(name, args)
        except Exception as exc:
            try:
                self._emit("qmp", {"command": name, "arguments": args, "success": False,
                                   "response": None, "error": {"type": type(exc).__name__, "message": str(exc)[:8192]}})
            except BaseException:
                pass  # Keep the actual transport error; recording loss is retained above.
            raise
        self._emit("qmp", {"command": name, "arguments": args, "success": True,
                           "response": value, "error": None})
        return value

    def _graph(self, selected, *, filter_exists=True):
        b = self.binding
        values = self._call("query-named-block-nodes")
        _require(type(values) is list, "invalid node query")
        nodes = {n.get("node-name"): n for n in values if type(n) is dict}
        _require(len(nodes) == len(values), "duplicate or malformed nodes")
        _require(b.raw_node in nodes and b.file_node in nodes, "missing exact disk nodes")
        raw, file = nodes[b.raw_node], nodes[b.file_node]
        _require(file.get("drv") == "file" and file.get("image", {}).get("filename") == b.disk_path
                 and file.get("children", []) == [], "file node/disk binding changed")
        _require(raw.get("drv") == "raw" and raw.get("children") == [{"node-name": selected, "child": "file"}], "raw child binding changed")
        if filter_exists:
            filt = nodes.get(b.filter_node, {})
            _require(filt.get("drv") == "blkdebug" and filt.get("children") == [{"node-name": b.file_node, "child": "image"}], "filter child binding changed")
            filename = filt.get("image", {}).get("filename", "")
            rules = _blkdebug_rules(filename, b, self.rule)
            _require(rules == ([self.rule] if self.rule else []), "resident rule differs from actual requested rule")
        else:
            _require(b.filter_node not in nodes, "filter name already exists; no adoption")
        blocks = self._call("query-block")
        _require(type(blocks) is list, "invalid device query")
        matching = [v for v in blocks if type(v) is dict and v.get("inserted", {}).get("node-name") == b.raw_node]
        _require(len(matching) == 1, "disk attachment absent or ambiguous")
        device = matching[0]
        _require(device.get("qdev") in (b.device_id, "/machine/peripheral/" + b.device_id + "/" + b.device_id + ".0",
                 "/machine/peripheral/" + b.device_id + "/" + b.device_id + ".0/legacy[0]"), "disk device changed")
        serial = self._call("qom-get", {"path": "/machine/peripheral/" + b.device_id,
                                        "property": "serial"})
        _require(serial == b.device_serial, "actual QMP device serial changed")
        self._call("query-blockstats")

    def prepare(self):
        _require(self.state == "new", "prepare only once")
        self._graph(self.binding.file_node, filter_exists=False)
        self._call("blockdev-add", {"driver": "blkdebug", "node-name": self.binding.filter_node,
                   "image": self.binding.file_node, "inject-error": [self.rule] if self.rule else []})
        self.state_epoch += 1
        self.state = "prepared"
        self._graph(self.binding.file_node)
        self._emit("prepared", self.resident())

    def bind_plan(self, plan_sha256):
        """Bind the current parent's already loaded exact plan, before effects."""
        _require(self.state == "new" and self.plan_sha256 is None
                 and type(plan_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", plan_sha256),
                 "plan may be bound exactly once before effects")
        self.plan_sha256 = plan_sha256
        self._emit("plan-bound", self.resident())

    def arm(self):
        _require(self.state == "prepared", "arm only once after preparation")
        self._graph(self.binding.file_node)
        # Mark uncertainty before the request: an error/lost response must still
        # cause one bounded direct-child restoration attempt, never a replay.
        self.state, self.state_epoch = "arm-uncertain", self.state_epoch + 1
        self._call("blockdev-reopen", {"options": [{"driver": "raw", "node-name": self.binding.raw_node, "file": self.binding.filter_node}]})
        self.state = "armed"
        self._graph(self.binding.filter_node)
        self._emit("armed", self.resident())

    def clear(self):
        _require(self.state in ("armed", "arm-uncertain"), "no active/uncertain filter")
        issues = []
        if self.record_failure_count:
            issues.append({"type": "RecordingUnavailable", "message": "prior retained record failed"})

        def preserve_issue(exc):
            issues.append({"type": type(exc).__name__, "message": str(exc)[:2048]})

        def emit_cleanup(kind, value):
            try:
                self._emit(kind, value)
            except BaseException as exc:
                preserve_issue(exc)

        emit_cleanup("before-clear", self.resident())
        if self.state == "armed":
            try:
                self._graph(self.binding.filter_node)
            except BaseException as exc:
                preserve_issue(exc)
        self.state, self.state_epoch = "clear-uncertain", self.state_epoch + 1
        args = {"options": [{"driver": "raw", "node-name": self.binding.raw_node, "file": self.binding.file_node}]}
        self.clear_outcome = {"attempted": True, "arguments": deepcopy(args), "response_received": False,
                              "response": None, "error": None, "graph_verified": False,
                              "recording_complete": False, "observation_errors": []}
        # Cleanup must reach this one actual transport call even when every
        # ledger callback fails. Logging is separate from the effect; neither a
        # failed pre-clear record nor a failed result record may skip/replay it.
        try:
            response = self.qmp.call("blockdev-reopen", args)
        except BaseException as exc:
            self.clear_outcome["error"] = {"type": type(exc).__name__, "message": str(exc)[:8192]}
            emit_cleanup("qmp", {"command": "blockdev-reopen", "arguments": args,
                "success": False, "response": None, "error": deepcopy(self.clear_outcome["error"])})
            self.clear_outcome["observation_errors"] = deepcopy(issues)
            emit_cleanup("clear-incomplete", self.resident())
            raise
        self.clear_outcome.update(response_received=True, response=deepcopy(response))
        emit_cleanup("qmp", {"command": "blockdev-reopen", "arguments": args,
                              "success": True, "response": response, "error": None})
        try:
            self._graph(self.binding.file_node)
            self.clear_outcome["graph_verified"] = True
        except BaseException as exc:
            preserve_issue(exc)
        if not issues:
            self.state = "cleared"
            self.clear_outcome["recording_complete"] = True
            emit_cleanup("cleared", self.resident())
        if issues:
            self.state = "refused"
            self.clear_outcome.update(recording_complete=False, observation_errors=deepcopy(issues))
            emit_cleanup("clear-incomplete", self.resident())
            raise HostError("direct-child restoration attempted; observations or recording incomplete")

    def accept(self, event):
        """Prepare exact ack; caller reports actual append+flush via sent()."""
        self._check_code()
        _require(self.state in ("prepared", "armed", "cleared"), "controller not ready")
        self.session.accept_event(event)
        self._emit("guest-event", event)
        observation = event["observation"]
        if event["stage"] == "prepared":
            actual = observation.get("volume_binding")
            _require(type(actual) is dict, "missing actual guest volume inventory")
            _require(actual.get("device_serial") == self.binding.device_serial
                     and actual.get("root") == self.binding.root and actual.get("unit") == self.binding.unit,
                     "guest device/root/unit binding mismatch")
            for key in ("disk_number", "partition_number"):
                _require(type(actual.get(key)) is int and actual[key] >= 0, "missing actual disk/partition")
            _require(actual.get("filesystem") == "NTFS" and actual.get("is_boot") is False
                     and actual.get("is_system") is False and type(actual.get("volume_unique_id")) is str
                     and bool(actual["volume_unique_id"]), "guest volume selection not independently bound")
            serials = []
            for value in (actual.get("volume_serial"), self.binding.volume_serial):
                _require(type(value) is str and re.fullmatch(r"[0-9A-Fa-f]{1,8}", value.replace("-", "")),
                         "invalid native volume serial")
                serials.append(int(value.replace("-", ""), 16))
            bridge = observation.get("write_probe", {}).get("before", {}).get("bridge_before", {})
            _require(serials[0] == serials[1] and type(bridge.get("volume_serial_u32")) is int
                     and bridge["volume_serial_u32"] == serials[0], "same-FD volume bridge differs from actual disk inventory")
            _require(type(observation.get("volume_binding_file_sha256")) is str
                     and re.fullmatch(r"[0-9a-f]{64}", observation["volume_binding_file_sha256"]),
                     "actual guest volume inventory bytes not bound")
        if event["stage"] == "before_candidate_hold":
            self.arm()
        elif event["stage"] == "candidate_hold":
            self.clear()
        elif event["stage"] == "failure":
            self.cancel("guest reported failure")
            return None
        command = protocol.COMMANDS.get(event["stage"])
        if command is None:
            return None
        raw = protocol.encode_command(event, command)
        self._pending = raw
        self._emit("command-prepared", {"command": json.loads(raw)})
        return raw

    def sent(self, raw):
        _require(raw == self._pending and self._pending is not None, "stale or mismatched ack send")
        self.session.accept_command(raw)
        self._emit("command-sent", {"command": json.loads(raw)})
        self._pending = None

    def cancel(self, reason):
        """Clear at most once; retain uncertainty and never release the child."""
        try:
            try:
                self._emit("cancelled", {"reason": str(reason)[:8192], "resident": self.resident()})
            finally:
                if self.state in ("armed", "arm-uncertain"):
                    self.clear()
        finally:
            self.state = "refused"
            self.state_epoch += 1


def drive_mailbox(controller, qga, event_path, command_path, *, timeout=120,
                  clock=time.monotonic, sleep=time.sleep, cancel=lambda: False):
    """Read append-only event files, deliver each exact ack once; no replay.

    Bootstrap must already have exclusively created both mailbox paths. A
    missing/unreadable file is an actual failure, never a presumed empty file.
    The caller separately retains QGA process exit/output and partial artifacts.
    """
    _require(0 < timeout <= 300, "invalid mailbox deadline")
    deadline, prior, consumed = clock() + timeout, b"", 0
    try:
        for _ in range(MAX_POLLS):
            _require(not cancel() and clock() < deadline, "mailbox cancelled or deadline")
            data = qga.read_file(event_path)
            _require(data.startswith(prior), "event mailbox rewritten or truncated")
            prior = data
            while b"\n" in data[consumed:]:
                end = data.index(b"\n", consumed) + 1
                raw = data[consumed:end]
                consumed = end
                ack = controller.accept(protocol.parse_event(raw))
                if ack is not None:
                    qga.append(command_path, ack)
                    controller.sent(ack)
                if controller.session.complete:
                    _require(consumed == len(data), "unexpected event after final")
                    return controller.resident()
            _require(len(data) - consumed <= protocol.MAX_EVENT_BYTES, "unterminated event exceeds bound")
            sleep(.05)
        raise HostError("mailbox poll bound")
    except Exception as exc:
        controller.cancel(type(exc).__name__ + ": " + str(exc))
        raise


class _LiteralLoopbackHttpServer(http.server.HTTPServer):
    """Bind the fixed IPv4 loopback address without reverse-DNS discovery."""
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


class HttpEndpoint:
    """Existing disposable-guest NAT topology with an exact finite endpoint.

    Assets are bytes loaded by the current parent before serving, not paths
    reread on GET. Each POST is the raw outer event; the response is its exact
    command or a bounded acknowledgement. There is no queue, replay, credential,
    authority import or automatic guest launch. Bind only to host loopback.
    """
    def __init__(self, controller, assets, *, port, timeout=120, artifacts=None,
                 artifact_sink=None, required_files=(), require_export=False, export_timeout=120):
        _require(type(port) is int and 1024 <= port <= 65535 and 0 < timeout <= 300,
                 "invalid HTTP endpoint bounds")
        _require(type(assets) is dict and len(assets) <= 64, "invalid HTTP asset allowlist")
        self.controller = controller
        _require(type(require_export) is bool and 0 < export_timeout <= 120, "invalid export bounds")
        artifacts = {} if artifacts is None else artifacts
        _require(type(artifacts) is dict and len(artifacts) <= 32, "invalid artifact allowlist")
        for name, bound in artifacts.items():
            _require(type(name) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name)
                     and type(bound) is int and 0 <= bound <= 16 * 1024 * 1024,
                     "invalid fixed artifact bound")
        _require(set(required_files).issubset(artifacts), "required files outside allowlist")
        _require(not artifacts or callable(artifact_sink), "exclusive parent artifact sink required")
        _require(not require_export or bool(artifacts), "actual export needs fixed artifacts")
        self.artifacts, self.artifact_sink = dict(artifacts), artifact_sink
        self.required_files = set(required_files)
        self.require_export, self.export_timeout = require_export, export_timeout
        self.uploaded, self.exported_bytes = {}, 0
        self.exit_confirmed, self.export_complete, self.guest_failed = False, False, False
        self.assets = {}
        total = 0
        for route, data in assets.items():
            _require(type(route) is str and re.fullmatch(r"/[A-Za-z0-9_.-]{1,100}", route)
                     and type(data) is bytes and len(data) <= 64 * 1024 * 1024,
                     "invalid immutable HTTP asset")
            total += len(data)
            self.assets[route] = data
        _require(total <= 128 * 1024 * 1024, "HTTP assets exceed total bound")
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.deadline = time.monotonic() + timeout
        self.failure = None
        self.requests = 0
        endpoint = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(min(5, max(.001, endpoint.deadline - time.monotonic())))
                # Socket idle timeouts alone allow a trickled header/body to
                # reset the wait forever. This separate total receive ceiling
                # can close the connection without waiting for endpoint.lock.
                def expire_receive():
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                self.receive_timer = threading.Timer(
                    min(5, max(.001, endpoint.deadline - time.monotonic())), expire_receive)
                self.receive_timer.daemon = True
                self.receive_timer.start()

            def finish(self):
                self.receive_timer.cancel()
                super().finish()

            def _reply(self, status, data):
                self.send_response(status)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                written = self.wfile.write(data)
                _require(written == len(data), "partial HTTP response")
                self.wfile.flush()
                self.close_connection = True

            def _body(self, length):
                deadline = min(endpoint.deadline, time.monotonic() + 5)
                data = bytearray()
                while len(data) < length:
                    remaining = deadline - time.monotonic()
                    _require(remaining > 0, "HTTP body absolute deadline")
                    self.connection.settimeout(min(.5, remaining))
                    chunk = self.rfile.read1(min(CHUNK_BYTES, length - len(data)))
                    _require(bool(chunk), "short HTTP event")
                    data.extend(chunk)
                return bytes(data)

            def do_GET(self):
                with endpoint.lock:
                    self.receive_timer.cancel()
                    endpoint.requests += 1
                    try:
                        _require(endpoint.requests <= 128, "HTTP request count exhausted")
                        if endpoint.failure is not None or time.monotonic() >= endpoint.deadline:
                            self._reply(410, b"expired\n")
                        elif self.path in endpoint.assets:
                            self._reply(200, endpoint.assets[self.path])
                        else:
                            self._reply(404, b"unknown asset\n")
                    except Exception as exc:
                        endpoint.failure = {"type": type(exc).__name__, "message": str(exc)[:8192]}
                        try:
                            controller.cancel("HTTP asset transfer failed: " + str(exc))
                        finally:
                            endpoint.stop.set()

            def do_POST(self):
                with endpoint.lock:
                    try:
                        endpoint.requests += 1
                        _require(endpoint.requests <= 128, "HTTP request count exhausted")
                        _require(endpoint.failure is None and time.monotonic() < endpoint.deadline,
                                 "HTTP attempt expired/refused")
                        event_route = "/event/" + controller.binding.unit
                        artifact_prefix = "/artifact/" + controller.binding.unit + "/"
                        export_route = "/export-complete/" + controller.binding.unit
                        is_artifact = self.path.startswith(artifact_prefix)
                        artifact_name = self.path[len(artifact_prefix):] if is_artifact else None
                        _require(self.path in (event_route, export_route) or
                                 (is_artifact and artifact_name in endpoint.artifacts),
                                 "wrong current attempt endpoint")
                        values = self.headers.get_all("Content-Length", [])
                        _require(len(values) == 1 and values[0].isascii() and values[0].isdigit()
                                 and self.headers.get("Transfer-Encoding") is None,
                                 "unsupported HTTP framing")
                        length = int(values[0])
                        if is_artifact:
                            _require(endpoint.exit_confirmed and artifact_name not in endpoint.uploaded,
                                     "artifact before confirmed exit or duplicate upload")
                            _require(0 <= length <= endpoint.artifacts[artifact_name]
                                     and endpoint.exported_bytes + length <= 64 * 1024 * 1024,
                                     "artifact exceeds fixed bound")
                        else:
                            _require(0 < length <= (65536 if self.path == export_route else protocol.MAX_EVENT_BYTES),
                                     "HTTP body exceeds bound")
                        # Never retain the controller lock while waiting on
                        # guest bytes: the independent deadline must be able to
                        # restore the direct child even if this peer disappears.
                        endpoint.lock.release()
                        try:
                            raw = self._body(length)
                        finally:
                            endpoint.lock.acquire()
                        _require(len(raw) == length, "short HTTP event")
                        _require(endpoint.failure is None and time.monotonic() < endpoint.deadline,
                                 "HTTP current-parent deadline during body")
                        self.receive_timer.cancel()
                        if is_artifact:
                            sha = hashlib.sha256(raw).hexdigest()
                            _require(self.headers.get_all("X-Imageinfo-Sha256", []) == [sha], "artifact hash header mismatch")
                            # Callback must exclusively create the reviewed fixed
                            # destination. A partial callback failure is retained;
                            # the upload is never replayed or resumed.
                            endpoint.artifact_sink(artifact_name, raw)
                            value = {"name": artifact_name, "bytes": length, "sha256": sha}
                            endpoint.uploaded[artifact_name] = value
                            endpoint.exported_bytes += length
                            controller._emit("http-artifact", value)
                            self._reply(200, b"{}\n")
                            return
                        if self.path == export_route:
                            _require(endpoint.exit_confirmed and (controller.session.complete or endpoint.guest_failed)
                                     and not endpoint.export_complete,
                                     "export completion before final or duplicate")
                            value = json.loads(raw, object_pairs_hook=protocol.worker_protocol._pairs)
                            _require(type(value) is dict and set(value) == {"schema", "exit_confirmed", "files", "missing"}
                                     and value["schema"] == "imageinfo-0219-http-export-v1"
                                     and value["exit_confirmed"] is True, "invalid export manifest")
                            _require(type(value["files"]) is list and type(value["missing"]) is list
                                     and len(value["files"]) + len(value["missing"]) == len(endpoint.artifacts),
                                     "incomplete export denominator")
                            names = set()
                            for item in value["files"]:
                                _require(type(item) is dict and set(item) == {"name", "bytes", "sha256", "guest_path"},
                                         "invalid exported file")
                                name = item["name"]
                                _require(type(name) is str and name in endpoint.uploaded and name not in names
                                         and type(item["bytes"]) is int
                                         and type(item["sha256"]) is str
                                         and {k: item[k] for k in ("name", "bytes", "sha256")} == endpoint.uploaded[name],
                                         "export manifest differs from received bytes")
                                _path(item["guest_path"])
                                names.add(name)
                            _require(endpoint.required_files.issubset(names), "required captures not exported")
                            for item in value["missing"]:
                                _require(type(item) is dict and set(item) == {"name", "status", "error", "guest_path"},
                                         "invalid missing artifact")
                                name = item["name"]
                                _require(type(name) is str and name in endpoint.artifacts and name not in names
                                         and name not in endpoint.uploaded and item["status"] in ("absent", "error")
                                         and (item["error"] is None or type(item["error"]) is dict), "invalid missing artifact status")
                                _path(item["guest_path"])
                                names.add(name)
                            _require(names == set(endpoint.artifacts), "export allowlist denominator changed")
                            controller._emit("http-export", value)
                            self._reply(200, b"{}\n")
                            endpoint.export_complete = True
                            endpoint.stop.set()
                            return
                        controller._emit("http-request", {"method": "POST", "path": self.path,
                                                         "body_hex": raw.hex()})
                        event = protocol.parse_event(raw)
                        command = controller.accept(event)
                        response = command if command is not None else b"{}\n"
                        self._reply(200, response)
                        controller._emit("http-response", {"status": 200, "body_hex": response.hex()})
                        if command is not None:
                            controller.sent(command)
                        if event["stage"] == "exited":
                            endpoint.exit_confirmed = True
                        if event["stage"] == "failure":
                            endpoint.guest_failed = True
                            endpoint.exit_confirmed = event["observation"].get("exit_confirmed") is True
                            if endpoint.require_export and endpoint.exit_confirmed:
                                endpoint.deadline = time.monotonic() + endpoint.export_timeout
                            else:
                                endpoint.stop.set()
                        if controller.session.complete:
                            if endpoint.require_export:
                                endpoint.deadline = time.monotonic() + endpoint.export_timeout
                            else:
                                endpoint.stop.set()
                    except Exception as exc:
                        endpoint.failure = {"type": type(exc).__name__, "message": str(exc)[:8192]}
                        try:
                            controller.cancel(type(exc).__name__ + ": " + str(exc))
                        except Exception as cleanup:
                            endpoint.failure["clear_error"] = {"type": type(cleanup).__name__,
                                                               "message": str(cleanup)[:8192]}
                        endpoint.stop.set()
                        try:
                            self._reply(400, b"attempt refused\n")
                        except OSError:
                            pass

        self.server = _LiteralLoopbackHttpServer(("127.0.0.1", port), Handler)
        self.thread = None
        self.watchdog = None
        controller._emit("http-assets", {"port": port, "assets": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in self.assets.items()}, "artifacts": self.artifacts,
            "required_files": sorted(self.required_files), "require_export": self.require_export,
            "export_timeout": self.export_timeout})

    def start(self):
        _require(self.thread is None, "HTTP endpoint already started")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        def watch():
            while not self.stop.wait(.1):
                if time.monotonic() >= self.deadline:
                    self.cancel("HTTP current-parent deadline")
                    return
        self.watchdog = threading.Thread(target=watch, daemon=True)
        self.watchdog.start()

    def wait(self):
        """Current parent waits; deadline clears even if guest never posts again."""
        while not self.stop.wait(.1):
            if time.monotonic() >= self.deadline:
                self.cancel("HTTP current-parent deadline")
        _require(self.failure is None and not self.guest_failed and self.controller.session.complete
                 and (not self.require_export or self.export_complete),
                 "HTTP cell partial/refused: " + str(self.failure))
        return self.controller.resident()

    def cancel(self, reason):
        with self.lock:
            self.failure = {"type": "Cancelled", "message": str(reason)[:8192]}
            try:
                self.controller.cancel(reason)
            finally:
                self.stop.set()

    def close(self):
        if not self.stop.is_set():
            self.cancel("HTTP endpoint closed before confirmed final")
        if self.thread is not None:
            self.server.shutdown()
            self.thread.join(timeout=10)
        if self.watchdog is not None:
            self.watchdog.join(timeout=10)
        self.server.server_close()

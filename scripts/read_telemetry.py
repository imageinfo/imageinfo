"""Bounded Windows direct-child counters, separate from elapsed-only v1 records.

No process-tree containment, physical I/O inference, or allocation quota.
"""
import ctypes
import os
import time

REVISION = "read-telemetry-v2"
MAX_SAMPLES = 2048
MAX_PROCESSES = 32768
METRICS = {
    "userCpuNs": ("ns", "GetProcessTimes user FILETIME * 100"),
    "systemCpuNs": ("ns", "GetProcessTimes kernel FILETIME * 100"),
    "workingSetBytes": ("bytes", "GetProcessMemoryInfo WorkingSetSize"),
    "peakWorkingSetBytes": ("bytes", "GetProcessMemoryInfo PeakWorkingSetSize; OS lifetime high-water"),
    "privateCommitBytes": ("bytes", "GetProcessMemoryInfo PrivateUsage; committed private memory, not private RSS"),
    "readOperations": ("operations", "GetProcessIoCounters ReadOperationCount"),
    "writeOperations": ("operations", "GetProcessIoCounters WriteOperationCount"),
    "otherOperations": ("operations", "GetProcessIoCounters OtherOperationCount"),
    "readTransferBytes": ("bytes", "GetProcessIoCounters ReadTransferCount; logical process transfers"),
    "writeTransferBytes": ("bytes", "GetProcessIoCounters WriteTransferCount; logical process transfers"),
    "otherTransferBytes": ("bytes", "GetProcessIoCounters OtherTransferCount; logical process transfers"),
    "physicalIoBytes": ("bytes", "unavailable: process transfer counters do not measure device traffic"),
}


class WindowsCounters:
    """Typed stdlib ctypes calls against the Popen-owned process handle.

    The handle is borrowed, never closed here. Only snapshot handles are owned.
    Counter APIs do not request privilege or change the child/host configuration.
    """
    def __init__(self, process):
        from ctypes import wintypes as w
        self.pid = process.pid
        self.handle = int(process._handle)  # Windows CPython Popen keeps this handle through wait.
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ps = ctypes.WinDLL("psapi", use_last_error=True)
        size = ctypes.c_size_t

        class Memory(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD)] + [
                (name, size) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                         "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                         "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Entry(ctypes.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                        ("th32DefaultHeapID", size), ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
                        ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG),
                        ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]

        self.Memory, self.IO, self.Entry = Memory, IO, Entry
        self.FILETIME = w.FILETIME
        definitions = [
            (self.k.GetProcessTimes, [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4, w.BOOL),
            (self.k.GetProcessIoCounters, [w.HANDLE, ctypes.POINTER(IO)], w.BOOL),
            (self.ps.GetProcessMemoryInfo, [w.HANDLE, ctypes.POINTER(Memory), w.DWORD], w.BOOL),
            (self.k.CreateToolhelp32Snapshot, [w.DWORD, w.DWORD], w.HANDLE),
            (self.k.Process32FirstW, [w.HANDLE, ctypes.POINTER(Entry)], w.BOOL),
            (self.k.Process32NextW, [w.HANDLE, ctypes.POINTER(Entry)], w.BOOL),
            (self.k.CloseHandle, [w.HANDLE], w.BOOL),
        ]
        for function, args, result in definitions:
            function.argtypes, function.restype = args, result

    def read(self):
        values = {key: None for key in METRICS}
        errors = {}
        times = [self.FILETIME() for _ in range(4)]
        if self.k.GetProcessTimes(self.handle, *[ctypes.byref(t) for t in times]):
            for name, t in zip(("systemCpuNs", "userCpuNs"), times[2:]):
                values[name] = ((t.dwHighDateTime << 32) | t.dwLowDateTime) * 100
        else:
            errors["cpu"] = f"winerror:{ctypes.get_last_error()}"
        memory = self.Memory()
        memory.cb = ctypes.sizeof(memory)
        if self.ps.GetProcessMemoryInfo(self.handle, ctypes.byref(memory), memory.cb):
            values.update(workingSetBytes=memory.WorkingSetSize, peakWorkingSetBytes=memory.PeakWorkingSetSize,
                          privateCommitBytes=memory.PrivateUsage)
        else:
            errors["memory"] = f"winerror:{ctypes.get_last_error()}"
        io = self.IO()
        if self.k.GetProcessIoCounters(self.handle, ctypes.byref(io)):
            for name, field in zip(("readOperations", "writeOperations", "otherOperations", "readTransferBytes",
                                    "writeTransferBytes", "otherTransferBytes"), self.IO._fields_):
                values[name] = getattr(io, field[0])
        else:
            errors["logicalIo"] = f"winerror:{ctypes.get_last_error()}"
        errors["physicalIoBytes"] = "not instrumented; logical transfers are not device traffic"
        return values, errors

    def descendants(self):
        snapshot = self.k.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS only.
        if snapshot == ctypes.c_void_p(-1).value:
            raise OSError(ctypes.get_last_error(), "process snapshot unavailable")
        try:
            entry = self.Entry()
            entry.dwSize = ctypes.sizeof(entry)
            if not self.k.Process32FirstW(snapshot, ctypes.byref(entry)):
                raise OSError(ctypes.get_last_error(), "process enumeration unavailable")
            pairs = []
            while True:
                if len(pairs) >= MAX_PROCESSES:
                    raise OSError("process enumeration bound reached")
                pairs.append((entry.th32ProcessID, entry.th32ParentProcessID))
                if not self.k.Process32NextW(snapshot, ctypes.byref(entry)):
                    if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES.
                        raise OSError(ctypes.get_last_error(), "process enumeration failed")
                    break
            # We need only detect an immediate child: every visible descendant chain
            # with a live parent must cross this edge. Reparenting/short-lived gaps
            # and PID reuse remain limitations, not proof of continuous exclusion.
            return sorted({pid for pid, parent in pairs if parent == self.pid and pid != self.pid})
        finally:
            self.k.CloseHandle(snapshot)


class Observer:
    def __init__(self, interval_ms=10, backend_factory=None):
        if type(interval_ms) is not int or not 1 <= interval_ms <= 1000:
            raise ValueError("sampling interval must be 1..1000 ms")
        self.interval_ms = interval_ms
        self.factory = backend_factory
        self.backend = None
        self.start = None
        self.pid = None
        self.samples = []
        self.errors = []
        self.stop_reason = None
        self.membership = "unavailable"
        self.descendant_pids = []
        self.next_sample = 0
        self.overhead = 0

    def launch_failed(self, start):
        self.start = start
        self.errors.append("launch-error: no direct child counters")

    def attach(self, process, start):
        self.start, self.pid = start, process.pid
        try:
            if self.factory is not None:
                self.backend = self.factory(process)
            elif os.name == "nt":
                self.backend = WindowsCounters(process)
            else:
                raise OSError("unsupported platform: only Windows counters qualified")
        except (OSError, AttributeError) as error:
            self.errors.append(f"counter-setup:{type(error).__name__}:{error}")
        self.sample()

    def sample(self, final=False):
        if self.start is None or self.backend is None:
            return
        now = time.perf_counter_ns()
        if not final and now < self.next_sample:
            return
        # Reserve the last slot for the direct-exit snapshot, including at limit.
        if len(self.samples) >= MAX_SAMPLES - (0 if final else 1):
            self.stop_reason = "telemetry-limit"
            return
        self.next_sample = now + self.interval_ms * 1_000_000
        errors = {}
        values = {key: None for key in METRICS}
        try:
            values, errors = self.backend.read()
        except (OSError, ValueError) as error:
            errors["counterRead"] = f"{type(error).__name__}:{error}"
        errors["physicalIoBytes"] = "not instrumented; logical transfers are not device traffic"
        try:
            descendants = self.backend.descendants()
            if descendants:
                self.membership = "invalid-descendants"
                self.descendant_pids = sorted(set(self.descendant_pids + descendants))[:MAX_PROCESSES]
            elif self.membership == "unavailable" and not any("membership" in x["errors"] for x in self.samples):
                self.membership = "direct-only-observed"
        except OSError as error:
            errors["membership"] = f"{type(error).__name__}:{error}"
            if self.membership != "invalid-descendants":
                self.membership = "unavailable"
        end = time.perf_counter_ns()
        duration = end - now
        self.overhead += duration
        self.samples.append({"beginOffsetNs": now - self.start, "endOffsetNs": end - self.start,
                             "final": final, "values": values, "errors": errors})

    def report(self):
        # Endpoint failures never get replaced by earlier counters or zero values.
        valid = (bool(self.samples) and self.membership == "direct-only-observed" and not self.errors
                 and self.stop_reason is None and all(
                     not (set(s["errors"]) - {"physicalIoBytes"}) for s in self.samples))
        maxima = {key: max((s["values"][key] for s in self.samples if s["values"][key] is not None), default=None)
                  for key in ("workingSetBytes", "privateCommitBytes")}
        return {"pid": self.pid, "requestedIntervalMs": self.interval_ms, "maxSamples": MAX_SAMPLES,
                "membership": self.membership, "observedDescendantPids": self.descendant_pids,
                "valid": valid, "errors": self.errors, "stopReason": self.stop_reason,
                "observerWallNs": self.overhead, "sampledMaxima": maxima, "samples": self.samples}


def extension(elapsed_record, telemetry, purpose="metadata-read"):
    import read_benchmark as b
    elapsed_record["schemaVersion"] = 2
    elapsed_record["collectorRevision"] = "read-collector-v2-elapsed-core"
    elapsed_record["unavailableReason"] = "elapsed-only core; resource observations and reasons are in the v2 telemetry companion"
    return {"schemaVersion": 2, "collectorRevision": REVISION, "purpose": purpose,
            "telemetryDriverSha256": b.digest(__file__), "elapsedRecord": elapsed_record,
            "scope": "direct Popen-owned process handle; no descendants included",
            "method": "Windows stdlib ctypes; GetProcessTimes/GetProcessMemoryInfo/GetProcessIoCounters; Toolhelp process snapshots",
            "alignment": "sample begin/end perf_counter_ns offsets from before Popen; counters read sequentially inside each bracket",
            "overhead": "observerWallNs sums counter and membership snapshot wall time; polling/capture overhead also included in elapsed; none subtracted",
            "membershipLimit": "sampled immediate-child detection only; short-lived/reparented processes and PID reuse may escape; no containment",
            "metrics": {key: {"unit": unit, "method": method} for key, (unit, method) in METRICS.items()},
            "telemetry": telemetry}

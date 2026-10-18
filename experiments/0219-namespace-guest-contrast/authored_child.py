"""Authored Python-only wire actor; never loads a worker or native API."""
import json
import os
import sys
import time


def emit(value):
    sys.stdout.buffer.write(value)
    sys.stdout.buffer.flush()


def main():
    mode, unit = sys.argv[1:3]
    if mode == "wait":
        time.sleep(10)
        return 0
    if mode == "partial":
        emit(b"partial")
        return 0
    if mode == "stdout_overflow":
        emit(b"x" * 65536 + b"\n")
        return 0
    if mode == "stderr_overflow":
        sys.stderr.buffer.write(b"x" * 65536)
        sys.stderr.buffer.flush()
        return 0
    if mode == "lost_input":
        os.close(0)
        emit(b"input_closed\n")
        time.sleep(10)
        return 0
    if mode == "nonzero":
        return 7
    if mode == "early_eof":
        return 0
    seq = 0

    def event(kind, stage, result=None, gate=False):
        nonlocal seq
        seq += 1
        value = {"v": 1, "unit": unit, "seq": seq, "kind": kind,
                 "stage": stage, "result": result,
                 "bindings": [{"identity": "00", "facts": "ff"}],
                 "committed": False, "production_profile_admitted": False,
                 "raw_admitted": False, "authority_importable": False}
        emit(b"IMAGEINFO218 " + json.dumps(value).encode() + b"\n")
        if gate:
            if mode == "lost_ack" and stage == "create-Candidate":
                time.sleep(10)
                return False
            raw = sys.stdin.buffer.readline(1025)
            expected = {key: value[key] for key in ("v", "unit", "seq", "stage")}
            expected["command"] = "release" if kind == "candidate_result" else "continue"
            if json.loads(raw) != expected:
                return False
        return True

    success = {"success": True, "failure": None, "native_error_kind": None,
               "native_os_error": None}
    for stage in ("preflight", "create-root", "root-flush", "parent-flush", "create-Candidate"):
        if not event("before_operation", stage, gate=True):
            return 21
        if stage == "create-Candidate":
            failed = {"success": False, "failure": "BackendIo",
                      "native_error_kind": "Other", "native_os_error": 1117}
            if not event("candidate_result", stage, failed, gate=True):
                return 22
            if mode == "exit_race":
                return 0
        else:
            event("operation_result", stage, success)
    event("runtime_result", "runtime",
          {"status": "FailedBeforePublish", "phase": "CandidateCreated",
           "failure": "BackendIo", "publication_possible": False,
           "release_possible": False, "protocol_complete": False,
           "retained_material": True, "pending_cleanup": False, "charged_bytes": 17})
    event("backend_dropped", "backend-drop")
    if mode == "late_stderr":
        sys.stderr.buffer.write(b"x" * 65536)
        sys.stderr.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

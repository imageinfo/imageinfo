"""Tiny authored stdio actor for process controls; never loads the native worker.

The token exchange here is deliberately synthetic. Real observer event and
acknowledgement validation belongs to protocol.py and its separate controls.
"""
from __future__ import annotations

import os
import sys
import time


def emit(value: bytes):
    sys.stdout.buffer.write(value)
    sys.stdout.buffer.flush()


def main():
    mode = sys.argv[1]
    if mode == "wait":
        emit(b"waiting\n")
        time.sleep(10)
    elif mode == "partial":
        emit(b"partial")
    elif mode == "nonzero":
        emit(b"refused\n")
        return 7
    elif mode in ("stdout_overflow", "line_overflow"):
        emit(b"x" * 1024 + b"\n")
    elif mode == "stderr_overflow":
        sys.stderr.buffer.write(b"e" * 1024)
        sys.stderr.buffer.flush()
    elif mode == "lost_input":
        os.close(0)
        emit(b"input_closed\n")
        time.sleep(10)
    elif mode == "event_overflow":
        emit(b"one\ntwo\nthree\n")
    elif mode == "exchange":
        if sys.stdin.buffer.readline(128) != b"request 1\n":
            return 21
        emit(b"paused 1\n")
        if sys.stdin.buffer.readline(128) != b"release 1\n":
            emit(b"ack_refused\n")
            return 22
        emit(b"paused 2\n")
        if sys.stdin.buffer.readline(128) != b"release 2\n":
            emit(b"ack_refused\n")
            return 23
        emit(b"complete\n")
    else:
        return 24
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Finite authored subprocess controls, unrelated to JPEG or private media.

The complete handshake is published only after both pipe prefixes are flushed. Waiting
children never continue without an explicit release file (which tests withhold).
These children create no descendants; this says nothing about descendant cleanup.
"""
import json
import os
from pathlib import Path
import sys
import threading


OUT = b"authored stdout prefix\n"
ERR = b"authored stderr prefix\n"
PARTIAL = b'{"authoredPartial":'


def publish_handshake(handshake, mode):
    """Publish a closed complete JSON file in this fresh single-writer fixture."""
    staged = handshake.with_name(handshake.name + ".staged")
    if handshake.exists():
        raise FileExistsError("authored handshake already exists")
    with staged.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"mode": mode, "pid": os.getpid(), "prefixesFlushed": True}, stream)
    # Same-directory rename is the visibility boundary. The unique fresh test
    # root has one producer; this is not an adversarial publication protocol.
    staged.rename(handshake)


def main():
    mode, handshake_name = sys.argv[1:]
    handshake = Path(handshake_name)
    if mode not in {"normal", "nonzero", "partial", "wait", "overflow", "stderr-overflow"}:
        raise ValueError("unknown authored child mode")
    sys.stdout.buffer.write(PARTIAL if mode == "partial" else OUT)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(ERR)
    sys.stderr.buffer.flush()
    publish_handshake(handshake, mode)
    if mode == "normal":
        return 0
    if mode == "nonzero":
        return 23
    if mode == "partial":
        return 24
    if mode in {"overflow", "stderr-overflow"}:
        # Finite producer, far above the test's logical capture ceiling.
        for _ in range(256):
            pipe = sys.stderr.buffer if mode == "stderr-overflow" else sys.stdout.buffer
            pipe.write(b"X" * 4096)
            pipe.flush()
    # The parent must terminate and reap this direct child. There is no timeout
    # inside the helper that could make a broken parent appear to clean up.
    threading.Event().wait()
    return 99


if __name__ == "__main__":
    raise SystemExit(main())

"""Authored PTY lifecycle controls; no child or real terminal is created."""
import errno
import types
import unittest
from unittest.mock import Mock, patch

import plain_terminal_pty as subject


class PosixDrainTests(unittest.TestCase):
    def capture(self, readiness, chunks, ticks=None, limit=None):
        process = Mock()
        process.poll.return_value = 0
        process.wait.return_value = 0
        select = Mock(side_effect=[([10] if ready else [], [], []) for ready in readiness])
        modules = {
            "fcntl": types.SimpleNamespace(ioctl=Mock()),
            "pty": types.SimpleNamespace(openpty=lambda: (10, 11)),
            "termios": types.SimpleNamespace(TIOCSWINSZ=0),
            "select": types.SimpleNamespace(select=select),
        }
        with patch.dict("sys.modules", modules), patch.object(subject.os, "name", "posix"), \
                patch.object(subject.os, "close"), patch.object(subject.os, "read", side_effect=chunks), \
                patch.object(subject.subprocess, "Popen", return_value=process), \
                patch.object(subject.time, "monotonic", side_effect=ticks or (lambda: 0)), \
                patch.object(subject, "LIMIT", subject.LIMIT if limit is None else limit):
            return subject.capture(["authored"], ".", 40, {}, seconds=10)

    def test_exited_child_empty_poll_does_not_drop_later_tail_before_eof(self):
        self.assertEqual(self.capture([False, True, True], [b"retained tail", b""]),
                         (0, b"retained tail", "posix-pty"))

    def test_eio_is_terminal_eof_after_retaining_bytes(self):
        self.assertEqual(self.capture([True, True], [b"tail", OSError(errno.EIO, "PTY EOF")]),
                         (0, b"tail", "posix-pty"))

    def test_exited_child_without_eof_still_obeys_original_deadline(self):
        with self.assertRaisesRegex(AssertionError, "PTY deadline exceeded"):
            self.capture([False], [], ticks=[0, 0, 11])

    def test_capture_bound_and_non_eio_errors_remain_failures(self):
        with self.assertRaisesRegex(AssertionError, "PTY capture limit exceeded"):
            self.capture([True], [b"too long"], limit=2)
        with self.assertRaises(PermissionError):
            self.capture([True], [PermissionError(errno.EACCES, "authored")])


if __name__ == "__main__":
    unittest.main()

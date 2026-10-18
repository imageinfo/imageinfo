"""Bounded owned-child PTY capture for #0138; no desktop input or shell.

POSIX uses a fresh PTY. Windows uses ConPTY directly via the standard library.
ConPTY host-generated VT bytes are retained separately from redirected app bytes.
"""
import os
import subprocess
import threading
import time

LIMIT = 1024 * 1024


def capture(argv, cwd, columns, env, seconds=10):
    if os.name == 'nt':
        return _windows(argv, cwd, columns, env, seconds)
    import fcntl
    import pty
    import select
    import struct
    import termios
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 100, columns, 0, 0))
    process = None
    data = bytearray()
    deadline = time.monotonic() + seconds
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=slave,
                                   stdout=slave, stderr=slave, close_fds=True)
        os.close(slave)
        slave = None
        while True:
            assert time.monotonic() < deadline, 'PTY deadline exceeded'
            if select.select([master], [], [], .05)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    if error.errno == 5:
                        break
                    raise
                if not chunk:
                    break
                data.extend(chunk)
                assert len(data) <= LIMIT, 'PTY capture limit exceeded'
            # Child exit does not establish that the PTY has drained. Wait for
            # EOF/EIO under the same deadline, including delayed final output.
        return process.wait(timeout=2), bytes(data), 'posix-pty'
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        os.close(master)
        if slave is not None:
            os.close(slave)


def _windows(argv, cwd, columns, env, seconds):
    import ctypes as c
    from ctypes import wintypes as w
    kernel = c.WinDLL('kernel32', use_last_error=True)
    H = w.HANDLE
    class COORD(c.Structure):
        _fields_ = [('X', c.c_short), ('Y', c.c_short)]
    class STARTUPINFO(c.Structure):
        _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR),
                    ('title', w.LPWSTR), ('x', w.DWORD), ('y', w.DWORD),
                    ('xs', w.DWORD), ('ys', w.DWORD), ('xc', w.DWORD),
                    ('yc', w.DWORD), ('fill', w.DWORD), ('flags', w.DWORD),
                    ('show', w.WORD), ('reserved2size', w.WORD),
                    ('reserved2', c.POINTER(c.c_byte)), ('input', H),
                    ('output', H), ('error', H)]
    class STARTUPINFOEX(c.Structure):
        _fields_ = [('StartupInfo', STARTUPINFO), ('attributes', c.c_void_p)]
    class PROCESSINFO(c.Structure):
        _fields_ = [('process', H), ('thread', H), ('pid', w.DWORD), ('tid', w.DWORD)]
    def declare(name, args, result=w.BOOL):
        fn = getattr(kernel, name)
        fn.argtypes, fn.restype = args, result
        return fn
    pipe = declare('CreatePipe', [c.POINTER(H), c.POINTER(H), c.c_void_p, w.DWORD])
    close = declare('CloseHandle', [H])
    create = declare('CreatePseudoConsole', [COORD, H, H, w.DWORD, c.POINTER(H)], c.c_long)
    close_pty = declare('ClosePseudoConsole', [H], None)
    init = declare('InitializeProcThreadAttributeList', [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)])
    update = declare('UpdateProcThreadAttribute', [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p])
    delete = declare('DeleteProcThreadAttributeList', [c.c_void_p], None)
    spawn = declare('CreateProcessW', [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR, c.POINTER(STARTUPINFOEX), c.POINTER(PROCESSINFO)])
    read = declare('ReadFile', [H, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p])
    wait = declare('WaitForSingleObject', [H, w.DWORD], w.DWORD)
    terminate = declare('TerminateProcess', [H, w.UINT])
    code = declare('GetExitCodeProcess', [H, c.POINTER(w.DWORD)])
    def check(result):
        if not result:
            raise c.WinError(c.get_last_error())
    ir, iw, out_r, out_w, pc = H(), H(), H(), H(), H()
    pi = PROCESSINFO()
    attributes = None
    reader = None
    data = bytearray()
    overflow = threading.Event()
    try:
        check(pipe(c.byref(ir), c.byref(iw), None, 0))
        check(pipe(c.byref(out_r), c.byref(out_w), None, 0))
        hr = create(COORD(columns, 100), ir, out_w, 0, c.byref(pc))
        assert hr == 0, f'CreatePseudoConsole HRESULT {hr}'
        close(ir); ir = H()
        close(out_w); out_w = H()
        size = c.c_size_t()
        init(None, 1, 0, c.byref(size))
        attributes = c.create_string_buffer(size.value)
        check(init(attributes, 1, 0, c.byref(size)))
        check(update(attributes, 0, 0x00020016, pc, c.sizeof(H), None, None))
        si = STARTUPINFOEX()
        si.StartupInfo.cb = c.sizeof(si)
        si.StartupInfo.flags = 0x00000100
        si.attributes = c.cast(attributes, c.c_void_p)
        command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
        environment = c.create_unicode_buffer('\0'.join(f'{k}={v}' for k, v in sorted(env.items())) + '\0\0')
        check(spawn(None, command, None, None, False, 0x00080000 | 0x00000400,
                    environment, str(cwd), c.byref(si), c.byref(pi)))
        def drain():
            buffer = c.create_string_buffer(65536)
            count = w.DWORD()
            while read(out_r, buffer, len(buffer), c.byref(count), None) and count.value:
                if len(data) + count.value > LIMIT:
                    overflow.set()
                elif not overflow.is_set():
                    data.extend(buffer.raw[:count.value])
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        result = wait(pi.process, int(seconds * 1000))
        if result != 0:
            terminate(pi.process, 124)
            wait(pi.process, 2000)
            raise AssertionError('PTY child deadline exceeded')
        status = w.DWORD()
        check(code(pi.process, c.byref(status)))
        close_pty(pc); pc = H()
        reader.join(timeout=3)
        assert not reader.is_alive(), 'PTY output did not close'
        assert not overflow.is_set(), 'PTY capture limit exceeded'
        return status.value, bytes(data), 'windows-conpty'
    finally:
        if pi.process and wait(pi.process, 0) != 0:
            terminate(pi.process, 124)
            wait(pi.process, 2000)
        if pc:
            close_pty(pc)
        if attributes is not None:
            delete(attributes)
        for handle in (ir, iw, out_r, out_w, pi.process, pi.thread):
            if handle:
                close(handle)

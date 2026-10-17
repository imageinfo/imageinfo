"""Test-only #0140 native child launcher; never imported by production code.

Windows CreateProcessW preserves deliberately invalid STARTUPINFO handles rather
than letting subprocess repair or reject them before the child runs. POSIX uses
an owned child's pre-exec fd manipulation. No shell or privileged helper is used.
"""
import os
from pathlib import Path
import subprocess


LIMIT = 8192
SECONDS = 10


def launch(binary, case, fixture, captures):
    """Return actual status/stdout/stderr and injection metadata; retain captures."""
    captures.mkdir()
    out = captures / 'stdout.bin'
    err = captures / 'stderr.bin'
    # Files are opened before the invalid/closed-handle construction, preventing
    # our own subsequent opens from reusing that just-closed handle value.
    fds = []

    def opened(path, flags):
        fd = os.open(path, flags | getattr(os, 'O_BINARY', 0), 0o600)
        fds.append(fd)
        return fd

    output = opened(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    errors = opened(err, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    source = opened(fixture / 'empty', os.O_RDONLY)
    detail = {'stdin': case, 'stdout': 'capture-file'}
    try:
        if case == 'eof-pipe':
            source, writer = os.pipe()
            fds.append(source)
            os.close(writer)
        elif case == 'stdin-write-only':
            source = opened(fixture / 'guard', os.O_WRONLY)
        elif case == 'stdin-directory':
            source = opened(fixture, os.O_RDONLY | os.O_DIRECTORY)
        elif case == 'stdout-read-only':
            output = opened(fixture / 'guard', os.O_RDONLY)
            detail['stdout'] = 'read-only-file'
        elif case == 'stdout-broken-pipe':
            reader, output = os.pipe()
            fds.append(output)
            os.close(reader)
            detail['stdout'] = 'pipe-with-no-reader'
        if os.name == 'nt':
            status, native = _windows(binary, case, fixture, source, output, errors)
            detail.update(native)
        else:
            def setup():
                if case == 'stdin-closed':
                    os.close(0)
            child = subprocess.Popen([str(binary), 'session', 'read'], cwd=fixture,
                                     stdin=source, stdout=output, stderr=errors,
                                     preexec_fn=setup, close_fds=True)
            try:
                try:
                    status = child.wait(timeout=SECONDS)
                except subprocess.TimeoutExpired:
                    status = None
                    detail['watchdogTerminated'] = True
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=2)
        assert out.stat().st_size <= LIMIT and err.stat().st_size <= LIMIT, 'capture bound'
        return status, out.read_bytes(), err.read_bytes(), detail
    finally:
        for fd in fds:
            os.close(fd)


def _windows(binary, case, cwd, source, output, errors):
    import ctypes as c
    from ctypes import wintypes as w
    import msvcrt

    kernel = c.WinDLL('kernel32', use_last_error=True)
    H = w.HANDLE

    class STARTUPINFO(c.Structure):
        _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR),
                    ('title', w.LPWSTR), ('x', w.DWORD), ('y', w.DWORD),
                    ('xs', w.DWORD), ('ys', w.DWORD), ('xc', w.DWORD),
                    ('yc', w.DWORD), ('fill', w.DWORD), ('flags', w.DWORD),
                    ('show', w.WORD), ('reserved2size', w.WORD),
                    ('reserved2', c.POINTER(c.c_byte)), ('input', H),
                    ('output', H), ('error', H)]

    class PROCESSINFO(c.Structure):
        _fields_ = [('process', H), ('thread', H), ('pid', w.DWORD), ('tid', w.DWORD)]

    def declare(name, args, result=w.BOOL):
        fn = getattr(kernel, name)
        fn.argtypes, fn.restype = args, result
        return fn

    spawn = declare('CreateProcessW', [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p,
                    w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR,
                    c.POINTER(STARTUPINFO), c.POINTER(PROCESSINFO)])
    wait = declare('WaitForSingleObject', [H, w.DWORD], w.DWORD)
    exit_code = declare('GetExitCodeProcess', [H, c.POINTER(w.DWORD)])
    terminate = declare('TerminateProcess', [H, w.UINT])
    close = declare('CloseHandle', [H])
    information = declare('GetHandleInformation', [H, c.POINTER(w.DWORD)])
    for fd in (source, output, errors):
        os.set_inheritable(fd, True)
    inp = msvcrt.get_osfhandle(source)
    detail = {'launcher': 'CreateProcessW-STARTF_USESTDHANDLES'}
    if case == 'stdin-null':
        inp = 0
    elif case == 'stdin-invalid':
        inp = c.c_void_p(-1).value
    elif case == 'stdin-closed':
        closed_fd = os.open(cwd / 'empty', os.O_RDONLY | os.O_BINARY)
        inp = msvcrt.get_osfhandle(closed_fd)
        os.close(closed_fd)
        detail['inputHandleClosedBeforeSpawn'] = True
    if case == 'stdin-null':
        flags = w.DWORD()
        valid = bool(information(inp, c.byref(flags)))
        native_error = c.get_last_error()
        assert not valid and native_error == 6, 'expected invalid input handle before spawn'
        detail.update(preSpawnHandleValid=False, preSpawnHandleError=native_error)
    if case == 'stdin-invalid':
        # INVALID_HANDLE_VALUE is also the current-process pseudo-handle for
        # some handle-management APIs, so GetHandleInformation is no oracle.
        detail['inputHandleValue'] = 'INVALID_HANDLE_VALUE'
    startup = STARTUPINFO()
    startup.cb = c.sizeof(startup)
    startup.flags = 0x100  # STARTF_USESTDHANDLES
    startup.input, startup.output, startup.error = inp, msvcrt.get_osfhandle(output), msvcrt.get_osfhandle(errors)
    process = PROCESSINFO()
    command = c.create_unicode_buffer(subprocess.list2cmdline([str(binary), 'session', 'read']))
    if not spawn(str(binary), command, None, None, True, 0x08000000, None,
                 str(cwd), c.byref(startup), c.byref(process)):
        raise c.WinError(c.get_last_error())
    try:
        waited = wait(process.process, SECONDS * 1000)
        if waited != 0:
            assert terminate(process.process, 124), c.WinError(c.get_last_error())
            assert wait(process.process, 2000) == 0, 'terminated child did not stop'
            if waited != 258:
                raise c.WinError(c.get_last_error())
            return None, {**detail, 'watchdogTerminated': True,
                          'watchdogSeconds': SECONDS, 'forcedExitCode': 124}
        status = w.DWORD()
        assert exit_code(process.process, c.byref(status)), c.WinError(c.get_last_error())
        return status.value, detail
    finally:
        close(process.thread)
        close(process.process)

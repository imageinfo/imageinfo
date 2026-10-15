"""Bounded marker-only Win32 calls; no metadata setters or privilege changes."""
import ctypes
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path


class FileInformation(ctypes.Structure):
    _fields_ = [('attributes', w.DWORD), ('creation', w.FILETIME),
                ('access', w.FILETIME), ('write', w.FILETIME),
                ('volume', w.DWORD), ('sizeHigh', w.DWORD), ('sizeLow', w.DWORD),
                ('links', w.DWORD), ('indexHigh', w.DWORD), ('indexLow', w.DWORD)]


class Native:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Windows marker qualification only')
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.a = ctypes.WinDLL('advapi32', use_last_error=True)
        specs = [(self.k, 'CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                        w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
                 (self.k, 'CloseHandle', [w.HANDLE], w.BOOL),
                 (self.k, 'WriteFile', [w.HANDLE, ctypes.c_void_p, w.DWORD,
                                        ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
                 (self.k, 'ReadFile', [w.HANDLE, ctypes.c_void_p, w.DWORD,
                                       ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
                 (self.k, 'FlushFileBuffers', [w.HANDLE], w.BOOL),
                 (self.k, 'GetFileInformationByHandle', [w.HANDLE, ctypes.POINTER(FileInformation)], w.BOOL),
                 (self.a, 'GetSecurityInfo', [w.HANDLE, ctypes.c_int, w.DWORD,
                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                      ctypes.POINTER(ctypes.c_void_p)], w.DWORD),
                 (self.a, 'ConvertSecurityDescriptorToStringSecurityDescriptorW',
                      [ctypes.c_void_p, w.DWORD, w.DWORD,
                       ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.DWORD)], w.BOOL),
                 (self.k, 'LocalFree', [ctypes.c_void_p], ctypes.c_void_p)]
        for dll, name, arguments, result in specs:
            function = getattr(dll, name)
            function.argtypes = arguments
            function.restype = result
        if ctypes.sizeof(FileInformation) != 52:
            raise RuntimeError('Unexpected SDK structure layout')

    def open(self, path, *, writer=False, write_through=False):
        flags = 0x00200000 | (0x80000000 if write_through else 0)
        handle = self.k.CreateFileW(str(Path(path)), 0xc0020000 if writer else 0x80020000,
                                   1 if writer else 7, None, 1 if writer else 3, flags, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def close(self, handle):
        if not self.k.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def write_marker(self, handle):
        data = ctypes.create_string_buffer(b'3' * 65536)
        count = w.DWORD()
        if not self.k.WriteFile(handle, data, 65536, ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value != 65536:
            raise RuntimeError('Native short marker write')

    def flush(self, handle):
        if not self.k.FlushFileBuffers(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def info(self, handle):
        information = FileInformation()
        if not self.k.GetFileInformationByHandle(handle, ctypes.byref(information)):
            raise ctypes.WinError(ctypes.get_last_error())
        stamp = lambda value: value.dwLowDateTime | value.dwHighDateTime << 32
        return {'identity': f'{information.volume:x}:{(information.indexHigh << 32 | information.indexLow):x}',
                'size': information.sizeHigh << 32 | information.sizeLow,
                'creationTime': stamp(information.creation), 'lastWriteTime': stamp(information.write),
                'attributes': information.attributes, 'links': information.links}

    def security(self, handle):
        descriptor = ctypes.c_void_p()
        result = self.a.GetSecurityInfo(handle, 1, 5, None, None, None, None, ctypes.byref(descriptor))
        if result:
            raise ctypes.WinError(result)
        text = ctypes.c_void_p()
        length = w.DWORD()
        try:
            if not self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    descriptor, 1, 5, ctypes.byref(text), ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not text.value or length.value > 32768:
                raise RuntimeError('Security text bound')
            return ctypes.wstring_at(text)
        finally:
            if text.value:
                self.k.LocalFree(text)
            self.k.LocalFree(descriptor)

    def observe(self, path, retained):
        first = self.info(retained)
        fresh = self.open(path)
        try:
            path_information = self.info(fresh)
            security = self.security(fresh)
            data = ctypes.create_string_buffer(65537)
            count = w.DWORD()
            if not self.k.ReadFile(fresh, data, 65537, ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if count.value > 65536:
                raise RuntimeError('Marker observation size bound')
            wire = data.raw[:count.value]
            return {'retainedBeforeReads': first, 'freshPath': path_information,
                    'retainedAfterReads': self.info(retained), 'sddl': security,
                    'sha256': hashlib.sha256(wire).hexdigest(), 'bytes': len(wire)}
        finally:
            self.close(fresh)

    def inventory(self, root):
        result = {}
        for path in sorted(Path(root).iterdir()):
            if not path.is_file():
                raise RuntimeError('Unexpected transaction directory')
            handle = self.open(path)
            try:
                result[path.name] = self.observe(path, handle)
            finally:
                self.close(handle)
        return result

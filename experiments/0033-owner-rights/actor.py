"""Same-user Win32 actors on explicit owned marker paths; no privilege changes."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys


class Actor:
    def __init__(self):
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.a=ctypes.WinDLL('advapi32',use_last_error=True)
        specs=[(self.k,'CreateFileW',[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE),
               (self.k,'CloseHandle',[w.HANDLE],w.BOOL),
               (self.k,'SetFileTime',[w.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(w.FILETIME)],w.BOOL),
               (self.k,'SetFileAttributesW',[w.LPCWSTR,w.DWORD],w.BOOL),
               (self.k,'WriteFile',[w.HANDLE,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p],w.BOOL),
               (self.k,'ReadFile',[w.HANDLE,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p],w.BOOL),
               (self.a,'ConvertStringSecurityDescriptorToSecurityDescriptorW',[w.LPCWSTR,w.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p],w.BOOL),
               (self.a,'GetSecurityDescriptorDacl',[ctypes.c_void_p,ctypes.POINTER(w.BOOL),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(w.BOOL)],w.BOOL),
               (self.a,'SetSecurityInfo',[w.HANDLE,ctypes.c_int,w.DWORD,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p],w.DWORD),
               (self.k,'LocalFree',[ctypes.c_void_p],ctypes.c_void_p)]
        for dll,name,args,result in specs:
            fn=getattr(dll,name);fn.argtypes=args;fn.restype=result

    def open(self,path,access,create=3):
        handle=self.k.CreateFileW(str(path),access,7,None,create,0x200000,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def mtime(self,handle):
        stamp=133444736000000000
        value=w.FILETIME(stamp&0xffffffff,stamp>>32)
        if not self.k.SetFileTime(handle,None,None,ctypes.byref(value)):raise ctypes.WinError(ctypes.get_last_error())

    def dacl(self,handle):
        # Reapply a protected owner-rights read-only descriptor, not broad grants.
        descriptor=ctypes.c_void_p()
        if not self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;;RC;;;OW)',1,ctypes.byref(descriptor),None):raise ctypes.WinError(ctypes.get_last_error())
        try:
            present=w.BOOL();defaulted=w.BOOL();acl=ctypes.c_void_p()
            if not self.a.GetSecurityDescriptorDacl(descriptor,ctypes.byref(present),ctypes.byref(acl),ctypes.byref(defaulted)):raise ctypes.WinError(ctypes.get_last_error())
            assert present.value and acl.value
            code=self.a.SetSecurityInfo(handle,1,0x80000004,None,None,acl,None)
            if code:raise ctypes.WinError(code)
        finally:self.k.LocalFree(descriptor)

    def bytes(self,handle,write=False):
        data=ctypes.create_string_buffer(b'foreign-marker' if write else 65536)
        count=w.DWORD()
        fn=self.k.WriteFile if write else self.k.ReadFile
        size=14 if write else 65536
        if not fn(handle,data,size,ctypes.byref(count),None):raise ctypes.WinError(ctypes.get_last_error())
        if not write:assert count.value==65536 and data.raw[:65536]==b'3'*65536

    def act(self,name,path,handle=None):
        owned=handle is None
        try:
            if name=='link':os.link(path,path.with_name('alias.marker'));return
            if name=='delete':os.unlink(path);return
            if name=='rename':os.rename(path,path.with_name('moved.marker'));return
            if name=='readonly':
                if not self.k.SetFileAttributesW(str(path),1):raise ctypes.WinError(ctypes.get_last_error())
                return
            access={'mtime':0x100,'dacl':0x60000,'owner-access':0x80000,'read':1,'write':2,'ads':2}[name]
            if owned:handle=self.open(str(path)+':probe' if name=='ads' else path,access,1 if name=='ads' else 3)
            if name=='mtime':self.mtime(handle)
            elif name=='dacl':self.dacl(handle)
            elif name in ['write','ads']:self.bytes(handle,True)
            elif name=='read':self.bytes(handle)
        finally:
            if owned and handle is not None:self.k.CloseHandle(handle)


if __name__=='__main__':
    name,path=sys.argv[1:3];path=Path(path)
    if os.name!='nt' or not path.is_absolute() or path.suffix!='.marker':raise RuntimeError('Owned Windows marker path required')
    actor=Actor();handle=None
    try:
        if name.startswith('preopen-'):
            name=name[8:];handle=actor.open(path,{'mtime':0x100,'dacl':0x60000}[name])
            print(json.dumps({'preopened':True}),flush=True)
            assert sys.stdin.readline().strip()=='continue'
        try:
            actor.act(name,path,handle);result={'allowed':True,'winError':None}
        except OSError as error:result={'allowed':False,'winError':error.winerror}
        print(json.dumps(result),flush=True)
    finally:
        if handle is not None:actor.k.CloseHandle(handle)

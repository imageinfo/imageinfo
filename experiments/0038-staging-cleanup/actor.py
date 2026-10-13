"""Ordinary readers/actors on the probe's newly owned marker roots."""
from importlib.util import spec_from_file_location,module_from_spec
import ctypes
import json
import os
from pathlib import Path
import sys

spec=spec_from_file_location('owner_actor',Path(__file__).resolve().parents[1]/'0033-owner-rights'/'actor.py')
module=module_from_spec(spec);spec.loader.exec_module(module)
if __name__=='__main__':
    mode,spelling=sys.argv[1:3];path=Path(spelling)
    if os.name!='nt' or not path.is_absolute() or path.suffix!='.marker':raise RuntimeError('Owned marker operand required')
    actor=module.Actor();handle=None
    try:
        if mode in ['reader','reader-no-delete-share']:
            share=7 if mode=='reader' else 1
            handle=actor.k.CreateFileW(str(path),1,share,None,3,0x200000,None)
            if handle==ctypes.c_void_p(-1).value:
                print(json.dumps({'opened':False,'winError':ctypes.get_last_error()}),flush=True);handle=None
            else:
                print(json.dumps({'opened':True}),flush=True)
                assert sys.stdin.readline().strip()=='release'
        elif mode=='root-dacl':
            handle=actor.k.CreateFileW(str(path),0x60000,7,None,3,0x02200000,None)
            if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            actor.dacl(handle);print(json.dumps({'changedOwnedRootDacl':True}),flush=True)
        else:
            try:actor.act(mode,path);result={'allowed':True,'winError':None}
            except OSError as error:result={'allowed':False,'winError':error.winerror}
            print(json.dumps(result),flush=True)
    finally:
        if handle is not None:actor.k.CloseHandle(handle)

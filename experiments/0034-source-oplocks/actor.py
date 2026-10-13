"""Reuse reviewed same-user actors; add explicit late-hard-link alias operations."""
from importlib.util import spec_from_file_location, module_from_spec
import json
import os
from pathlib import Path
import sys

spec = spec_from_file_location('owner_actor', Path(__file__).resolve().parents[1]/'0033-owner-rights'/'actor.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == '__main__':
    name, spelling = sys.argv[1:3]
    path = Path(spelling)
    if os.name != 'nt' or not path.is_absolute() or path.suffix != '.marker':
        raise RuntimeError('Explicit owned Windows marker path required')
    actor = module.Actor()
    handle = None
    try:
        if name.startswith('preopen-'):
            name = name[8:]
            handle = actor.open(path, {'mtime': 0x100, 'dacl': 0x60000}[name])
            print(json.dumps({'preopened': True}), flush=True)
            assert sys.stdin.readline().strip() == 'continue'
        try:
            if name.startswith('link-'):
                actor.act('link', path)
                path = path.with_name('alias.marker')
                name = name[5:]
            actor.act(name, path, handle)
            result = {'allowed': True, 'winError': None}
        except OSError as error:
            result = {'allowed': False, 'winError': error.winerror}
        print(json.dumps(result), flush=True)
    finally:
        if handle is not None:
            actor.k.CloseHandle(handle)

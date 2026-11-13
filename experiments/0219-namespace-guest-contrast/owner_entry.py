"""Verify captured runner source before loading the maintained owner CLI."""
import hashlib
from pathlib import Path
import sys


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv) < 4:
        raise SystemExit('use isolated Python -I -S with the absolute runner path and reviewed source digest')
    path = Path(sys.argv[1])
    if not path.is_absolute() or path != path.resolve(strict=True) or path.is_symlink():
        raise SystemExit('canonical runner path required')
    with path.open('rb') as stream:
        raw = stream.read(4194305)
    sha = hashlib.sha256(raw).hexdigest()
    if len(raw) > 4194304 or sha != sys.argv[2]:
        raise SystemExit('reviewed runner source pin differs')
    sys.argv = sys.argv[1:2] + sys.argv[3:]
    exec(compile(raw, str(path), 'exec', dont_inherit=True),
         {'__name__': '__main__', '__file__': str(path), '__captured_entry_sha256__': sha})


if __name__ == '__main__':
    main()

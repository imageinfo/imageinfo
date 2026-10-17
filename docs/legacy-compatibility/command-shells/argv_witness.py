"""Authored shell qualification witness; never executes imageinfo."""
import hashlib
import json
from pathlib import Path
import sys

data = sys.stdin.buffer.read()
Path(sys.argv[1]).write_text(json.dumps({
    'argv': sys.argv[2:], 'stdinHex': data.hex(),
    'stdinSha256': hashlib.sha256(data).hexdigest(),
}, ensure_ascii=True) + '\n', encoding='utf-8', newline='\n')

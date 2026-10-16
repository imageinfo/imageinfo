"""Existing standard-user guest sign-in/agent bootstrap through scoped QMP.

Never prints the retained fixture account password. No guest installation,
license changes, registry changes, privilege changes or host desktop input.
"""
import argparse
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '0022-ordinary-output'))
from windows_guest import Qmp


def run(root, base, login, bootstrap=False):
    pid = int((root / 'qemu.pid').read_text())
    args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    if (f'file={root}/windows.qcow2,if=ide,format=qcow2,cache=writeback'.encode() not in args
            or f'unix:{root}/qmp,server=on,wait=off'.encode() not in args):
        raise RuntimeError('Unverified private overlay console')
    q = Qmp(root)
    def key(*codes):
        q.call('send-key', {'keys': [{'type': 'qcode', 'data': c} for c in codes], 'hold-time': 75})
        time.sleep(.20)
    plain = {' ': 'spc', ':': 'semicolon', '/': 'slash', '\\': 'backslash',
             '-': 'minus', '.': 'dot', "'": 'apostrophe', '=': 'equal'}
    shifted = {'_': 'minus', ':': 'semicolon', '"': 'apostrophe',
               '(': '9', ')': '0', '+': 'equal'}
    def text(value):
        for char in value:
            if char.isupper():
                key('shift', char.lower())
            elif char in shifted:
                key('shift', shifted[char])
            else:
                key(plain.get(char, char))
    try:
        if login:
            document = ET.parse(base / 'config/Autounattend.xml')
            namespace = {'u': 'urn:schemas-microsoft-com:unattend'}
            password = document.find('.//u:AutoLogon/u:Password/u:Value', namespace).text
            key('ret')
            time.sleep(2)
            key('ctrl', 'a')
            text(password)
            key('ret')
            time.sleep(8)
        if not bootstrap:
            return
        key('meta_l', 'r')
        time.sleep(1)
        key('ctrl', 'a')
        text('powershell.exe')
        key('ret')
        time.sleep(8)
        text('iex(iwr http://10.0.2.2:18722/bootstrap -usebasicparsing).content')
        key('ret')
    finally:
        q.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--base', required=True, type=Path)
    p.add_argument('--login', action='store_true')
    p.add_argument('--bootstrap', action='store_true')
    a = p.parse_args()
    run(a.root.resolve(), a.base.resolve(), a.login, a.bootstrap)

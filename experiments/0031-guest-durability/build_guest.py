"""Assemble owned regular-file QEMU inputs; never mount or format a host device."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def build(kernel, template, probe, parent):
    if os.name != 'posix':
        raise RuntimeError('Build only in Linux; guest-only crash controls stay in initramfs')
    kernel, template, probe = [Path(p).resolve() for p in [kernel, template, probe]]
    if not kernel.is_file() or not probe.is_file() or not (template/'usr/bin/busybox').is_file():
        raise RuntimeError('Explicit extracted kernel/initramfs tree and static probe required')
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix='imageinfo-qemu-guest-', dir=parent))
    root = target/'root'
    shutil.copytree(template, root, symlinks=True)
    shutil.copyfile(kernel, target/'kernel')
    shutil.copyfile(probe, root/'probe')
    (root/'probe').chmod(0o755)
    shutil.copyfile(Path(__file__).parent/'guest-init.sh', root/'init-imageinfo')
    (root/'init-imageinfo').chmod(0o755)
    # Feed literal names to cpio, with no shell interpolation or host mounts.
    names = ['.']
    for folder, directories, files in os.walk(root, followlinks=False):
        names += [str((Path(folder)/name).relative_to(root)) for name in directories + files]
    packed = subprocess.run(['cpio','--null','-o','--format=newc'],
                            input=('\0'.join(sorted(names))+'\0').encode(),
                            cwd=root, capture_output=True, check=True).stdout
    with (target/'initramfs.cpio.gz').open('wb') as output:
        output.write(gzip.compress(packed, mtime=0))
    disk = target/'blank.raw'
    with disk.open('xb') as output:
        output.truncate(64*1024*1024)
    if not disk.is_file() or disk.is_symlink() or not disk.resolve().is_relative_to(target):
        raise RuntimeError('Only the newly owned regular image may be formatted')
    subprocess.run(['mkfs.ext4','-q','-F','-m','0',str(disk)], check=True)
    manifest = {'files': {name: hashlib.sha256((target/name).read_bytes()).hexdigest()
                         for name in ['kernel','initramfs.cpio.gz','blank.raw']},
                'probeSha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
                'hostDevicesFormatted': 0, 'hostMounts': 0}
    (target/'build.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['kernel','template','probe','parent']:
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    build(args.kernel, args.template, args.probe, args.parent)

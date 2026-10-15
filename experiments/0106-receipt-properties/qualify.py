"""Nine bounded marker cells; frozen actor, separate read-only native observer.

Run in WSL as the ordinary guest owner. Only the exact private overlay QEMU is
turned off; the host and retained base are never interrupted or modified.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / '0022-ordinary-output'
sys.path.insert(0, str(TOOLS))
import windows_guest as guest
from guest_qualify import (hello, job, queue, state, verify_guest_token,
                          wait_event, rebooted)

ACTOR = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
FLAGS = ('committed', 'namespaceAcknowledged', 'productionPublicationAllowed', 'repairAllowed')
MATRIX = [('normal', None, None, 'native-first')] + [
    (f'{kind}-{phase}-{order}', kind, phase, order)
    for phase in ('receipt-written', 'receipt-file-flushed')
    for kind in ('process-kill', 'vm-off')
    for order in ('native-first', 'rich-first')]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def agent_source(observer_hash):
    """Keep actor bytes unchanged; helper selection is outside actor code."""
    source = guest.AGENT
    source = source.replace("'ordinary-inventory'))", "'ordinary-inventory','ordinary-receipt-properties'))")
    source = source.replace("$child.StartInfo.FileName='C:\\ImageInfoGuest\\probe.exe'",
        "$child.StartInfo.FileName=if($mode -eq 'ordinary-receipt-properties'){'C:\\ImageInfoGuest\\observer.exe'}else{'C:\\ImageInfoGuest\\probe.exe'}")
    helper = r'''
function Native-Properties($root) {
    $child=Start-Probe $root 'ordinary-receipt-properties'
    try {
        $child.StandardInput.Close()
        $text=$child.StandardOutput.ReadToEnd();$errorText=$child.StandardError.ReadToEnd()
        $child.WaitForExit()
        return @{stdout=@($text.TrimEnd().Split("`n") | ForEach-Object {$_.TrimEnd("`r")});stderr=$errorText;exitCode=$child.ExitCode;observerSha256=(Get-FileHash -LiteralPath 'C:\ImageInfoGuest\observer.exe' -Algorithm SHA256).Hash.ToLowerInvariant();guestUtc=[DateTime]::UtcNow.ToString('o');wrapperInventoryPerformed=$false}
    } finally {if(-not $child.HasExited){$child.Kill();$child.WaitForExit()};$child.Dispose()}
}
'''
    source = source.replace('function Get-Inventory($root)', helper + '\nfunction Get-Inventory($root)')
    download = r'''
        Invoke-WebRequest ($base+'/observer.exe') -OutFile C:\ImageInfoGuest\observer.new.exe -UseBasicParsing
        if((Get-FileHash C:\ImageInfoGuest\observer.new.exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'OBSERVER_HASH') {throw 'Observer payload mismatch'}
        Move-Item C:\ImageInfoGuest\observer.new.exe C:\ImageInfoGuest\observer.exe -Force
        Send '/event' @{id='startup';event=@{observerReady=$true;observerSha256='OBSERVER_HASH';actorSha256=$meta.sha256}}
'''.replace('OBSERVER_HASH', observer_hash)
    source = source.replace('        while($true) {\n            $work=', download + '\n        while($true) {\n            $work=')
    source = source.replace("            if($work.mode -eq 'ordinary-inventory') {",
        "            if($work.mode -eq 'ordinary-receipt-properties') {$native=Native-Properties $root;$native.id=$work.id;Send '/result' $native;continue}\n            if($work.mode -eq 'ordinary-inventory') {")
    source = source.replace("                    if($event.barrier -eq $work.stopAt) {",
        "                    if($event.barrier -eq $work.stopAt) {\n                        Send '/event' @{id=$work.id;event=@{preProperties=(Native-Properties $root);supervisorObservation=$true}}")
    # The frozen inspector is still actor code; omit wrapper hashes so their
    # ordering cannot conceal an extra content observer before native-first.
    source = source.replace('$files=@(Get-Inventory $root)', '$files=@()')
    source = source.replace('rootInfo=(Get-RootInfo $root);processTermination=', 'wrapperInventoryPerformed=$false;processTermination=')
    if source == guest.AGENT or 'preProperties=' not in source:
        raise RuntimeError('Agent transformation failed')
    if (source.count("'ordinary-receipt-properties'))") != 1
            or source.count('preProperties=') != 1
            or source.count('wrapperInventoryPerformed=$false') != 2
            or '$files=@(Get-Inventory $root)' in source
            or source.count('observerReady=$true') != 1):
        raise RuntimeError('Exact agent template transformation counts changed')
    return source


def source_binding(actor, observer, frozen, native_baseline, actor_binding, actor_frozen):
    paths = list((frozen / 'experiments/0032-windows-publication/src').glob('*.rs'))
    paths += list((frozen / 'experiments/0028-recovery-evidence/src').glob('*.rs'))
    paths += [frozen / p for p in ('rust-toolchain.toml',
        'experiments/0032-windows-publication/Cargo.toml',
        'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0028-recovery-evidence/Cargo.toml',
        'experiments/0028-recovery-evidence/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs',
        'experiments/0038-staging-cleanup/src/disposition.rs')]
    if len(paths) < 20 or any(not p.is_file() or b'\r' in p.read_bytes() for p in paths):
        raise RuntimeError('Complete canonical-LF observer source freeze required')
    baseline = json.loads(native_baseline.read_text())
    actor_source = json.loads(actor_binding.read_text())
    if (baseline.get('caseCount') != 93 or actor_source.get('workerSha256') != ACTOR
            or len(actor_source.get('sources', {})) < 20):
        raise RuntimeError('Exact accepted 93-cell F869 native baseline required')
    for relative, expected in actor_source['sources'].items():
        if digest(actor_frozen / relative.replace('\\', '/')) != expected:
            raise RuntimeError('Frozen actor baseline source mismatch')
    if digest(actor) != ACTOR or digest(observer) == ACTOR:
        raise RuntimeError('Wrong frozen actor or non-separate observer')
    return {'actorSha256': ACTOR, 'observerSha256': digest(observer),
        'observerSources': {p.relative_to(frozen).as_posix(): digest(p) for p in sorted(paths)},
        'nativeBaselineSha256': digest(native_baseline), 'nativeBaseline': baseline,
        'actorSourceBindingSha256': digest(actor_binding), 'actorSourceBinding': actor_source,
        'controllerSources': {str(p.relative_to(HERE.parent)): digest(p)
            for p in sorted(list(HERE.glob('*.py')) + [TOOLS / 'windows_guest.py', TOOLS / 'guest_qualify.py'])},
        'guestAgentSha256': hashlib.sha256(agent_source(digest(observer)).encode()).hexdigest()}


def prepare(base, root):
    base, root = base.resolve(), root.resolve()
    if root.exists() or root == base or os.getuid() == 0:
        raise RuntimeError('New ordinary-owner private overlay root required')
    for name in ('qemu.pid', 'tpm.pid'):
        pidfile = base / name
        if pidfile.exists() and Path('/proc/' + pidfile.read_text().strip()).exists():
            raise RuntimeError('Retained base must be normally stopped before copying state')
    manifest = json.loads((base / 'guest.private.json').read_text())
    if not manifest.get('installed') or manifest['uid'] != os.getuid():
        raise RuntimeError('Verified installed ordinary-owner guest required')
    root.mkdir(mode=0o700)
    base_binding = {'root': str(base), 'diskSha256': digest(base / 'windows.qcow2'),
                    'varsSha256': digest(base / 'vars.fd'), 'manifestSha256': digest(base / 'guest.private.json')}
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b',
                    str(base / 'windows.qcow2'), str(root / 'windows.qcow2')], check=True, capture_output=True)
    shutil.copy2(base / 'vars.fd', root / 'vars.fd')
    shutil.copytree(base / 'tpm', root / 'tpm')
    manifest['root'] = str(root)
    write(root / 'guest.private.json', manifest)
    write(root / 'overlay-binding.private.json', base_binding)
    return root


def serve(root, actor, observer):
    # Reuse the bounded queue transport; add exactly one immutable payload route.
    import http.server
    old = http.server.ThreadingHTTPServer
    def factory(address, handler):
        original = handler.do_GET
        def get(self):
            if self.path == '/observer.exe':
                return self.send(observer.read_bytes(), 'application/octet-stream')
            if self.path == '/bootstrap':
                # Runs only in the disposable guest's ordinary interactive token.
                script = r'''$ErrorActionPreference='Stop'
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object {$_.ProcessId -ne $PID -and $_.CommandLine -match '(?i)-file\s+c:\\imageinfoguest\\agent\.ps1\s*$'} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force}
Start-Sleep -Seconds 1
Invoke-WebRequest 'http://10.0.2.2:18722/agent.ps1' -OutFile 'C:\ImageInfoGuest\agent.ps1' -UseBasicParsing
& powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File 'C:\ImageInfoGuest\agent.ps1'
'''
                return self.send(script.encode(), 'text/plain; charset=utf-8')
            return original(self)
        handler.do_GET = get
        return old(address, handler)
    http.server.ThreadingHTTPServer = factory
    guest.AGENT = agent_source(digest(observer))
    guest.serve(root, actor)


def invoke(case, suffix, mode, **extra):
    request = {'id': case + '-' + suffix, 'action': 'run', 'case': case, 'mode': mode, **extra}
    queue(request)
    return wait_event(lambda e: e['path'] == '/result' and e['value'].get('id') == request['id'])['value']


def events(identifier):
    return [e for e in state() if e['value'].get('id') == identifier]


def vm_off(root, folder):
    pid = int((root / 'qemu.pid').read_text())
    args = [a.decode() for a in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if a]
    disk = str(root / 'windows.qcow2')
    if (not args or Path(args[0]).name != 'qemu-system-x86_64'
            or not any(a.split(',')[0] == 'file=' + disk for a in args)
            or f'unix:{root / "qmp"},server=on,wait=off' not in args):
        raise RuntimeError('Unverified scoped overlay emulator')
    q = guest.Qmp(root)
    write(folder / 'vm-off-target.private.json', {'pid': pid, 'argv': args, 'root': str(root),
        'qmpStatusBefore': q.call('query-status'), 'command': 'quit'})
    q.call('quit')
    q.close()
    deadline = time.monotonic() + 20
    while Path(f'/proc/{pid}').exists() and time.monotonic() < deadline:
        time.sleep(.2)
    if Path(f'/proc/{pid}').exists():
        raise RuntimeError('Exact overlay emulator exit unconfirmed')
    write(folder / 'vm-off-completed.private.json', {'processExitConfirmed': True})


def restart_overlay(root, folder, base):
    launcher = TOOLS / 'windows_guest.py'
    result = subprocess.run(['/mnt/c/Windows/System32/wsl.exe', '-u', 'root', '-e',
        'python3', str(launcher), 'launch', '--root', str(root)], capture_output=True, timeout=40)
    write(folder / 'relaunch.private.json', {'exitCode': result.returncode,
        'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace')})
    if result.returncode:
        raise RuntimeError('Overlay relaunch failed')
    time.sleep(35)
    import console
    console.run(root, base, True)


def run(root, actor, observer, frozen, baseline, output, actor_binding, actor_frozen):
    binding = source_binding(actor, observer, frozen, baseline, actor_binding, actor_frozen)
    output.mkdir(exist_ok=False)
    write(output / 'source-binding.private.json', binding)
    (output / 'actor-source-binding.private.json').write_bytes(actor_binding.read_bytes())
    for relative, expected in binding['controllerSources'].items():
        target = output / 'controller-sources.private' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((HERE.parent / relative).read_bytes())
        if digest(target) != expected:
            raise RuntimeError('Controller freeze changed before collection')
    (output / 'served-agent.private.ps1').write_bytes(agent_source(binding['observerSha256']).encode())
    write(output / 'overlay-binding.private.json', json.loads((root / 'overlay-binding.private.json').read_text()))
    write(output / 'initial-launch.private.json', json.loads((root / 'launch.private.json').read_text()))
    rows = []
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    write(output / 'host-before.private.json', {'boot': host_boot})
    try:
        for index, (name, kind, phase, order) in enumerate(MATRIX):
            folder = output / name
            folder.mkdir()
            before = hello()
            verify_guest_token(before['value'])
            if before['value']['build'] != '26300' or before['value']['scriptSha256'] != binding['guestAgentSha256']:
                raise RuntimeError('Exact installed guest/agent binding mismatch')
            case = f'c106-{index}-{int(time.time())}'
            prepared = invoke(case, 'prepare', 'ordinary-prepare')
            request = {'id': case + '-live', 'action': 'run', 'case': case, 'mode': 'ordinary-receipt'}
            if phase:
                request['stopAt'] = phase
            if kind == 'process-kill':
                request['control'] = 'terminate'
            queue(request)
            checkpoint = None
            live_result = None
            if phase:
                checkpoint = wait_event(lambda e: e['path'] == '/event' and e['value'].get('id') == request['id']
                    and e['value']['event'].get('supervisorControl', {}).get('control') == 'held'
                    and e['value']['event']['supervisorControl']['barrier'] == phase)
                pre = next(e['value']['event']['preProperties'] for e in events(request['id'])
                           if 'preProperties' in e['value'].get('event', {}))
            else:
                live_result = wait_event(lambda e: e['path'] == '/result' and e['value'].get('id') == request['id'])['value']
                pre = invoke(case, 'native-control', 'ordinary-receipt-properties')
            context = next((e['value']['event']['receiptContext'] for e in reversed(events(request['id']))
                            if 'receiptContext' in e['value'].get('event', {})), None)
            write(folder / 'before.private.json', {'case': case, 'hello': before, 'prepare': prepared,
                  'request': request, 'checkpoint': checkpoint, 'receiptContext': context, 'preProperties': pre})
            after = before
            if kind == 'vm-off':
                fault_time = time.time()
                vm_off(root, folder)
                restart_overlay(root, folder, Path(json.loads((root / 'overlay-binding.private.json').read_text())['root']))
                after = rebooted(before, fault_time)
                verify_guest_token(after['value'])
            elif kind:
                live_result = wait_event(lambda e: e['path'] == '/result' and e['value'].get('id') == request['id'])['value']
            if order == 'rich-first':
                inventory_before = invoke(case, 'rich-before', 'ordinary-inventory')
                post = invoke(case, 'native-post', 'ordinary-receipt-properties')
            else:
                post = invoke(case, 'native-post', 'ordinary-receipt-properties')
                inventory_before = invoke(case, 'rich-before', 'ordinary-inventory')
            pre_inspect = invoke(case, 'native-pre-inspect', 'ordinary-receipt-properties')
            inspect_request = {'receiptContext': context}
            inspection = invoke(case, 'inspect', 'ordinary-receipt-inspect', **inspect_request)
            post_inspect = invoke(case, 'native-post-inspect', 'ordinary-receipt-properties')
            inventory_after = invoke(case, 'rich-after', 'ordinary-inventory')
            final = invoke(case, 'native-final', 'ordinary-receipt-properties')
            write(folder / 'after.private.json', {'hello': after, 'liveResult': live_result, 'order': order,
                'postbootProperties': post, 'inventoryBefore': inventory_before,
                'preInspectProperties': pre_inspect, 'postInspectProperties': post_inspect,
                'inspectRequest': inspect_request, 'inspect': inspection,
                'inventoryAfter': inventory_after, 'finalProperties': final})
            write(folder / 'controller-events.private.json', [e for e in state() if e['value'].get('id', '').startswith(case)])
            rows.append({'id': name, 'faultKind': kind, 'barrier': phase, 'order': order, 'retained': True})
            write(output / 'progress.private.json', {'cases': rows})
            print(json.dumps({'cell': name, 'retained': True}), flush=True)
        final_binding = source_binding(actor, observer, frozen, baseline, actor_binding, actor_frozen)
        write(output / 'source-binding-after.private.json', final_binding)
        if final_binding != binding:
            raise RuntimeError('Source/binary/controller binding changed during run')
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot:
            raise RuntimeError('Host boot changed')
        write(output / 'host-after.private.json', {'boot': host_boot})
        base_binding = json.loads((root / 'overlay-binding.private.json').read_text())
        base = Path(base_binding['root'])
        base_after = {'root': str(base), 'diskSha256': digest(base / 'windows.qcow2'),
            'varsSha256': digest(base / 'vars.fd'), 'manifestSha256': digest(base / 'guest.private.json')}
        write(output / 'base-after.private.json', base_after)
        if base_after != base_binding:
            raise RuntimeError('Preserved base changed')
        write(output / 'summary.private.json', {'cases': rows, 'caseCount': len(rows), 'vmOffs': 4,
              'hostCachesAlive': True, 'enabledProfiles': 0, **dict.fromkeys(FLAGS, False)})
    except BaseException as error:
        write(output / 'incomplete.private.json', {'cases': rows, 'diagnostic': str(error)})
        raise


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Assertions required')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'serve', 'run', 'agent'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--base', type=Path)
    p.add_argument('--actor', type=Path)
    p.add_argument('--observer', type=Path)
    p.add_argument('--frozen', type=Path)
    p.add_argument('--baseline', type=Path)
    p.add_argument('--actor-binding', type=Path)
    p.add_argument('--actor-frozen', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.mode == 'prepare':
        prepare(a.base, a.root)
    elif a.mode == 'serve':
        serve(a.root, a.actor, a.observer)
    elif a.mode == 'agent':
        print(agent_source(digest(a.observer)), end='')
    else:
        run(a.root, a.actor, a.observer, a.frozen, a.baseline, a.output, a.actor_binding, a.actor_frozen)

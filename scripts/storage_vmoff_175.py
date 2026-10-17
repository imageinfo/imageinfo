"""Fixed #0175 disposable Windows guest campaign; run in the ordinary WSL user.

No research actor is used. QMP quit is VM-off with host caches alive. The caller
must freeze/review the actual Cargo library-test worker before invoking run.
Every request, refusal and partial capture is retained; cells are never retried.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LEGACY = REPO / 'experiments/0022-ordinary-output'
BASE = Path('/var/tmp/imageinfo-windows-eval-20261014')
PORT = 18735
URL = f'http://127.0.0.1:{PORT}'
MAX_BODY = 8 * 1024 * 1024
MATRIX = (
    ('normal', 'run', 'none', 'none'),
    ('kill-candidate-ready', 'run', 'process-kill', 'candidate-ready'),
    ('kill-intent-ready', 'run', 'process-kill', 'intent-ready'),
    ('kill-possible-publication', 'run', 'process-kill', 'possible-publication'),
    ('kill-installed-ack', 'run', 'process-kill', 'installed-ack'),
    ('kill-receipt-before-ack', 'run', 'process-kill', 'receipt-before-ack'),
    ('kill-final-success-response', 'run', 'process-kill', 'final-success-response'),
    ('vmoff-possible-publication', 'run', 'vm-off', 'possible-publication'),
    ('vmoff-receipt-before-ack', 'run', 'vm-off', 'receipt-before-ack'),
    ('vmoff-completed-predicate', 'run', 'vm-off', 'completed-predicate'),
    ('kill-restart-finalize', 'finalize', 'process-kill', 'finalize-receipt-created'),
    ('kill-partial-cleanup', 'cleanup', 'process-kill', 'cleanup-one-removed'),
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def emulator_digest(pid):
    path = Path(f'/proc/{int(pid)}/exe')
    try:
        return digest(path)
    except PermissionError:
        # QEMU's privilege drop makes proc exe nondumpable to its normal uid.
        # This fixed root helper reads only that already-verified process image.
        result = subprocess.run(['/mnt/c/Windows/System32/wsl.exe', '-u', 'root', '-e',
                                 'sha256sum', str(path)], capture_output=True, timeout=20)
        value = result.stdout.decode('ascii').split()[0] if result.returncode == 0 else ''
        if len(value) != 64 or any(char not in '0123456789abcdef' for char in value):
            raise RuntimeError('Exact emulator image hash unavailable')
        return value


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    """No overwrites: partial or failed attempts remain explicit evidence."""
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def ref(path, output):
    path = Path(path).resolve()
    return {'path': path.relative_to(output.resolve()).as_posix(), 'sha256': digest(path)}


def load_legacy(name, filename):
    sys.path.insert(0, str(LEGACY))
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scoped(root):
    root = Path(root).resolve()
    if root.parent != BASE or not root.name.startswith('production-0175-'):
        raise ValueError('Exact retained-base child production-0175-* overlay required')
    return root


def prepare(root):
    root = scoped(root)
    helper = load_legacy('storage175_prepare', REPO / 'experiments/0106-receipt-properties/qualify.py')
    return helper.prepare(BASE, root)


def process_binding(root):
    root = scoped(root)
    manifest = read(root / 'guest.private.json')
    if manifest['root'] != str(root) or manifest['uid'] != os.getuid() or not manifest.get('installed'):
        raise ValueError('Installed ordinary-owner fixture binding required')
    if root.stat().st_uid != os.getuid() or not (root / 'overlay-binding.private.json').is_file():
        raise ValueError('Owned disposable overlay required')
    binding = read(root / 'overlay-binding.private.json')
    if Path(binding['root']).resolve() != BASE:
        raise ValueError('Unexpected retained backing image')
    pid = int((root / 'qemu.pid').read_text(encoding='utf-8'))
    args = [p.decode('utf-8') for p in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if p]
    launch = read(root / 'launch.private.json')
    validate_emulator_args(root, manifest, args, launch['argv'])
    native = load_legacy('storage175_native', LEGACY / 'windows_guest.py')
    q = native.Qmp(root)
    try:
        blocks = q.call('query-block')
        validate_backing(blocks, root, Path(manifest['tools']) / 'usr/share/OVMF/OVMF_CODE_4M.ms.fd')
        return {'pid': pid, 'argv': args, 'root': str(root), 'overlay_binding': binding,
                'status': q.call('query-status'), 'blocks': blocks,
                'version': q.call('query-version'), 'host_boot_utc': host_boot(),
                'wsl_boot_id': wsl_boot(), 'emulator_sha256': emulator_digest(pid)}
    finally:
        q.close()


def validate_emulator_args(root, manifest, args, launched):
    tools = Path(manifest['tools'])
    drives = [args[i + 1] for i, value in enumerate(args[:-1]) if value == '-drive']
    expected = [f'if=pflash,format=raw,unit=0,readonly=on,file={tools}/usr/share/OVMF/OVMF_CODE_4M.ms.fd',
                f'if=pflash,format=raw,unit=1,file={root}/vars.fd',
                f'file={root}/windows.qcow2,if=ide,format=qcow2,cache=writeback']
    if (not args or Path(args[0]).name != 'qemu-system-x86_64' or args != launched or drives != expected
            or f'unix:{root}/qmp,server=on,wait=off' not in args):
        raise ValueError('Actual emulator argv differs from exact scoped three-drive launch')
    forbidden = ('-blockdev', '-hda', '-hdb', '-hdc', '-hdd', '-fda', '-fdb', '-cdrom', '-virtfs', '-fsdev', '-readconfig', '-chroot')
    if any(value in forbidden or 'hostfwd' in value or 'media=cdrom' in value or '/dev/' in value
           or 'virtiofs' in value or 'nvdimm' in value for value in args):
        raise ValueError('Unexpected disks, shared filesystem or host forwarding')


def validate_backing(blocks, root, firmware=None):
    disk = root / 'windows.qcow2'
    allowed = {str(disk), str(root / 'vars.fd')}
    if firmware is not None: allowed.add(str(firmware))
    if any(block.get('inserted', {}).get('file') not in allowed for block in blocks if 'inserted' in block):
        raise ValueError('Unexpected live inserted drive outside the frozen system/firmware set')
    selected = [block['inserted'] for block in blocks if block.get('inserted', {}).get('file') == str(disk)]
    if len(selected) != 1: raise ValueError('Exact live system overlay is missing/ambiguous')
    image = selected[0].get('image', {})
    backing = image.get('backing-image', {})
    if (image.get('filename') != str(disk) or image.get('format') != 'qcow2'
            or image.get('full-backing-filename') != str(BASE / 'windows.qcow2')
            or backing.get('filename') != str(BASE / 'windows.qcow2') or backing.get('format') != 'qcow2'
            or backing.get('backing-image') or backing.get('backing-filename')):
        raise ValueError('Live QMP backing chain differs from the single retained base')


def wsl_boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text(encoding='utf-8').strip()


def host_facts():
    executable = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    command = "$v=Get-CimInstance Win32_OperatingSystem; @{boot=$v.LastBootUpTime.ToUniversalTime().ToString('o');build=$v.BuildNumber;version=$v.Version}|ConvertTo-Json -Compress"
    result = subprocess.run([executable, '-NoProfile', '-Command', command], capture_output=True, timeout=20)
    if result.returncode: raise RuntimeError('Windows host boot identity unavailable')
    value = json.loads(result.stdout.decode('utf-8-sig').strip())
    if not value.get('boot') or not value.get('build'): raise RuntimeError('Windows host boot response incomplete')
    return value


def host_boot():
    return host_facts()['boot']


def off(root, folder, cell, profile_hash):
    target = process_binding(root)  # Recheck the live PID/argv immediately before quit.
    target.update(requested_cell_id=cell, profile_sha256=profile_hash, command='quit')
    save(folder / 'off-target.private.json', target)
    native = load_legacy('storage175_off', LEGACY / 'windows_guest.py')
    q = native.Qmp(root)
    response = None
    error = None
    try:
        try:
            response = q.call('quit')
        except Exception as failure:
            # QEMU quit need not return a response. Never resend; the verified
            # process-exit observation below decides whether VM-off occurred.
            error = type(failure).__name__ + ': ' + str(failure)
    finally:
        try: q.close()
        except Exception as failure:
            error = (error + '; ' if error else '') + 'close: ' + str(failure)
    save(folder / 'off-response.private.json', {'quit_response': response, 'quit_error': error,
         'quit_attempts': 1, 'requested_cell_id': cell})
    deadline = time.monotonic() + 20
    while Path(f'/proc/{target["pid"]}').exists() and time.monotonic() < deadline:
        time.sleep(.2)
    if Path(f'/proc/{target["pid"]}').exists():
        raise RuntimeError('Exact disposable VM process exit unconfirmed')
    save(folder / 'off-completed.private.json', {'vm_process_exit_confirmed': True,
         'requested_cell_id': cell, 'host_boot_utc': host_boot(), 'host_caches_alive': True,
         'quit_response': response, 'quit_error': error, 'quit_attempts': 1})


def launch(root, folder, profile_hash):
    # Existing launcher checks evaluation age and preserves installed backing state.
    result = subprocess.run(['/mnt/c/Windows/System32/wsl.exe', '-u', 'root', '-e',
        'python3', str(LEGACY / 'windows_guest.py'), 'launch', '--root', str(root)],
        capture_output=True, timeout=40)
    value = {'exit_code': result.returncode, 'stdout': result.stdout.decode('utf-8', errors='replace'),
             'stderr': result.stderr.decode('utf-8', errors='replace'), 'profile_sha256': profile_hash}
    if result.returncode == 0:
        value['live_binding'] = process_binding(root)
    save(folder / 'restart-launch.private.json', value)
    if result.returncode:
        raise RuntimeError('Disposable guest launch failed; retained launch receipt')


def console(root, login=False):
    """Scoped console uses existing retained credential without logging its value."""
    process_binding(root)
    native = load_legacy('storage175_keys', LEGACY / 'windows_guest.py')
    q = native.Qmp(root)
    def key(*codes):
        q.call('send-key', {'keys': [{'type': 'qcode', 'data': code} for code in codes], 'hold-time': 75})
        time.sleep(.15)
    command = 'iex(iwr http://10.0.2.2:18735/bootstrap -usebasicparsing).content'
    plain = {' ': 'spc', '/': 'slash', '\\': 'backslash', '-': 'minus', '.': 'dot', ';': 'semicolon'}
    shifted = {':': 'semicolon', '"': 'apostrophe', '&': '7', '_': 'minus',
               '(': '9', ')': '0', '+': 'equal', '@': '2', '?': 'slash'}
    def text(value):
        for char in value:
            if char.isupper(): key('shift', char.lower())
            elif char in shifted: key('shift', shifted[char])
            else: key(plain.get(char, char))
    try:
        if login:
            tree = ET.parse(BASE / 'config/Autounattend.xml')
            credential = tree.find('.//u:AutoLogon/u:Password/u:Value', {'u': 'urn:schemas-microsoft-com:unattend'}).text
            # The original two-second lock-screen transition dropped initial
            # keystrokes in inventory setup. This fixed wait is preregistered
            # before cells; there is no sign-in or measurement retry loop.
            key('ret'); time.sleep(8); key('ctrl', 'a'); text(credential); key('ret'); time.sleep(15)
        key('meta_l', 'r'); time.sleep(1); key('ctrl', 'a')
        text('powershell.exe -NoProfile -ExecutionPolicy Bypass'); key('ret'); time.sleep(8); text(command)
        key('ret')
    finally:
        q.close()


def http(route, value=None):
    data = None if value is None else json.dumps(value).encode('utf-8')
    request = urllib.request.Request(URL + route, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def wait(predicate, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for item in reversed(http('/state')):
            if predicate(item): return item
        time.sleep(.25)
    raise TimeoutError('Fixed guest evidence deadline exceeded; no retry')


def invoke(job):
    http('/queue', job)
    return wait(lambda item: item['route'] == '/result' and item['value'].get('id') == job['id'])['value']


def hello(binding):
    nonce = secrets.token_hex(16)
    value = invoke({'id': 'hello-' + nonce, 'action': 'hello', 'challenge': nonce})
    if value.get('failed') or value.get('hello', {}).get('challenge') != nonce:
        raise RuntimeError('Fresh guest readiness challenge failed')
    raw = value['hello']
    for key, expected in [('workerSha256', binding['workerSha256']), ('readerSha256', binding['readerSha256']),
                          ('scriptSha256', binding['guestScriptSha256'])]:
        if raw.get(key) != expected: raise RuntimeError('Guest tooling differs from frozen payload')
    groups = '\n'.join(raw['groups'])
    if 'S-1-5-32-544' in groups or 'S-1-16-8192' not in groups or raw['filesystem'] != 'NTFS' or raw['driveType'] != 3:
        raise RuntimeError('Guest token or local filesystem mismatch')
    return {'boot_utc': raw['boot'], 'os_version': raw['version'], 'os_build': raw['build'],
            'executable_sha256': raw['workerSha256'], 'reader_sha256': raw['readerSha256'],
            'host_boot_utc': host_boot(), 'raw': raw}


def same_profile(actual, expected, boot_change=False):
    keys = ('computer', 'user', 'groups', 'os', 'build', 'version', 'servicingRevision', 'architecture',
            'filesystem', 'volumeSerial', 'driveType', 'clusterBytes', 'volumeSizeBytes', 'volumeDeviceId',
            'controllers', 'controllerDrivers', 'disks', 'guestCachePolicy', 'workerSha256', 'readerSha256', 'scriptSha256')
    if any(actual['raw'].get(key) != expected['raw'].get(key) for key in keys):
        raise ValueError('Frozen guest OS/storage/token/tool profile changed')
    if actual['host_boot_utc'] != expected['host_boot_utc']:
        raise ValueError('Actual Windows host boot changed')
    if not boot_change and actual['boot_utc'] != expected['boot_utc']:
        raise ValueError('Unexpected guest reboot outside VM-off cell')


def serve(output, worker, root):
    output = output.resolve()
    scoped(root)
    output.mkdir(parents=True, exist_ok=True)
    payloads = {'/actor.exe': worker.read_bytes(), '/reader.ps1': (HERE / 'read_storage_artifacts_175.ps1').read_bytes(),
                '/agent.ps1': (HERE / 'storage_vmoff_guest_175.ps1').read_bytes()}
    payloads['/bootstrap'] = b"$ErrorActionPreference='Stop';$p='C:\\ImageInfoGuest\\agent175.ps1';iwr http://10.0.2.2:18735/agent.ps1 -UseBasicParsing -OutFile $p;& $p"
    binding = {'workerSha256': hashlib.sha256(payloads['/actor.exe']).hexdigest(),
               'readerSha256': hashlib.sha256(payloads['/reader.ps1']).hexdigest(),
               'guestScriptSha256': hashlib.sha256(payloads['/agent.ps1']).hexdigest(),
               'controllerSha256': digest(Path(__file__))}
    save(output / 'transport-binding.private.json', binding)
    jobs = queue.Queue(maxsize=1)
    controls = {}
    history = []
    history_bytes = 0
    lock = threading.Lock()
    journal = (output / 'transport-history.private.jsonl').open('x', encoding='utf-8', newline='\n')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def reply(self, value, content_type='application/json'):
            data = value if isinstance(value, bytes) else json.dumps(value).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            if self.path in payloads:
                return self.reply(payloads[self.path], 'text/plain; charset=utf-8' if self.path.endswith('.ps1') or self.path == '/bootstrap' else 'application/octet-stream')
            if self.path == '/meta': return self.reply(binding)
            if self.path == '/job':
                try: value = jobs.get_nowait()
                except queue.Empty: value = {}
                return self.reply(value)
            if self.path.startswith('/control?'):
                identifier = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id', [''])[0]
                with lock: value = controls.pop(identifier, {})
                return self.reply(value)
            if self.path == '/state':
                with lock: value = list(history)
                return self.reply(value)
            return self.send_error(404)
        def do_POST(self):
            nonlocal history_bytes
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY: raise ValueError('Body bound')
                value = json.loads(self.rfile.read(length))
                if self.path == '/queue': jobs.put_nowait(value)
                elif self.path == '/set-control':
                    if value.get('action') not in ('kill', 'continue'): raise ValueError('Control not allowed')
                    with lock: controls[value['id']] = value
                elif self.path not in ('/event', '/hello', '/result', '/stop'): raise ValueError('Route')
                entry = {'at': time.time(), 'route': self.path, 'value': value}
                wire = json.dumps(entry, sort_keys=True) + '\n'
                with lock:
                    if len(history) >= 1024 or history_bytes + len(wire) > 128 * 1024 * 1024: raise ValueError('Fixed history byte/event bound')
                    journal.write(wire); journal.flush(); os.fsync(journal.fileno())
                    history_bytes += len(wire)
                    history.append(entry)
                if self.path == '/stop': threading.Thread(target=server.shutdown, daemon=True).start()
                return self.reply({})
            except (ValueError, KeyError, queue.Full): return self.send_error(400)
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try: server.serve_forever()
    finally: journal.close(); server.server_close()


def retain_bytes(path, encoded):
    if not isinstance(encoded, str): raise RuntimeError('Missing retained byte capture')
    data = base64.b64decode(encoded, validate=True)
    if len(data) > MAX_BODY: raise RuntimeError('Decoded capture bound')
    with path.open('xb') as stream: stream.write(data)


def freeze(output, worker, source_manifest):
    spec = read(source_manifest)
    if spec.get('workerSha256') != digest(worker) or not spec.get('sources'):
        raise ValueError('Parent-reviewed exact source/executable freeze required')
    frozen = output / 'frozen'; frozen.mkdir()
    result = {}
    inputs = {'executable': worker, 'actor_source': REPO / 'src/storage/qualification.rs',
              'reader': HERE / 'read_storage_artifacts_175.ps1', 'controller': Path(__file__),
              'guest_controller': HERE / 'storage_vmoff_guest_175.ps1', 'source_manifest': source_manifest,
              'legacy_launcher': LEGACY / 'windows_guest.py',
              'legacy_console': REPO / 'experiments/0110-receipt-context/console.py'}
    for name in ('audit_storage_vmoff_175.py', 'test_audit_storage_vmoff_175.py',
                 'test_read_storage_artifacts_175.py', 'test_storage_vmoff_175.py',
                 'check_production_vmoff_trace.py', 'test_production_vmoff_trace.py'):
        inputs[name.replace('.', '_')] = HERE / name
    inputs['method_ledger'] = REPO / 'docs/write-safety/production-vmoff-cells.json'
    for label in ('native_baseline_evidence', 'freeze_review_evidence'):
        supplied = spec.get(label + '_path')
        expected = spec.get(label + '_sha256')
        if not supplied or not expected: raise ValueError('Required retained evidence path/hash: ' + label)
        supplied = Path(supplied)
        evidence = (supplied if supplied.is_absolute() else REPO / supplied).resolve()
        if not evidence.is_relative_to(REPO) or digest(evidence) != expected:
            raise ValueError('Retained baseline/review evidence mismatch: ' + label)
        inputs[label] = evidence
    for relative, expected in spec['sources'].items():
        path = (REPO / relative).resolve()
        if not path.is_relative_to(REPO) or digest(path) != expected: raise ValueError('Frozen source mismatch')
        inputs['source_' + relative.replace('/', '_')] = path
    for label, source in inputs.items():
        destination = frozen / (label + source.suffix)
        shutil.copyfile(source, destination)
        result[label] = ref(destination, output)
    return result


def run(root, output, worker, source_manifest):
    """Only invoke after the parent grants the frozen campaign slot."""
    root, output = scoped(root), output.resolve()
    if (output / 'manifest.private.json').exists(): raise ValueError('No repeated campaign')
    frozen = freeze(output, worker, source_manifest)
    binding = read(output / 'transport-binding.private.json')
    expected_binding = {'workerSha256': digest(worker), 'readerSha256': digest(HERE / 'read_storage_artifacts_175.ps1'),
                        'guestScriptSha256': digest(HERE / 'storage_vmoff_guest_175.ps1'), 'controllerSha256': digest(Path(__file__))}
    if binding != expected_binding: raise ValueError('Served frozen tooling mismatch')
    initial = hello(binding)
    if (not initial['raw']['guestCachePolicy'].get('querySucceeded')
            or initial['raw']['guestCachePolicy'].get('enabled') not in (1, 2)
            or initial['raw']['guestCachePolicy'].get('type') not in (1, 2, 3)
            or initial['raw']['guestCachePolicy'].get('writeThrough') not in (1, 2)
            or not initial['raw']['clusterBytes'] or not initial['raw']['volumeSizeBytes']
            or not initial['raw']['controllers'] or not initial['raw']['controllerDrivers']):
        save(output / 'unsupported-profile.private.json', {'hello': initial, 'reason': 'Required guest storage/cache facts unavailable; no actor cell executed'})
        raise ValueError('Unsupported guest profile; no campaign effects')
    emulator = process_binding(root)
    profile = {'schema': 'imageinfo-0175-profile-v1', 'guest': initial, 'emulator': emulator,
               'launch': read(root / 'launch.private.json'), 'guest_manifest': read(root / 'guest.private.json'),
               'backing': read(root / 'overlay-binding.private.json'), 'host_caches_alive': True,
               'physical_power_tested': False, 'filesystem': 'NTFS', 'cache': 'writeback',
               'host_caches_survive_vmoff': True,
               'controller_cache': 'QEMU IDE cache=writeback; host caches survive VM-off'}
    raw = initial['raw']
    declared = read(source_manifest)
    profile.update({
        'guest_os_edition': raw['os'], 'guest_os_version': raw['version'], 'guest_os_build': raw['build'],
        'guest_os_servicing_revision': raw['servicingRevision'],
        'guest_architecture': raw['architecture'], 'guest_account_kind': 'ordinary medium integrity nonadministrator',
        'guest_boot_identity_before': raw['boot'], 'guest_volume_identity': {'serial': raw['volumeSerial'], 'device': raw['volumeDeviceId']},
        'guest_filesystem': raw['filesystem'], 'guest_volume_cluster_bytes': raw['clusterBytes'],
        'guest_volume_size_bytes': raw['volumeSizeBytes'], 'guest_volume_kind': 'local fixed NTFS system volume',
        'hypervisor_version': emulator['version'], 'hypervisor_executable_sha256': emulator['emulator_sha256'],
        'hypervisor_arguments': emulator['argv'], 'controller_model': raw['controllers'], 'controller_driver': raw['controllerDrivers'],
        'virtual_disk_format': 'qcow2', 'virtual_disk_backing_chain': emulator['overlay_binding'],
        'host_cache_mode': 'QEMU cache=writeback, host caches remain alive', 'guest_cache_policy': raw['guestCachePolicy'],
        'host_boot_identity': initial['host_boot_utc'], 'host_os_build': host_facts()['build'],
        'actor_source_sha256': frozen['actor_source']['sha256'], 'actor_executable_sha256': binding['workerSha256'],
        'actor_invocation': '--exact storage::qualification::guest_actor --ignored --nocapture --test-threads=1',
        'controller_sha256': binding['controllerSha256'], 'guest_script_sha256': binding['guestScriptSha256'],
        'auditor_sha256': digest(HERE / 'audit_storage_vmoff_175.py'),
        'method_ledger_sha256': digest(REPO / 'docs/write-safety/production-vmoff-cells.json'),
        'production_source_manifest_sha256': digest(source_manifest), 'cargo_lock_sha256': digest(REPO / 'Cargo.lock'),
        'rust_toolchain_file_sha256': digest(REPO / 'rust-toolchain.toml'),
        'adapter_crate_sha256': digest(REPO / 'crates/imageinfo-windows-storage/src/lib.rs'),
        'platform_facade_sha256': digest(REPO / 'src/storage/windows.rs'),
    })
    for name in ('actor_toolchain', 'actor_build_command', 'native_baseline_evidence_sha256', 'freeze_review_evidence_sha256'):
        if not declared.get(name): raise ValueError('Parent freeze metadata missing: ' + name)
        profile[name] = declared[name]
    save(output / 'profile.private.json', profile)
    profile_ref = ref(output / 'profile.private.json', output)
    manifest = {'schema': 'imageinfo-0175-audit-manifest-v1', 'implementation': read(source_manifest)['implementation'],
                'possible_publication_checkpoint': 'possible-publication', 'frozen': frozen, 'profile': profile_ref,
                'cells': []}
    previous = initial
    try:
        for cell, mode, fault, checkpoint in MATRIX:
            folder = output / cell; folder.mkdir()
            refs = {}
            row = {'id': cell, 'mode': mode, 'fault': fault, 'requested_checkpoint': checkpoint,
                   'status': 'not-run', 'references': refs}
            manifest['cells'].append(row)
            def record(label, name, value):
                save(folder / name, value); refs[label] = ref(folder / name, output)
            before = hello(binding)
            record('before_hello', 'before-hello.private.json', before)
            same_profile(before, previous)
            request = {'cell_id': cell, 'mode': mode, 'fault': fault, 'requested_checkpoint': checkpoint,
                       'executable_sha256': binding['workerSha256'], 'reader_sha256': binding['readerSha256']}
            record('request', 'request.private.json', request)
            job = {'id': cell + '-run', 'action': 'run', 'cell': cell, 'mode': mode, 'checkpoint': checkpoint}
            http('/queue', job)
            reached = wait(lambda item: item['value'].get('id') == job['id'] and item['route'] in ('/event', '/result'))
            gate = reached['route'] == '/event' and reached['value'].get('kind') == 'gate'
            if fault != 'none' and gate:
                raw = reached['value']; event = raw['actorEvent']
                encoded = base64.b64decode(raw['eventFileBase64'], validate=True)
                lines = [line + b'\n' for line in encoded.splitlines()]
                actual = next(line for line in lines if json.loads(line)['sequence'] == event['sequence'])
                record('gate', 'gate.private.json', {'observed_checkpoint': event['event'], 'actor_pid': raw['pid'],
                    'event_sequence': event['sequence'], 'event_sha256': hashlib.sha256(actual).hexdigest(),
                    'gate_armed': True, 'raw': raw})
                if event['event'] != checkpoint: raise RuntimeError('Gate did not match requested checkpoint')
                if fault == 'process-kill':
                    http('/set-control', {'id': job['id'], 'action': 'kill'})
                    result = wait(lambda item: item['route'] == '/result' and item['value'].get('id') == job['id'])['value']
                else:
                    off(root, folder, cell, profile_ref['sha256'])
                    refs['off_target'] = ref(folder / 'off-target.private.json', output)
                    refs['off_completed'] = ref(folder / 'off-completed.private.json', output)
                    result = {'pid': raw['pid'], 'eventFileBase64': raw['eventFileBase64'], 'vm_off': True}
                    launch(root, folder, profile_ref['sha256']); refs['restart_launch'] = ref(folder / 'restart-launch.private.json', output)
                    time.sleep(35); console(root, login=True)
                    wait(lambda item: item['route'] == '/hello' and item['at'] > reached['at'])
            else:
                result = reached['value']
            save(folder / 'raw-run-result.private.json', result)
            if result.get('eventFileBase64'):
                retain_bytes(folder / 'events.private.jsonl', result['eventFileBase64'])
                refs['events'] = ref(folder / 'events.private.jsonl', output)
            control = result.get('control') or {}
            confirmed = (fault == 'vm-off' and result.get('vm_off')) or bool(control.get('action') == 'kill' and control.get('processExitConfirmed'))
            record('run_result', 'run-result.private.json', {'actor_pid': result.get('pid'),
                'exit_confirmed': bool(confirmed or isinstance(result.get('exitCode'), int)), 'fault_confirmed': bool(confirmed),
                'observed_checkpoint': checkpoint if gate else None,
                'reason': result.get('diagnostic') or ('Requested fault gate not reached or actual actor failed' if not confirmed and fault != 'none' else
                         'Actual actor exited nonzero before declared outcome' if result.get('exitCode') not in (None, 0) else None), 'raw': result})
            row['status'] = 'actual' if (fault == 'none' and result.get('exitCode') == 0) or confirmed else 'refused'
            after = hello(binding); record('after_hello', 'after-hello.private.json', after)
            same_profile(after, before, boot_change=(fault == 'vm-off' and gate))
            if fault == 'vm-off' and gate and after['boot_utc'] == before['boot_utc']: raise RuntimeError('Guest restart boot unchanged')
            if after['host_boot_utc'] != before['host_boot_utc']: raise RuntimeError('Host kernel boot changed')
            previous = after
            for stage in ('before-inspect', 'after-inspect'):
                capture = invoke({'id': cell + '-' + stage, 'action': 'snapshot', 'cell': cell, 'stage': stage})
                save(folder / (stage + '-transport.private.json'), capture)
                retain_bytes(folder / ('snapshot-' + stage + '.private.json'), capture.get('snapshotBase64'))
                refs['snapshot_before' if stage == 'before-inspect' else 'snapshot_after'] = ref(folder / ('snapshot-' + stage + '.private.json'), output)
                if stage == 'before-inspect':
                    inspection = invoke({'id': cell + '-inspect', 'action': 'run', 'cell': cell, 'mode': 'inspect', 'checkpoint': 'none'})
                    retain_bytes(folder / 'inspect-events.private.jsonl', inspection.get('eventFileBase64'))
                    refs['inspect_events'] = ref(folder / 'inspect-events.private.jsonl', output)
                    record('inspect_result', 'inspect-result.private.json', {'exit_code': inspection.get('exitCode'),
                        'authority_imported': False, 'mutation_requested': False, 'raw': inspection})
            save(folder / 'cell.private.json', row)
            print(json.dumps({'cell': cell, 'retained': True, 'status': row['status']}), flush=True)
            if row['status'] == 'refused': raise RuntimeError('Unreached/refused cell retained; no adaptive continuation')
        for cell, mode, fault, checkpoint in MATRIX[len(manifest['cells']):]:
            manifest['cells'].append({'id': cell, 'mode': mode, 'fault': fault, 'requested_checkpoint': checkpoint, 'status': 'not-run', 'references': {}})
    except BaseException as error:
        save(output / 'incomplete.private.json', {'diagnostic': str(error), 'completed_cells': len(manifest['cells'])})
        raise
    finally:
        present = {row['id'] for row in manifest['cells']}
        for cell, mode, fault, checkpoint in MATRIX:
            if cell not in present:
                manifest['cells'].append({'id': cell, 'mode': mode, 'fault': fault, 'requested_checkpoint': checkpoint, 'status': 'not-run', 'references': {}})
        save(output / 'manifest.private.json', manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'serve', 'console', 'preflight', 'run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--source-manifest', type=Path)
    parser.add_argument('--login', action='store_true')
    args = parser.parse_args()
    root = scoped(args.root)
    if args.mode == 'prepare': prepare(root)
    elif args.mode == 'preflight': print(json.dumps(process_binding(root), sort_keys=True))
    elif args.mode == 'console': console(root, args.login)
    elif args.mode == 'serve': serve(args.output, args.worker, root)
    elif args.mode == 'run': run(root, args.output, args.worker, args.source_manifest)


if __name__ == '__main__': main()

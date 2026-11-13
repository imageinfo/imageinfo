"""Authored single-client socket and actual maintained console orchestration."""
from contextlib import ExitStack, contextmanager, redirect_stdout
from dataclasses import asdict
import http.client
import io
import json
import os
from pathlib import Path, PureWindowsPath
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import console_transport as transport
import host_runner as runner
import audit
from test_audit import source_snapshot
from test_console_result import capture_fixture
from test_host import FakeQmp, h, outer


def request_http(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


class SingleClient:
    """A real socket peer. A competing connection never gets a greeting."""

    def __init__(self, path, bindings, *, loss=None, mutate=None, on_request=None):
        self.family = getattr(socket, 'AF_UNIX', socket.AF_INET)
        self.listener = socket.socket(self.family)
        self.listener.bind(str(path) if self.family != socket.AF_INET else ('127.0.0.1', 0))
        self.address = self.listener.getsockname()
        self.listener.listen(2)
        self.listener.settimeout(5)
        self.disks = {bound.raw_node: FakeQmp(bound) for bound in bindings}
        self.loss, self.mutate, self.on_request = loss, mutate, on_request
        self.accepted = 0
        self.requests, self.keys = [], []
        self.failure = None
        self.closing = False
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    @contextmanager
    def physical_boundary(self):
        if self.family != socket.AF_INET:
            yield
            return
        original = socket.socket
        listener = self

        class AuthoredSocket(original):
            def connect(self, address):
                return super().connect(listener.address if isinstance(address, str) else address)

        def construct(*args, **kwargs):
            if args and args[0] == socket.AF_INET:
                return AuthoredSocket(*args, **kwargs)
            return original(*args, **kwargs)

        with patch.object(socket, 'AF_UNIX', socket.AF_INET, create=True), patch.object(socket, 'socket', construct):
            yield

    def close(self):
        self.closing = True
        self.listener.close()
        self.thread.join(6)
        if self.failure is not None:
            raise self.failure
        if self.thread.is_alive():
            raise AssertionError('authored QMP server did not exit')

    def serve(self):
        try:
            with self.listener.accept()[0] as channel, channel.makefile('rb') as stream:
                self.accepted += 1
                channel.settimeout(10)
                channel.sendall(b'{"QMP": {}}\n')
                for raw in stream:
                    request = json.loads(raw)
                    self.requests.append(request)
                    if self.on_request:
                        self.on_request(request)
                    answer = self.reply(request['execute'], request.get('arguments'))
                    if answer is None:
                        return
                    reply = {'return': answer, 'id': request['id']}
                    channel.sendall(b'{"event":"AUTHORED"}\n' + runner.encode(reply).replace(b'\n', b'') + b'\n')
        except (ConnectionResetError, BrokenPipeError):
            pass
        except OSError as exc:
            if not self.closing:
                self.failure = exc
        except BaseException as exc:
            self.failure = exc

    def reply(self, command, arguments):
        if command in ('query-named-block-nodes', 'query-block', 'query-blockstats'):
            reply = [row for disk in self.disks.values() for row in disk(command, arguments)]
        elif command == 'query-status':
            reply = {'running': True}
        elif command == 'qom-get':
            reply = next(disk.binding.device_serial for disk in self.disks.values()
                         if arguments['path'].endswith('/' + disk.binding.device_id))
        elif command == 'blockdev-add':
            reply = next(disk(command, arguments) for disk in self.disks.values()
                         if disk.binding.filter_node == arguments['node-name'])
        elif command == 'blockdev-reopen':
            reply = self.disks[arguments['options'][0]['node-name']](command, arguments)
        elif command == 'screendump':
            Path(arguments['filename']).write_bytes(b'P6\n1 1\n255\n\x01\x02\x03')
            reply = {}
        elif command == 'input-send-event':
            self.keys.append(arguments['events'])
            if self.loss and self.loss(self.keys):
                return None
            reply = {}
        else:
            assert command == 'qmp_capabilities', command
            reply = {}
        return reply if self.mutate is None else self.mutate(command, reply)


class RunnerControls(unittest.TestCase):
    def setUp(self):
        # Short path for AF_UNIX; all generated bytes are authored and retained
        # only for the life of this control unless evidence is requested.
        temporary = tempfile.TemporaryDirectory(prefix='i72-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'owner'
        self.source.mkdir()
        for filename in runner.OWNER_SOURCES:
            (self.source / filename).write_bytes(Path(runner.__file__).with_name(filename).read_bytes())
        with patch.object(time, 'sleep', lambda _: None):
            self.modules, pins = runner.load_owner_modules(self.source, None)
        self.run = self.modules['host_runner.py']
        self.transport = self.modules['console_transport.py']
        self.result = self.modules['console_result.py']
        self.config_path = self.root / 'config.json'
        self.attempt = self.root / 'pair' / 'first'
        self.pid = {'pid': os.getpid(), 'start_ticks': 789, 'argv': [str(self.source / 'host_runner.py')], 'uid': 1000}
        self.expected_owner = {'sources': pins, 'runtime': self.run.runtime_identity(),
                               'code_sha256': self.run.live_entries(self.modules)[1]}
        self.bindings = [h.Binding(f'authored{n}', case, f'raw{n}', f'file{n}', f'filter{n}',
                                  f'/authored/disk{n}.raw', f'disk{n}', f'serial{n}', 'A219', rf'D:\authored{n}')
                         for n, case in enumerate(runner.CASES)]
        self.checked, self.config, self.raw = self.input_fixture()
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        for name, function in (('process_identity', lambda: self.pid), ('qmp_platform', lambda: True)):
            self.patch_preserving_identity(name, function)
        self.output = io.StringIO()
        self.patches.enter_context(redirect_stdout(self.output))
        self.result_thread = None
        self.result_errors = []

    def patch_preserving_identity(self, name, function):
        # Process and platform fakes are test boundary functions, not authored
        # owner callables. Their object binding remains checked at every phase.
        self.patches.enter_context(patch.object(self.run, name, function))

    def input_fixture(self):
        plan = {'cases': [], 'argv': [r'C:\AuthoredWorker.exe'], 'worker_test_name': 'authored', 'bounds': {},
                'console_owner': self.expected_owner, 'resident_expected': {'guest': {}, 'controller': {}}}
        port = free_port()
        result_port = free_port()
        while result_port == port:
            result_port = free_port()
        config = {'owner_source_root': str(self.source), 'pair_root': str(self.attempt.parent),
                  'qmp_socket': str(self.root / 'qmp'), 'port': port, 'result_port': result_port,
                  'plan': 'authored', 'freeze': 'authored', 'review': 'authored', 'vm_start_ticks': 567,
                  'guest_stage_directory': r'C:\AuthoredPayload', 'guest_python_relative': 'python.exe',
                  'guest_bootstrap_relative': 'bootstrap.ps1', 'guest_collector_relative': 'collector.py',
                  'guest_python_version': '3.14.7', 'cells': []}
        bootstrap = b'authored-bootstrap'
        config['input_sha256'] = {'bootstrap': runner.digest(bootstrap), 'payload_zip': 'a' * 64}
        pins = {'python.exe': 'a' * 64, 'collector.py': 'b' * 64, 'bootstrap.ps1': runner.digest(bootstrap)}
        plan['resident_expected']['guest']['files'] = {str(PureWindowsPath(config['guest_stage_directory']) /
                                                           'payload' / key): sha for key, sha in pins.items()}
        raw = {'bootstrap': bootstrap, 'payload_zip': b'authored-zip', 'payload_pins': runner.encode(pins),
               'readiness_capture': runner.encode({'os': {'LastBootUpTime': '/Date(1234)/'}})}
        for n, binding in enumerate(self.bindings):
            disk = {k: v for k, v in asdict(binding).items() if k not in ('unit', 'case', 'root', 'volume_serial')}
            identities = {'disk': disk, 'guest': {'vm_pid': 567}, 'volume': {'volume_serial': binding.volume_serial}}
            plan.setdefault('identities', identities)
            plan['cases'].append({'unit': binding.unit, 'root': binding.root, 'case': binding.case, 'identities': identities})
            plan['resident_expected']['controller'][binding.case] = {'controller_epoch': str(n) * 32,
                                                                     'code_sha256': h.resident_code_sha256()}
            config['cells'].append({'case': binding.case, 'attempt_name': ('first', 'second')[n],
                                    'guest_control_directory': rf'C:\Control{n}', 'volume_plan': {'authored': n}})
        executable = self.root / 'qemu-system-x86_64'
        executable.touch()
        launch = self.root / 'launch.json'
        qmp = Path(config['qmp_socket'])
        pidfile = qmp.parent / 'qemu.pid'
        pidfile.write_text('567', encoding='ascii')
        launch.write_bytes(runner.encode({'launch': {'argv': [str(executable), '-qmp', 'unix:' + str(qmp),
                                                            '-pidfile', str(pidfile)]}}))
        disk = self.root / 'disk.json'
        disk.write_bytes(runner.encode({'capture_bindings': {'launch': {'path': str(launch),
                                                                        'sha256': runner.digest(launch.read_bytes())}}}))
        checked = {'plan': plan, 'worker_sha256': 'e' * 64, 'freeze': {'inputs': {'disk_configuration': {
            'path': str(disk), 'sha256': runner.digest(disk.read_bytes())}}}}
        self.config_path.write_bytes(runner.encode(config))
        return checked, config, raw

    def root_observer(self, data):
        result = self.result
        prepared, _, sha = result.load_preparation(data)
        args = types.SimpleNamespace(mode='observe-console', bindings=str(self.config_path),
            context=str(Path(data['attempt']) / 'console-context.json'), approved_context_sha256=runner.digest(runner.encode(data)),
            approved_bindings_sha256=data['config_sha256'], approved_prepared_sha256=sha,
            parent_screen_sha256=prepared['screen_sha256'], parent_confirmed_idle_console=True)
        try:
            self.run.run_result_mode(args, self.config, self.expected_owner, self.modules)
        except BaseException as exc:
            self.result_errors.append(exc)

    def guest(self, data, prepared):
        endpoint_port = self.config['port']
        result_port = self.config['result_port']
        binding = next(item for item in self.bindings if item.unit == data['unit'])
        status, script = request_http(result_port, 'GET', prepared['operator_route'])
        self.assertEqual(status, 200)
        self.assertEqual(runner.digest(script), prepared['operator_sha256'])
        events = []
        for seq, stage in enumerate(h.protocol.STAGES, 1):
            event = outer(stage, seq, binding)
            if seq == 1:
                snapshot = source_snapshot(binding.root + r'\source.bin', count=0)
                for moment in ('before', 'after'):
                    snapshot['bridge_' + moment]['volume_serial_u32'] = int(binding.volume_serial, 16)
                event['observation']['write_probe']['before'] = snapshot
            events.append(event)
            status, response = request_http(endpoint_port, 'POST', f'/event/{binding.unit}', h.protocol.encode_event(event))
            self.assertEqual(status, 200, stage)
            if stage in h.protocol.COMMANDS:
                self.assertEqual(h.protocol.validate_command(response, event)['command'], h.protocol.COMMANDS[stage])
        files, missing = [], []
        guest_paths = {'source.bin': binding.root + r'\source.bin', 'old-source.bin': binding.root + r'\old-source.bin'}
        for name in ('source.bin', 'old-source.bin', 'candidate.bin', 'output.bin', 'prepared.record', 'intent.record',
                     'observation.record', 'receipt.record', 'stdout.bin', 'stderr.bin', 'events.jsonl', 'transcript.jsonl',
                     'result.json', 'guest-transcript.jsonl', 'guest.json', 'volume-binding.json'):
            if name in ('source.bin', 'old-source.bin', 'candidate.bin', 'output.bin', 'prepared.record', 'intent.record',
                        'observation.record', 'receipt.record'):
                guest_path = guest_paths.get(name, str(PureWindowsPath(binding.root) / 'unit' / name))
                missing.append({'name': name, 'guest_path': guest_path, 'status': 'absent', 'error': None})
                continue
            guest_path = (data['request']['volume_binding_path'] if name == 'volume-binding.json' else
                          str(PureWindowsPath(data['request']['attempt_dir']) / name))
            content = b'authored export bytes'
            sha = runner.digest(content)
            self.assertEqual(request_http(endpoint_port, 'POST', f'/artifact/{binding.unit}/{name}', content,
                                  {'X-Imageinfo-Sha256': sha})[0], 200)
            files.append({'name': name, 'guest_path': guest_path, 'sha256': sha, 'bytes': len(content)})
        export = {'schema': 'imageinfo-0219-http-export-v1', 'exit_confirmed': True, 'files': files, 'missing': missing}
        self.assertEqual(request_http(endpoint_port, 'POST', f'/export-complete/{binding.unit}', runner.encode(export))[0], 200)
        capture, _ = capture_fixture({**data, 'screen_sha256': prepared['screen_sha256']})
        self.assertEqual(request_http(result_port, 'POST', f'/result/{binding.unit}', runner.encode(capture))[0], 200)
        return {'guest': {'case': binding.case, 'unit': binding.unit, 'request': data['request']}, 'events': events,
                'fixture': {'root': binding.root, 'source': guest_paths['source.bin'], 'old': guest_paths['old-source.bin']}}

    def run_first(self, peer, *, handoff=None, failure=None, result_capture=False, before_inspect=None, peer_check=None):
        result = self.result
        endpoint_wait = h.HttpEndpoint.wait
        parent = {'reads': 0, 'data': None, 'prepared': None}

        def stdin(_stream, _deadline):
            parent['reads'] += 1
            data = runner.decode((self.attempt / 'console-context.json').read_bytes())
            if parent['reads'] == 1:
                if before_inspect is not None:
                    before_inspect(data)
                return f"inspect-console {data['unit']}\n".encode()
            if parent['reads'] == 3:
                return (runner.decode(self.output.getvalue().splitlines()[-1])['stdin_token'] + '\n').encode()
            prepared = result.prepare(data)
            _, _, sha = result.load_preparation(data)
            parent.update(data=data, prepared=prepared)
            ready = self.attempt / 'console-preparation' / 'result-ready.json'
            if result_capture:
                self.result_thread = threading.Thread(target=self.root_observer, args=(data,), daemon=True)
                self.result_thread.start()
                deadline = time.monotonic() + 3
                while not ready.is_file() and not self.result_errors and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertTrue(ready.is_file(), self.result_errors)
            else:
                ready.write_bytes(runner.encode(result.readiness_record(data, prepared, sha)))
            token = 'launch-console ' + ' '.join((data['unit'], data['config_sha256'], sha, data['owner_sha256'],
                                                   prepared['screen_sha256'])) + '\n'
            return token.encode() if handoff is None else handoff(data, token.encode())

        def wait(endpoint):
            if not result_capture:
                raise AssertionError('refused prefix advanced to guest wait')
            parent['guest_cell'] = self.guest(parent['data'], parent['prepared'])
            self.result_thread.join(5)
            self.assertFalse(self.result_thread.is_alive())
            self.assertFalse(self.result_errors)
            return endpoint_wait(endpoint)

        def audit_host(attempt, *_):
            assets = next(row['value'] for row in self.rows(attempt / 'host.jsonl') if row['kind'] == 'http-assets')
            plan = {**self.checked['plan'], 'parent_transport': 'bounded-http-current-parent-v1',
                    'http_assets': assets['assets'], 'http_export': {key: assets[key] for key in (
                        'artifacts', 'required_files', 'require_export', 'export_timeout')}}
            report = audit.audit_host(attempt / 'host.jsonl', parent['guest_cell'], plan, 'a' * 64)
            return {'passed': True, 'case': report['binding']['case'], 'unit': report['binding']['unit'],
                    'scope': 'unchanged host auditor over actual authored integration journal'}

        @contextmanager
        def directory(path):
            yield path

        def write(directory, name, content, *, runner_readable=False):
            result.write(directory / name, content)

        with ExitStack() as patches:
            patches.enter_context(peer.physical_boundary())
            # OS/process checks have separate fixture coverage in test_console_result.
            for name, value in (('verify_current_files', lambda *_: None), ('root_inspector', lambda: None),
                                ('verify_live_processes', lambda *_: None), ('read_result_marker', result.read),
                                ('result_directory', directory), ('write_result', write)):
                patches.enter_context(patch.object(result, name, value))
            patches.enter_context(patch.object(self.transport, 'read_line', stdin))
            patches.enter_context(patch.object(h.HttpEndpoint, 'wait', wait))
            for item in self.checked['plan']['resident_expected']['controller'].values():
                item['code_sha256'] = h.resident_code_sha256()
            patches.enter_context(patch.object(self.run, 'artifact_manifest', lambda *_: None))
            patches.enter_context(patch.object(self.run, 'verify_qmp_peer', peer_check or (lambda *_: None)))
            if peer.family == socket.AF_INET:
                Path(self.config['qmp_socket']).touch()
            self.expected_owner['code_sha256'] = self.run.live_entries(self.modules)[1]
            if failure is None:
                owner = self.run.Attestation(self.source, self.expected_owner, self.modules)
                self.attempt.mkdir(parents=True)
                self.run.run_cell(self.config_path, runner.digest(self.config_path.read_bytes()), self.config, self.raw, self.checked,
                    {'plan_sha256': 'a' * 64, 'freeze_sha256': 'b' * 64}, h,
                    types.SimpleNamespace(audit=audit_host), owner, self.transport, result,
                    self.config['cells'][0], self.checked['plan']['cases'][0], self.attempt)
            else:
                inputs = {'plan_sha256': 'a' * 64, 'freeze_sha256': 'b' * 64}
                freezer = types.SimpleNamespace(ParentDecision=lambda *_: None, verify_current=lambda *_, **kw: self.checked)
                patches.enter_context(patch.object(self.run, 'inspect', lambda *_, **kw:
                    (self.config, self.raw, freezer, None, self.checked, inputs, h, {})))
                self.expected_owner['code_sha256'] = self.run.live_entries(self.modules)[1]
                # The extra process boundary replacement above must be present
                # before the live callable baseline, never after it.
                with self.assertRaisesRegex(Exception, failure):
                    self.run.run(self.config_path, reviewer='authored', approved_sha256=runner.digest(self.config_path.read_bytes()),
                                 modules=self.modules)
                attempts = self.rows(self.attempt.parent / 'attempts.jsonl')
                self.assertEqual([entry['attempt_dir'] for entry in attempts], ['first'])
                self.assertFalse((self.attempt.parent / 'second').exists())
                self.assertTrue((self.attempt / 'driver-failure.json').is_file())
        peer.thread.join(5)
        self.assertFalse(peer.thread.is_alive())

    def rows(self, path):
        return [runner.decode(line) for line in path.read_bytes().splitlines()]

    def peer(self, **kwargs):
        peer = SingleClient(self.config['qmp_socket'], self.bindings, **kwargs)
        self.addCleanup(peer.close)
        return peer

    def test_actual_one_client_through_screen_keys_controller_and_result(self):
        peer = self.peer()
        self.run_first(peer, result_capture=True)
        self.assertEqual(peer.accepted, 1)
        self.assertEqual([req['id'] for req in peer.requests], list(range(1, len(peer.requests) + 1)))
        self.assertEqual(peer.keys[-1], [transport.key('ret', True), transport.key('ret', False)])
        held = set()
        for batch in peer.keys:
            for row in batch:
                code = row['data']['key']['data']
                if row['data']['down']:
                    self.assertNotIn(code, held)
                    self.assertNotIn(code, ('ctrl', 'ctrl_r'))
                    held.add(code)
                else:
                    held.discard(code)
            self.assertFalse(held)
        ledger = self.rows(self.attempt / 'host.jsonl')
        self.assertEqual([row['value']['command']['command'] for row in ledger if row['kind'] == 'command-sent'],
                         ['start', 'continue', 'armed', 'cleared', 'release'])
        graph = [req['arguments']['options'][0]['file'] for req in peer.requests if req['execute'] == 'blockdev-reopen']
        self.assertEqual(graph, ['filter0', 'file0'])
        self.assertEqual(self.rows(self.attempt / 'console-owner.jsonl')[-1]['status'], 'audited')

    def test_old_second_constructor_gets_no_greeting(self):
        peer = self.peer()
        with peer.physical_boundary():
            first = h.JsonSocketChannel(self.config['qmp_socket'], timeout=.25)
            try:
                with self.assertRaises(TimeoutError):
                    h.JsonSocketChannel(self.config['qmp_socket'], timeout=.05)
            finally:
                first.close()
        self.assertEqual(peer.accepted, 1)

    def test_first_key_reply_loss_retains_exact_prefix_and_refuses_second_slot(self):
        peer = self.peer(loss=lambda keys: len(keys) == 1)
        self.run_first(peer, failure='EOF')
        terminal = runner.decode((self.attempt / 'driver-failure.json').read_bytes())
        self.assertEqual(terminal['input_progress'], {'phase': 'launch-consumed', 'journaled': 1, 'attempted': 1,
                                                     'acknowledged': 0, 'channel_poisoned': True})
        self.assertEqual(len(peer.keys), 1)
        self.assertFalse((self.attempt / 'console-input-complete.json').exists())

    def test_saved_ready_does_not_authorize_wrong_phase(self):
        peer = self.peer()
        self.run_first(peer, handoff=lambda data, _: f"collector-exit-confirmed {data['unit']} 0\n".encode(),
                       failure='exact live parent launch-console')
        self.assertEqual(peer.keys, [])

    def test_changed_source_refuses_before_keys(self):
        peer = self.peer()

        def changed(_data, token):
            with (self.source / 'console_transport.py').open('ab') as stream:
                stream.write(b'\n# authored post-load change\n')
            return token

        self.run_first(peer, handoff=changed, failure='loaded owner source changed')
        self.assertEqual(peer.keys, [])

    def test_early_valid_guest_event_cannot_move_controller(self):
        peer = self.peer()

        def early(data):
            self.assertEqual(request_http(self.config['port'], 'GET', '/launch.ps1')[0], 404)
            event = outer(bound=self.bindings[0])
            self.assertEqual(request_http(self.config['port'], 'POST', '/event/' + data['unit'],
                                          h.protocol.encode_event(event))[0], 400)

        self.run_first(peer, before_inspect=early, failure='prepared state or endpoint budget changed')
        rows = self.rows(self.attempt / 'host.jsonl')
        self.assertNotIn('guest-event', [row['kind'] for row in rows])
        self.assertEqual(peer.keys, [])

    def test_wrong_peer_refuses_before_filter_creation(self):
        peer = self.peer()

        def wrong(*_):
            raise ValueError('authored mismatched peer PID')

        self.run_first(peer, peer_check=wrong, failure='mismatched peer PID')
        self.assertEqual([row['execute'] for row in peer.requests], ['qmp_capabilities'])

    def test_changed_loaded_dispatch_refuses_before_keys(self):
        peer = self.peer()

        def changed(_data, token):
            self.transport.OwnedChannel.call = lambda *_args, **_kwargs: {}
            return token

        self.run_first(peer, handoff=changed, failure='loaded owner callable or code changed')
        self.assertEqual(peer.keys, [])

    def test_final_enter_reply_loss_remains_uncertain(self):
        peer = self.peer(loss=lambda keys: keys[-1] == [transport.key('ret', True), transport.key('ret', False)])
        self.run_first(peer, failure='EOF')
        terminal = runner.decode((self.attempt / 'driver-failure.json').read_bytes())
        progress = terminal['input_progress']
        self.assertEqual(progress['attempted'], len(peer.keys))
        self.assertEqual(progress['acknowledged'], len(peer.keys) - 1)
        self.assertTrue(progress['channel_poisoned'])
        self.assertFalse((self.attempt / 'console-input-complete.json').exists())

    def test_mid_chord_reply_loss_stops_without_retyping(self):
        peer = self.peer(loss=lambda keys: len(keys) == 8)
        self.run_first(peer, failure='EOF')
        terminal = runner.decode((self.attempt / 'driver-failure.json').read_bytes())
        self.assertEqual(len(peer.keys), 8)
        self.assertEqual(terminal['input_progress']['acknowledged'], 7)

    def test_graph_filter_change_refuses_before_input(self):
        peer = self.peer()

        def changed(_data, token):
            peer.disks['raw0'].config['inject-error'] = []
            return token

        self.run_first(peer, handoff=changed, failure='missing/extra rule')
        self.assertEqual(peer.keys, [])

    def test_isolated_entry_refuses_live_checkpoint_modes(self):
        entry = self.source / 'owner_entry.py'
        driver = self.source / 'host_runner.py'
        invocation = [sys.executable, '-I', '-S', str(entry), str(driver), self.expected_owner['sources'][driver.name]]
        inventory = subprocess.run([*invocation, 'owner-inventory'], capture_output=True, timeout=10, check=True)
        self.assertEqual(runner.decode(inventory.stdout)['sources'], self.expected_owner['sources'])
        for mode in ('run', 'prepare-console', 'observe-console'):
            result = subprocess.run([*invocation, mode], capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'checkpoint permits inventory and read-only inspection only', result.stderr)


if __name__ == '__main__':
    unittest.main()

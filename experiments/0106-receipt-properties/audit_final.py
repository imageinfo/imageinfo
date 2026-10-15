# Postcollection correction: validate the immutable captured controller bytes,
# mapping historical CRLF helpers to published canonical bytes. The frozen
# auditor also assumed each rich inventory was an atomic metadata/content view;
# this diagnostic must retain the measured stale-size disagreement separately
# from unchanged independently read bytes. No profile criterion is relaxed.
# The original bound auditor remains unchanged for evidence provenance.
"""Independently audit retained #0106 authored-marker property observations.

This auditor never imports the controller or opens a guest/media path. Raw
identities, absolute paths and timestamps remain in retained private captures.
"""
import argparse
import base64
import datetime
import hashlib
import json
from pathlib import Path
import re

ACTOR = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
REVISION = 'b819f54533c495b332c3d4dbb0caccef49923036'
# Exact retained accepted #0047 pair, independently compared with its native
# run binding and frozen actor source. Neither a new 93-case claim nor another
# executable may stand in for this previously audited baseline.
BASELINE_BINDING = '9cd2073baf64136aacaca899a1c28bacb33a6fd0e261a8fcd751256ffccdfc95'
BASELINE_AUDIT = '329231ec64189688dd65399ffb9d4ae34c4d6715052e7da4b0e536016a6de480'
MARKER = hashlib.sha256(b'3' * 65536).hexdigest()
FLAGS = ('committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed')
NAMES = ('.', 'source.marker', 'output.marker', 'prepared.record', 'intent.record',
         'observation.record', 'receipt.record')
INFO = {'identity', 'size', 'links', 'attributes', 'creationTime', 'lastWriteTime'}
PROPERTY_FIELDS = {'attributes', 'creationTimeUtc', 'lastWriteTimeUtc', 'sddl'}
SUCCESS = 'observed-receipt-recovery-required'
PREFIX = ['source-guarded', 'candidate-flushed', 'prepared-record-flushed',
          'intent-record-flushed', 'before-property-check', 'before-namespace-call',
          'published', 'installed-file-flushed', 'parent-flushed',
          'observation-file-flushed', 'observation-parent-flushed',
          'observed-record-flushed', 'receipt-written', 'receipt-file-flushed',
          'receipt-parent-flushed', 'final-checked']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def members(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON member')
        value[key] = item
    return value


def decode(data):
    return json.loads(data, object_pairs_hook=members)


def load(path):
    return decode(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def safe(event):
    require(type(event) is dict and all(event.get(flag) is False for flag in FLAGS),
            'Missing/unsafe native capability flag')


def events(result):
    require(type(result['stdout']) is list, 'Missing captured native output')
    parsed = [decode(line) if isinstance(line, str) else line for line in result['stdout']]
    require(len(parsed) <= 128, 'Native event bound exceeded')
    for item in parsed:
        safe(item)
    return parsed


def terminal(result, expected=None):
    require(result['exitCode'] == 0, 'Native process failed')
    endings = [item for item in events(result) if 'outcome' in item]
    require(len(endings) == 1, 'One terminal event required')
    if expected is not None:
        require(endings[0]['outcome'] == expected, 'Wrong native outcome')
    return endings[0]


def info(value):
    require(type(value) is dict and set(value) == INFO, 'Unexpected native Info shape')
    identity = value['identity'].split(':')
    require(len(identity) == 2 and all(0 < len(part) <= 16 and
            all(c in '0123456789abcdef' for c in part) for part in identity),
            'Invalid native identity')
    require(all(type(value[key]) is int and 0 <= value[key] <= 2**64 - 1
                for key in INFO - {'identity'}), 'Invalid integer property')
    return value


def properties(result):
    observed = terminal(result, 'receipt-properties-observed')
    require(observed['effectsAttempted'] is False and observed['contentRead'] is False
            and observed['ownedHandlesRemoved'] == 0
            and observed['propertyExclusionPromised'] is False,
            'Diagnostic observer claimed effects/exclusion')
    require(observed['queryOrder'] == ['native-info', 'security', 'streams',
            'path-binding', 'native-info'], 'Wrong native query order')
    rows = observed['observations']
    require([row['name'] for row in rows] == list(NAMES), 'Wrong fixed observer namespace')
    result = {}
    within = []
    for row in rows:
        name = row['name']
        require(row['diagnostic'] is None, 'Native observer query refused')
        for key in ('securityDiagnostic', 'bindingDiagnostic'):
            require(row[key] is None, 'Native property/binding check refused')
        require(row['streamDiagnostic'] == ('DIRECTORY_STREAM_QUERY_NOT_APPLICABLE'
                if name == '.' else None), 'Native stream check refused')
        left, right = info(row['before']), info(row['after'])
        require(left['attributes'] & 0x400 == right['attributes'] & 0x400 == 0,
                'Reparse object in fixed observer namespace')
        require(bool(left['attributes'] & 0x10) == bool(right['attributes'] & 0x10)
                == (name == '.'), 'Wrong native object kind')
        for field in sorted(INFO):
            if left[field] != right[field]:
                within.append({'object': name, 'field': field})
        result[name] = {'before': left, 'after': right}
    require(len({row['before']['identity'] for row in result.values()}) == len(NAMES),
            'Aliased fixed observer objects')
    return result, within


def changed(left, right):
    require(set(left) == set(right) == set(NAMES), 'Native namespace changed')
    rows = []
    for name in NAMES:
        for field in sorted(INFO):
            if left[name][field] != right[name][field]:
                row = {'object': name, 'field': field}
                if field in ('creationTime', 'lastWriteTime'):
                    row['deltaTicks'] = right[name][field] - left[name][field]
                rows.append(row)
    return rows


def context_info(context):
    require(context['purpose'] == 'imageinfo-od11-receipt-context-v1', 'Wrong context purpose')
    prior = context['prior']
    require(prior['purpose'] == 'imageinfo-od11-caller-context-v1'
            and prior['stage'] == 'after-publication'
            and prior['stoppedBeforePublication'] is False
            and prior['persistenceMode'] == 'write-through'
            and prior['sha256'] == MARKER, 'Wrong actual prior context')
    require([record['name'] for record in prior['records']] ==
            ['prepared', 'intent', 'observation'], 'Wrong context record set')
    values = {'.': info(prior['root']), 'source.marker': info(prior['source']),
              'output.marker': info(prior['candidate']),
              'receipt.record': info(context['receipt']['info'])}
    values.update({record['name'] + '.record': info(record['info']) for record in prior['records']})
    require(set(values) == set(NAMES), 'Wrong context namespace')
    return values


def inventory(result):
    require(result['exitCode'] == 0 and result['inventoryComplete'] is True
            and result['inventoryErrors'] == [], 'Incomplete rich inventory')
    files = result['files']
    require(len(files) == 6 and {entry['name'] for entry in files} == set(NAMES) - {'.'},
            'Unexpected rich inventory namespace')
    values = {entry['name']: entry for entry in files}
    require(result['rootInfo']['exists'] is True and result['rootInfo']['kind'] == 'directory'
            and result['rootInfo']['sddl'], 'Invalid rich root observation')
    for entry in values.values():
        require(entry['kind'] == 'file' and entry['sddl'] and not entry.get('inaccessible')
                and entry['streamsSupported'] is True and len(entry['streams']) == 1
                and entry['streams'][0]['name'] == ':$DATA'
                and type(entry['streams'][0]['length']) is int
                and 0 <= entry['streams'][0]['length'] <= 65536
                and type(entry['size']) is int and 0 <= entry['size'] <= 65536,
                'Invalid rich file/stream observation')
        if entry['name'].endswith('.record'):
            data = base64.b64decode(entry['recordBytesBase64'], validate=True)
            require(0 < len(data) <= 65536
                    and hashlib.sha256(data).hexdigest() == entry['sha256'],
                    'Captured record bytes/hash disagree')
    for name in ('source.marker', 'output.marker'):
        require(values[name]['sha256'] == MARKER,
                'Authored source/output bytes changed')
    return values


def rich_pair(before, after):
    first, second = inventory(before), inventory(after)
    differences = []
    for name, left, right in [(name, first[name], second[name]) for name in sorted(first)] + [
            ('.', before['rootInfo'], after['rootInfo'])]:
        separate = PROPERTY_FIELDS | {'size'}
        require({k: v for k, v in left.items() if k not in separate} ==
                {k: v for k, v in right.items() if k not in separate},
                'Captured rich names/content/streams changed')
        differences.extend({'object': name, 'field': field} for field in sorted(separate)
                           if left.get(field) != right.get(field))
    return first, differences


def rich_internal(result, stage):
    differences = []
    for name, entry in inventory(result).items():
        stream_size = entry['streams'][0]['length']
        record_size = (len(base64.b64decode(entry['recordBytesBase64'], validate=True))
                       if name.endswith('.record') else None)
        if entry['size'] != stream_size or (record_size is not None and entry['size'] != record_size):
            differences.append({'stage': stage, 'object': name,
                'cachedSizeAgreesWithStreamLength': entry['size'] == stream_size,
                'cachedSizeAgreesWithRecordBytes': None if record_size is None else entry['size'] == record_size,
                'streamLengthAgreesWithRecordBytes': None if record_size is None else stream_size == record_size})
    return differences


def filetime(text):
    """Convert the exact seven-digit UTC .NET round-trip form without floats."""
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d{7})(?:Z|\+00:00)', text)
    require(match is not None, 'Unsupported rich UTC timestamp form')
    whole = datetime.datetime.fromisoformat(match[1])
    offset = whole - datetime.datetime(1601, 1, 1)
    return (offset.days * 86400 + offset.seconds) * 10000000 + int(match[2])


def rich_native(rich, preceding, following, stage):
    """Retain disagreements between separately timed observation sources."""
    files = inventory(rich)
    files['.'] = rich['rootInfo']
    differences = []
    for name in NAMES:
        for rich_field, native_field in (('creationTimeUtc', 'creationTime'),
                                         ('lastWriteTimeUtc', 'lastWriteTime')):
            value = filetime(files[name][rich_field])
            before = preceding[name]['after'][native_field] if preceding is not None else None
            after = following[name]['before'][native_field]
            if value != after or (before is not None and value != before):
                differences.append({'stage': stage, 'object': name, 'field': native_field,
                    'matchesPrecedingNative': None if before is None else value == before,
                    'matchesFollowingNative': value == after,
                    'richMinusPrecedingNativeTicks': None if before is None else value - before,
                    'richMinusFollowingNativeTicks': value - after})
    return differences


def rich_context(rich, context, stage):
    differences = []
    for name, entry in inventory(rich).items():
        bound = context[name]
        for rich_field, native_field in (('creationTimeUtc', 'creationTime'),
                                         ('lastWriteTimeUtc', 'lastWriteTime')):
            if filetime(entry[rich_field]) != bound[native_field]:
                differences.append({'stage': stage, 'object': name, 'field': native_field})
        if entry['size'] != bound['size']:
            differences.append({'stage': stage, 'object': name, 'field': 'size'})
    return differences


def record(entry):
    envelope = decode(base64.b64decode(entry['recordBytesBase64'], validate=True))
    require(set(envelope) == {'body', 'sha256'} and type(envelope['body']) is str
            and hashlib.sha256(envelope['body'].encode('utf-8')).hexdigest() == envelope['sha256'],
            'Invalid record envelope')
    return decode(envelope['body'])


def bound_records(files, context):
    receipt = record(files['receipt.record'])
    require(receipt == {'purpose': 'imageinfo-od11-receipt-v1',
                       'protocol': 'imageinfo-new-output-protocol-v1',
                       'profile': 'unqualified-windows-marker-v1', 'prior': context['prior']},
            'Receipt differs from actual emitted context')
    require(files['receipt.record']['sha256'] == context['receipt']['sha256']
            and len(base64.b64decode(files['receipt.record']['recordBytesBase64'], validate=True))
            == context['receipt']['info']['size'],
            'Receipt bytes differ from actual emitted binding')
    for bound in context['prior']['records']:
        actual = files[bound['name'] + '.record']
        require(actual['sha256'] == bound['sha256']
                and len(base64.b64decode(actual['recordBytesBase64'], validate=True)) == bound['info']['size'],
                'Prior record bytes differ from context')
        value = record(actual)
        require(value['purpose'] == 'imageinfo-od11-marker-v1'
                and value['phase'] == {'prepared': 'prepared', 'intent': 'publication-intent',
                                      'observation': 'recovery-required'}[bound['name']]
                and value['target'] == 'output.marker' and value['expectedAbsence'] is True
                and value['committed'] is value['namespaceAcknowledged'] is False
                and value['observationOnly'] is True, 'Wrong prior record semantics')
        require(all(value[key] == context['prior'][key] for key in
                    ('root', 'source', 'candidate', 'sha256', 'persistenceMode')),
                'Prior record context disagrees')


def hello(envelope, agent_hash):
    require(envelope['path'] == '/hello', 'Missing guest hello envelope')
    value = envelope['value']
    groups = '\n'.join(value['groups']) if isinstance(value['groups'], list) else value['groups']
    require('S-1-5-32-544' not in groups and 'S-1-16-8192' in groups,
            'Guest token is not standard medium-integrity')
    require(value['build'] == '26300' and value['scriptSha256'] == agent_hash,
            'Guest build/agent mismatch')
    return datetime.datetime.fromisoformat(value['boot'])


def path_under(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), 'Binding path escapes declared source root')
    return path


def bindings(root, actor, observer, frozen, baseline):
    binding = load(root / 'source-binding.private.json')
    require(binding == load(root / 'source-binding-after.private.json'),
            'Source/binary/controller binding changed during observations')
    require(binding['actorSha256'] == sha(actor) == ACTOR
            and binding['observerSha256'] == sha(observer) != ACTOR,
            'Actor/observer binary mismatch')
    sources = binding['observerSources']
    required = {'rust-toolchain.toml', 'experiments/0032-windows-publication/src/ordinary.rs',
                'experiments/0032-windows-publication/src/native.rs',
                'experiments/0032-windows-publication/src/main.rs',
                'experiments/0032-windows-publication/Cargo.toml',
                'experiments/0032-windows-publication/Cargo.lock',
                'experiments/0028-recovery-evidence/Cargo.toml',
                'experiments/0028-recovery-evidence/Cargo.lock',
                'experiments/0038-staging-cleanup/src/staging.rs',
                'experiments/0038-staging-cleanup/src/disposition.rs'}
    require(required.issubset(sources) and len(sources) >= 20,
            'Incomplete frozen observer source binding')
    compiled = {p.relative_to(frozen).as_posix() for sub in
                ('experiments/0032-windows-publication/src', 'experiments/0028-recovery-evidence/src')
                for p in (frozen / sub).glob('*.rs')}
    require(compiled.issubset(sources), 'Compiled observer module omitted from binding')
    for relative, expected in sources.items():
        path = path_under(frozen, relative)
        require(b'\r' not in path.read_bytes() and sha(path) == expected,
                'Observer source differs or is not canonical LF')
    require(binding['nativeBaselineSha256'] == sha(baseline) == BASELINE_AUDIT
            and binding['nativeBaseline'] == load(baseline), 'Native baseline digest mismatch')
    require(binding['actorSourceBindingSha256'] == BASELINE_BINDING
            and binding['actorSourceBinding']['workerSha256'] == ACTOR,
            'Accepted native baseline does not bind the frozen actor')
    baseline_binding_bytes = (root / 'actor-source-binding.private.json').read_bytes()
    require(hashlib.sha256(baseline_binding_bytes).hexdigest() == BASELINE_BINDING
            and decode(baseline_binding_bytes) == binding['actorSourceBinding'],
            'Retained accepted native binding differs from independently reviewed pair')
    native = binding['nativeBaseline']
    require(native['caseCount'] == 93 and native['enabledProfiles'] == 0
            and all(native[flag] is False for flag in FLAGS), 'Wrong accepted native baseline')
    repo = Path(__file__).resolve().parents[2]
    controllers = binding['controllerSources']
    required_controllers = {'0106-receipt-properties/audit.py',
                            '0106-receipt-properties/qualify.py',
                            '0022-ordinary-output/windows_guest.py',
                            '0022-ordinary-output/guest_qualify.py'}
    normalized_controllers = {key.replace('\\', '/'): value for key, value in controllers.items()}
    require(required_controllers.issubset(normalized_controllers), 'Missing current controller binding')
    for relative, expected in normalized_controllers.items():
        captured = path_under(root / 'controller-sources.private', relative)
        published = path_under(repo / 'experiments', relative)
        require(sha(captured) == expected, 'Captured raw controller source differs from binding')
        raw = captured.read_bytes()
        canonical = raw.replace(b'\r\n', b'\n')
        require(b'\r' not in canonical and canonical == published.read_bytes().replace(b'\r\n', b'\n'),
                'Published canonical controller differs from captured bytes')
        require(not relative.startswith('0106-receipt-properties/') or b'\r' not in raw,
                'New #0106 source is not canonical LF')
    continuity = [load(root / ('host-' + stage + '.private.json'))
                  for stage in ('before', 'after')]
    for key in ('boot',):
        require(type(continuity[0][key]) is str and continuity[0][key]
                and continuity[0][key] == continuity[1][key],
                'WSL boot continuity not established')
    windows = [load(root / ('windows-host-' + stage + '.private.json'))
               for stage in ('before', 'after')]
    require(set(windows[0]) == set(windows[1]) == {'hostBootUtc', 'observedUtc'}
            and windows[0]['hostBootUtc'] == windows[1]['hostBootUtc'],
            'Actual Windows host boot continuity not established')
    host_boot = datetime.datetime.fromisoformat(windows[0]['hostBootUtc'])
    host_observations = [datetime.datetime.fromisoformat(proof['observedUtc']) for proof in windows]
    require(host_boot <= host_observations[0] < host_observations[1],
            'Windows host continuity observations are not ordered')
    require(not (root / 'incomplete.private.json').exists(), 'Run is explicitly incomplete')
    overlay = load(root / 'overlay-binding.private.json')
    require(all(len(overlay[key]) == 64 for key in
                ('diskSha256', 'varsSha256', 'manifestSha256')), 'Incomplete preserved-base binding')
    require(load(root / 'base-after.private.json') == overlay,
            'Retained base disk/firmware/manifest changed')
    return binding


def lifecycle(folder, before, after, kind, phase):
    request = before['request']
    require(request['action'] == 'run' and request['case'] == before['case']
            and request['mode'] == 'ordinary-receipt', 'Wrong frozen-actor request')
    raw = load(folder / 'controller-events.private.json')
    require(raw and all(entry['value'].get('id', '').startswith(before['case']) for entry in raw),
            'Unrelated or empty cell controller history')
    require([entry['at'] for entry in raw] == sorted(entry['at'] for entry in raw),
            'Cell controller history reordered')
    live = [entry for entry in raw if entry['value'].get('id') == request['id']]
    native = [entry['value']['event'] for entry in live if entry['path'] == '/event'
              and not entry['value']['event'].get('supervisorObservation')]
    for event in native:
        safe(event)
    expected = PREFIX if phase is None else PREFIX[:PREFIX.index(phase) + 1]
    require([event['barrier'] for event in native if 'barrier' in event] == expected,
            'Frozen actor barrier prefix differs')
    control_entries = [entry for entry in live if entry['path'] == '/event'
                       and 'supervisorControl' in entry['value']['event']]
    controls = [entry['value']['event']['supervisorControl'] for entry in control_entries]
    require([control['barrier'] for control in controls] == expected,
            'Supervisor did not observe each actor barrier')
    require([control['control'] for control in controls] ==
            (['continue'] * len(expected) if phase is None else
             ['continue'] * (len(expected) - 1) + ['held']), 'Wrong held/release schedule')
    require(len({control['processId'] for control in controls}) == 1
            and controls[0]['processId'] > 0, 'Owned actor process identity changed')
    contexts = [event['receiptContext'] for event in native if 'receiptContext' in event]
    require(contexts and all(context == contexts[0] for context in contexts)
            and contexts[-1] == before['receiptContext'], 'Supplied context differs from actual output')
    context = contexts[-1]
    context_info(context)
    results = [entry['value'] for entry in live if entry['path'] == '/result']
    if phase is not None:
        require(request['stopAt'] == phase and before['checkpoint'] == control_entries[-1],
                'Checkpoint is not the exact held actor barrier')
        pre_entries = [entry for entry in live if entry['path'] == '/event'
                       and 'preProperties' in entry['value']['event']]
        require(len(pre_entries) == 1 and
                pre_entries[0]['value']['event']['preProperties'] == before['preProperties']
                and live.index(pre_entries[0]) < live.index(control_entries[-1]),
                'Native pre-fault capture did not precede held notice')
    if kind == 'vm-off':
        require(not results and after['liveResult'] is None
                and not any('outcome' in event for event in native),
                'VM-off cell continued/completed original actor')
    else:
        require(results == [after['liveResult']], 'Final result differs from raw actor history')
        result = results[0]
        require(result['wrapperInventoryPerformed'] is False and events(result) == native,
                'Hidden actor inventory or inconsistent captured stdout')
        if kind is None:
            outcome = terminal(result, SUCCESS)
            require(all(outcome[key] is True for key in ('receiptWritten',
                    'receiptFileFlushSucceeded', 'receiptParentFlushSucceeded', 'finalCheckPassed')),
                    'Normal control did not complete observation sequence')
        else:
            require(request['control'] == 'terminate' and result['exitCode'] != 0
                    and not any('outcome' in event for event in native),
                    'Process fault was not a direct owned-child termination')
            stopped = result['processTermination']
            require(stopped['barrier'] == phase and stopped['control'] == 'terminate'
                    and stopped['killCalled'] is stopped['exitWaitCompleted'] is True
                    and stopped['barrierContinuationSent'] is False
                    and stopped['processId'] == controls[0]['processId']
                    and stopped['exitCode'] == result['exitCode'], 'Incomplete owned-child exit proof')
            notices = [entry for entry in live if entry['path'] == '/event'
                       and 'processTermination' in entry['value']['event']]
            require(len(notices) == 1 and notices[0]['value']['event']['processTermination'] == stopped
                    and [decode(line) for line in notices[0]['value']['event']['capturedStdout']] == native,
                    'Owned-process termination notice differs from captured result')
    return context, raw


def vm_exit(folder, before, after, postboots):
    target = load(folder / 'vm-off-target.private.json')
    complete = load(folder / 'vm-off-completed.private.json')
    require(target['command'] == 'quit' and complete == {'processExitConfirmed': True}
            and target['pid'] > 0 and target['qmpStatusBefore']['running'] is True,
            'Controlled VM-off exit was not confirmed')
    args = target['argv']
    require(Path(args[0]).name == 'qemu-system-x86_64'
            and any(arg.split(',')[0] == 'file=' + target['root'] + '/windows.qcow2' for arg in args)
            and 'unix:' + target['root'] + '/qmp,server=on,wait=off' in args,
            'VM-off target does not bind the exact private overlay')
    require(load(folder / 'relaunch.private.json')['exitCode'] == 0, 'Guest relaunch failed')
    require(after > before and after not in postboots, 'Missing/duplicate fresh VM-off boot')
    postboots.add(after)


def capture_order(raw, case, order, after):
    suffixes = ['native-post', 'rich-before'] if order == 'native-first' else ['rich-before', 'native-post']
    suffixes += ['native-pre-inspect', 'inspect', 'native-post-inspect', 'rich-after', 'native-final']
    expected_ids = [case + '-' + suffix for suffix in suffixes]
    results = [entry['value']['id'] for entry in raw if entry['path'] == '/result'
               and entry['value']['id'] in expected_ids]
    require(results == expected_ids, 'Actual post-fault observer ordering differs')
    fields = ('postbootProperties', 'inventoryBefore') if order == 'native-first' else (
              'inventoryBefore', 'postbootProperties')
    fields += ('preInspectProperties', 'inspect', 'postInspectProperties',
               'inventoryAfter', 'finalProperties')
    for identifier, field in zip(expected_ids, fields):
        entries = [entry['value'] for entry in raw if entry['path'] == '/result'
                   and entry['value']['id'] == identifier]
        require(entries == [after[field]], 'Saved observation differs from raw controller result')


def audit(root, actor, observer, frozen, baseline):
    binding = bindings(root, actor, observer, frozen, baseline)
    expected = [('normal', None, None, 'native-first')] + [
        (f'{kind}-{phase}-{order}', kind, phase, order)
        for phase in ('receipt-written', 'receipt-file-flushed')
        for kind in ('process-kill', 'vm-off') for order in ('native-first', 'rich-first')]
    summary = load(root / 'summary.private.json')
    require(summary['caseCount'] == 9 and summary['vmOffs'] == 4
            and summary['enabledProfiles'] == 0 and all(summary[flag] is False for flag in FLAGS)
            and summary['hostCachesAlive'] is True, 'Wrong finite run summary')
    require(summary['cases'] == [{'id': name, 'faultKind': kind, 'barrier': phase,
                                 'order': order, 'retained': True}
                                for name, kind, phase, order in expected], 'Wrong nine-cell schedule')
    rows, postboots = [], set()
    for name, kind, phase, order in expected:
        folder = root / name
        before, after = load(folder / 'before.private.json'), load(folder / 'after.private.json')
        require(after['order'] == order, 'Wrong saved observation order')
        terminal(before['prepare'], 'owned-source-prepared')
        first = hello(before['hello'], binding['guestAgentSha256'])
        second = hello(after['hello'], binding['guestAgentSha256'])
        context, raw = lifecycle(folder, before, after, kind, phase)
        if kind == 'vm-off':
            vm_exit(folder, first, second, postboots)
        else:
            require(first == second, 'Unexpected guest boot in process/normal cell')
            require(not (folder / 'vm-off-target.private.json').exists(), 'Unexpected extra VM-off')
        capture_order(raw, before['case'], order, after)
        timeline, within = [], []
        for label, value in [('pre-fault', before['preProperties']),
                             ('post-fault-first-native', after['postbootProperties']),
                             ('before-frozen-inspection', after['preInspectProperties']),
                             ('after-frozen-inspection', after['postInspectProperties']),
                             ('after-final-rich-inventory', after['finalProperties'])]:
            require(value['observerSha256'] == binding['observerSha256']
                    and value['wrapperInventoryPerformed'] is False, 'Wrong observer/hidden inventory')
            snapshot, deltas = properties(value)
            timeline.append((label, snapshot))
            within.extend({'stage': label, **delta} for delta in deltas)
        bound = context_info(context)
        pre = {key: value['before'] for key, value in timeline[0][1].items()}
        context_changes = changed(bound, pre)
        # Root mtime/size/link fields are not immutable context bindings: the
        # original directory snapshot predates the worker's record creation.
        context_changes = [delta for delta in context_changes if delta['object'] != '.' or
                           delta['field'] in ('identity', 'attributes', 'creationTime')]
        transitions = []
        for (left_label, left), (right_label, right) in zip(timeline, timeline[1:]):
            transitions.append({'from': left_label, 'to': right_label,
                'changes': changed({n: x['after'] for n, x in left.items()},
                                   {n: x['before'] for n, x in right.items()})})
        files, rich_changes = rich_pair(after['inventoryBefore'], after['inventoryAfter'])
        rich_internal_changes = rich_internal(after['inventoryBefore'], 'rich-before-inspection')
        rich_internal_changes += rich_internal(after['inventoryAfter'], 'rich-after-inspection')
        rich_context_changes = rich_context(after['inventoryBefore'], bound, 'rich-before-inspection')
        rich_context_changes += rich_context(after['inventoryAfter'], bound, 'rich-after-inspection')
        rich_native_changes = rich_native(after['inventoryBefore'],
            timeline[1][1] if order == 'native-first' else None,
            timeline[2][1] if order == 'native-first' else timeline[1][1],
            'rich-before-inspection')
        rich_native_changes += rich_native(after['inventoryAfter'], timeline[3][1],
                                           timeline[4][1], 'rich-after-inspection')
        bound_records(files, context)
        require(after['inspectRequest'] == {'receiptContext': context},
                'Inspector did not receive exact externally captured context')
        inspection = terminal(after['inspect'])
        require(inspection['outcome'] in (SUCCESS, 'receipt-inspection-refused')
                and inspection['effectsAttempted'] is False and inspection['ownedHandlesRemoved'] == 0
                and inspection['sourceRetained'] is inspection['rootRetained'] is True
                and after['inspect']['wrapperInventoryPerformed'] is False,
                'Inspector claimed effects or unexpected outcome')
        require(kind is not None or inspection['outcome'] == SUCCESS, 'Normal inspection refused')
        mismatches = ([{'stage': 'context-to-pre-fault', 'changes': context_changes}]
                      if context_changes else [])
        mismatches += [{'stage': row['to'], 'changes': row['changes']} for row in transitions if row['changes']]
        first_native_mismatch = 'context-to-pre-fault' if context_changes else None
        if first_native_mismatch is None:
            for index, (label, _) in enumerate(timeline):
                if index and transitions[index - 1]['changes']:
                    first_native_mismatch = label
                    break
                if any(delta['stage'] == label for delta in within):
                    first_native_mismatch = label + '-within-observer'
                    break
        stage_candidates = [('context-to-pre-fault', bool(context_changes)),
            ('pre-fault-within-observer', any(delta['stage'] == 'pre-fault' for delta in within))]
        native_post = [('post-fault-first-native', bool(transitions[0]['changes'])),
            ('post-fault-first-native-within-observer',
             any(delta['stage'] == 'post-fault-first-native' for delta in within))]
        rich_first = [('first-rich-inventory', any(delta['stage'] == 'rich-before-inspection'
                                                  for delta in rich_context_changes + rich_internal_changes))]
        stage_candidates += native_post + rich_first if order == 'native-first' else rich_first + native_post
        stage_candidates += [(row['to'], bool(row['changes'])) for row in transitions[1:]]
        first_property_mismatch = next((stage for stage, differs in stage_candidates if differs),
                                       first_native_mismatch)
        rows.append({'id': name, 'faultKind': kind, 'barrier': phase, 'order': order,
            'bootChanged': first != second, 'inspection': inspection['outcome'],
            'inspectionDiagnostic': inspection.get('diagnostic'),
            'firstObservedNativeMismatchStage': first_native_mismatch,
            'firstObservedPropertyMismatchStage': first_property_mismatch,
            'nativeDifferences': mismatches, 'withinObserverDifferences': within,
            'richPropertyDifferences': rich_changes,
            'richNativeTimeDisagreements': rich_native_changes,
            'richContextPropertyDisagreements': rich_context_changes,
            'richMetadataContentDisagreements': rich_internal_changes,
            'byteNameInventoriesUnchanged': not any(delta['field'] == 'size' for delta in rich_changes),
            'capturedBytesAndNamesUnchanged': True,
            'sourceRetained': True, 'rootRetained': True, **dict.fromkeys(FLAGS, False)})
    require(len(postboots) == 4, 'Four distinct VM-off boots required')
    return {'schemaVersion': 1, 'observedOn': '2026-10-15', 'data': 'authored markers only',
        'caseCount': 9, 'vmOffs': 4, 'processTerminations': 4, 'normalControls': 1,
        'vmOffMethod': 'QMP quit and confirmed emulator exit; backend I/O may drain',
        'guestBuild': '26300', 'standardWorkerToken': True, 'sameHostBoot': True,
        'hostCachesAlive': True, 'actorSha256': ACTOR, 'observerSha256': binding['observerSha256'],
        'controllerSources': binding['controllerSources'],
        'controllerCanonicalSources': {relative.replace('\\', '/'):
            hashlib.sha256(path_under(root / 'controller-sources.private', relative.replace('\\', '/'))
                           .read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for relative in binding['controllerSources']}, 'cases': rows,
        'nativeMismatchCells': sum(bool(row['nativeDifferences'] or row['withinObserverDifferences']) for row in rows),
        'richPropertyMismatchCells': sum(bool(row['richPropertyDifferences']) for row in rows),
        'richNativeTimeDisagreementCells': sum(bool(row['richNativeTimeDisagreements']) for row in rows),
        'richMetadataContentDisagreementCells': sum(bool(row['richMetadataContentDisagreements']) for row in rows),
        'enabledProfiles': 0, **dict.fromkeys(FLAGS, False),
        'limits': 'Finite native timestamp/identity diagnostic. Controlled VM-off can drain I/O and is distinct from historical emulator SIGKILL/NMI. Host caches remain alive; no observation establishes cause, a fix, namespace/receipt acknowledgement, durable current custody, a supported storage profile or RAW admission.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('root', 'actor', 'observer', 'frozen', 'baseline', 'public'):
        parser.add_argument('--' + argument, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.actor.resolve(), args.observer.resolve(),
                   args.frozen.resolve(), args.baseline.resolve())
    with args.public.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'auditedCells': result['caseCount'], 'vmOffs': result['vmOffs'],
                      'nativeMismatchCells': result['nativeMismatchCells'], 'enabledProfiles': 0}))

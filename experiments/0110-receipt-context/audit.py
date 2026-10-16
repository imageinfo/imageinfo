"""Independent read-only audit of #0110 marker context-boundary captures.

No controller is imported and no worker, native adapter or guest command is run.
Raw paths, object identities and timestamps remain in the private captures.
"""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
_spec = importlib.util.spec_from_file_location(
    'receipt106_independent_audit', HERE.parent/'0106-receipt-properties/audit_final.py')
old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old)
require, load, sha, decode = old.require, old.load, old.sha, old.decode
FLAGS = old.FLAGS
MODE = 'ordinary-receipt-checked-flush'
F869 = old.ACTOR
OBSERVER = '2a15627fd4a04c9efbb5eee93e3e8ee76fb0401cda362824a1a0cb34293a6bb7'
SUCCESS = old.SUCCESS
NAMES = set(old.NAMES) - {'.'}
PREFIX = old.PREFIX
MATRIX = {
    'normal': (None, None, 'receipt-written', 'receipt.record'),
    'cancel-pre-context': ('cancel', None, 'receipt-written', 'receipt.record'),
    'fail-pre-context': ('fail', None, 'receipt-written', 'receipt.record'),
    'terminate-pre-context': ('kill', None, 'receipt-written', 'receipt.record'),
    'receipt-mtime-pre-context': (None, 'mtime', 'receipt-written', 'receipt.record'),
    'receipt-ads-pre-context': (None, 'ads', 'receipt-written', 'receipt.record'),
    'held-default-write': (None, 'write', 'receipt-written', 'receipt.record'),
    'held-name-rename': (None, 'rename', 'receipt-written', 'receipt.record'),
    'later-stale-context': (None, 'mtime', 'receipt-file-flushed', 'receipt.record'),
    'source-property-pre-context': (None, 'mtime', 'receipt-written', 'source.marker'),
}


def native_events(folder):
    data = (folder/'stdout.jsonl').read_text(encoding='utf-8-sig')
    values = [decode(line) for line in data.splitlines()]
    require(0 < len(values) <= 128, 'Missing/unbounded native output')
    for value in values:
        old.safe(value)
    return values


def event_contract(events):
    """Require an exact checked event immediately before each actual export."""
    require(type(events) is list and 0 < len(events) <= 128, 'Invalid event bound')
    contexts, boundaries = [], []
    prior_context = None
    for ordinal, event in enumerate(events):
        old.safe(event)
        if 'callerContext' in event:
            prior_context = event['callerContext']
        if 'checkedReceiptBoundary' in event:
            name = event['checkedReceiptBoundary']
            require(name in ('receipt-file-flushed', 'receipt-parent-flushed')
                    and event.get('receiptFileFlushSucceeded') is True
                    and event.get('originalPropertiesMatch') is True,
                    'Unchecked receipt export boundary')
            require(ordinal + 1 < len(events) and 'receiptContext' in events[ordinal + 1],
                    'Checked event did not immediately precede an export')
            boundaries.append(name)
        if 'receiptContext' not in event:
            continue
        require(ordinal >= 1 and 'checkedReceiptBoundary' in events[ordinal - 1],
                'Receipt context lacks an immediately preceding exact check')
        name = events[ordinal - 1]['checkedReceiptBoundary']
        require(any(item.get('barrier') == 'receipt-written' for item in events[:ordinal - 1]),
                'Receipt context was exported before the written barrier')
        require(not any(item.get('barrier') == name for item in events[:ordinal]),
                'Receipt export occurred after its declared barrier')
        require(ordinal + 1 < len(events) and events[ordinal + 1].get('barrier') == name,
                'Receipt context is not followed by its checked barrier')
        context = event['receiptContext']
        old.context_info(context)
        require(prior_context is not None and context['prior'] == prior_context,
                'Receipt does not bind the actual latest caller context')
        require(not contexts or context == contexts[0][1],
                'Original receipt binding was rebased between exports')
        contexts.append((ordinal, context))
    require(boundaries == ['receipt-file-flushed', 'receipt-parent-flushed'][:len(boundaries)],
            'Duplicate/out-of-order checked export boundary')
    require(len(boundaries) == len(contexts), 'Unpaired context/check events')
    return contexts


def file_inventory(root):
    """Same fields as retained native inventory, independently recomputed."""
    result = {}
    for path in root.iterdir():
        require(path.is_file(), 'Unexpected transaction child kind')
        stat = path.stat()
        result[path.name] = {'sha256': sha(path), 'size': stat.st_size,
            'mtime': stat.st_mtime_ns, 'identity': stat.st_ino,
            'links': stat.st_nlink, 'attributes': stat.st_file_attributes}
        try:
            result[path.name+':probe'] = {'sha256': sha(Path(str(path)+':probe'))}
        except FileNotFoundError:
            pass
    return result


def compare_native_context(context, inventory, stale=False):
    bound = old.context_info(context)
    for name in NAMES:
        left, right = bound[name], inventory[name]
        require(right['identity'] == int(left['identity'].split(':')[1], 16)
                and right['size'] == left['size'] and right['links'] == left['links']
                and right['attributes'] == left['attributes'],
                'Retained native artifact properties differ from context')
        actual = right['mtime']//100 + 116444736000000000
        if stale and name == 'receipt.record':
            require(actual != left['lastWriteTime'], 'Stale context conflict was not retained')
        else:
            require(actual == left['lastWriteTime'], 'Retained native timestamp differs from context')


def native_record_files(root):
    files = {}
    for name in NAMES:
        data = (root/name).read_bytes()
        files[name] = {'sha256': hashlib.sha256(data).hexdigest(),
                      'recordBytesBase64': base64.b64encode(data).decode()}
    return files


def bound_prior_records(files, prior):
    receipt = old.record(files['receipt.record'])
    require(receipt == {'purpose': 'imageinfo-od11-receipt-v1',
        'protocol': 'imageinfo-new-output-protocol-v1',
        'profile': 'unqualified-windows-marker-v1', 'prior': prior},
        'Retained receipt does not contain actual emitted prior context')
    for binding in prior['records']:
        name = binding['name']+'.record'
        data = base64.b64decode(files[name]['recordBytesBase64'], validate=True)
        require(files[name]['sha256'] == binding['sha256']
                and len(data) == binding['info']['size'], 'Retained prior record hash/length mismatch')
        record = old.record(files[name])
        require(record['purpose'] == 'imageinfo-od11-marker-v1'
                and record['phase'] == {'prepared':'prepared', 'intent':'publication-intent',
                    'observation':'recovery-required'}[binding['name']]
                and record['expectedAbsence'] is record['observationOnly'] is True
                and record['committed'] is record['namespaceAcknowledged'] is False
                and record['target'] == 'output.marker'
                and all(record[key] == prior[key] for key in
                    ('root','source','candidate','sha256','persistenceMode')),
                'Retained prior record semantics/context differ')


def source_binding(root, binary, frozen):
    binding = load(root/'source-binding.private.json')
    require(binding == load(root/'source-binding-after.private.json'),
            'Native source/controller binding changed')
    require(binding['workerSha256'] == sha(binary) and binding['mode'] == MODE,
            'Native candidate hash/mode mismatch')
    sources = binding['sources']
    compiled = {p.relative_to(frozen).as_posix() for directory in
        ('experiments/0032-windows-publication/src', 'experiments/0028-recovery-evidence/src')
        for p in (frozen/directory).glob('*.rs')}
    require(len(compiled) >= 15 and compiled.issubset(sources), 'Compiled source omitted')
    required = {'rust-toolchain.toml', 'experiments/0032-windows-publication/Cargo.toml',
        'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0028-recovery-evidence/Cargo.toml',
        'experiments/0028-recovery-evidence/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs',
        'experiments/0038-staging-cleanup/src/disposition.rs'}
    require(required.issubset(sources), 'Missing build source binding')
    for relative, digest in sources.items():
        path = old.path_under(frozen, relative)
        require(b'\r' not in path.read_bytes() and sha(path) == digest,
                'Frozen build source is not exact canonical LF')
    harness = load(root/'harness-binding.private.json')
    require({'experiments/0110-receipt-context/qualify.py',
             'experiments/0110-receipt-context/audit.py',
             'experiments/0033-owner-rights/actor.py',
             'experiments/0034-source-oplocks/qualify.py'}.issubset(harness),
            'Missing imported native harness binding')
    for relative, digest in harness.items():
        path = old.path_under(root/'harness-sources.private', relative)
        raw = path.read_bytes()
        require(sha(path) == digest and raw.replace(b'\r\n', b'\n') ==
                old.path_under(REPO, relative).read_bytes().replace(b'\r\n', b'\n'),
                'Captured native harness differs from reviewed published source')
        require(not relative.startswith('experiments/0110-') or b'\r' not in raw,
                'New native harness source must be LF')
    return binding


def native_audit(root, binary, inspector, frozen):
    require(not (root/'failed-report.private.json').exists(), 'Native run is explicitly incomplete')
    binding = source_binding(root, binary, frozen)
    report = load(root/'report.private.json')
    require(report['caseCount'] == 11 and report['mode'] == MODE
            and report['workerSha256'] == sha(binary)
            and report['inspectorSha256'] == sha(inspector) == F869,
            'Wrong eleven-cell native binding')
    require(report['enabledProfiles'] == 0 and all(report.get(flag) is False for flag in FLAGS),
            'Native report claimed enabled capabilities')
    rows = report['cases']
    ids = [row['id'] for row in rows]
    require(len(ids) == len(set(ids)) == 11
            and set(ids) == set(MATRIX) | {'unchanged-inspector-stale-refusal'},
            'Wrong/duplicate native case set')
    public = []
    for row in rows:
        name = row['id']
        folder = root/name
        require(row == load(folder/'case.private.json'), 'Native case differs from raw saved row')
        inventories = load(folder/'inventories.private.json')
        if name == 'unchanged-inspector-stale-refusal':
            events = native_events(folder/'inspect')
            require(row['inspectorSha256'] == F869 and row['contextSource'] ==
                    row['transactionSource'] == 'later-stale-context', 'Wrong stale inspector binding')
            terminal = events[-1]
            require(terminal == row['terminal'] and row['exitCode'] ==
                    load(folder/'inspect/exit.json')['exitCode'] == 0
                    and terminal['outcome'] == 'receipt-inspection-refused'
                    and terminal['diagnostic'] == 'FILE_PROPERTIES_CHANGED'
                    and terminal['effectsAttempted'] is False
                    and terminal['ownedHandlesRemoved'] == 0,
                    'Unchanged inspector did not refuse stale original context')
            require(inventories['before'] == inventories['after'], 'Stale inspection changed artifacts')
            actual = file_inventory(root/'later-stale-context/transaction.marker')
            require(actual == inventories['after'], 'Stale inspector artifacts differ from capture')
            request = load(folder/'inspect-input.private.json')
            require(request == load(root/'later-stale-context/context.private.json'),
                    'Inspector was not supplied actual externally retained stale context')
            argv = load(folder/'inspect/argv.private.json')
            require(Path(argv[0]).resolve() == inspector.resolve()
                    and Path(argv[1]).resolve() == (root/'later-stale-context/transaction.marker').resolve()
                    and argv[2] == 'ordinary-receipt-inspect', 'Wrong inspector executable/mode/target')
            public.append({'id': name, 'inspection': terminal['outcome'],
                'diagnostic': terminal['diagnostic'], 'unchangedInventory': True})
            continue
        stop, action, phase, role = MATRIX[name]
        events = native_events(folder/'worker')
        contexts = event_contract(events)
        barriers = [event['barrier'] for event in events if 'barrier' in event]
        bad = stop is not None or action in ('mtime', 'ads')
        expected_prefix = PREFIX[:PREFIX.index(phase)+1] if bad else PREFIX
        require(barriers == expected_prefix, 'Native barrier history differs from finite cell')
        expected_count = 1 if name == 'later-stale-context' else (0 if bad else 2)
        require(row['mode'] == MODE and row['phase'] == phase and row['stop'] == stop
                and row['contextCount'] == len(contexts) == expected_count
                and row['contextOrdinals'] == [ordinal for ordinal, _ in contexts]
                and row['retained'] is True, 'Native context schedule/summary differs')
        argv = load(folder/'worker/argv.private.json')
        require(Path(argv[0]).resolve() == binary.resolve()
                and Path(argv[1]).resolve() == (folder/'transaction.marker').resolve()
                and argv[2] == MODE, 'Wrong actual worker executable/mode/target')
        code = load(folder/'worker/exit.json')['exitCode']
        require(code == row['exitCode'], 'Native exit differs from raw capture')
        controls = load(folder/'worker/controls.json')
        expected_controls = ['continue']*(len(barriers)-(1 if stop else 0))
        if stop in ('cancel', 'fail'):
            expected_controls.append(stop)
        require(controls == expected_controls, 'Native control history differs')
        terminals = [event for event in events if 'outcome' in event]
        if stop == 'kill':
            require(code != 0 and not terminals and row['terminal'] is None,
                    'Owned termination cell completed actor')
        else:
            require(code == 0 and len(terminals) == 1 and terminals[0] == row['terminal'],
                    'Wrong native terminal/exit capture')
            terminal = terminals[0]
            require(terminal['outcome'] == ('recovery-required' if bad else SUCCESS)
                    and terminal['ownedHandlesRemoved'] == 0
                    and terminal['sourceRetained'] is terminal['rootRetained'] is True
                    and terminal['publicationAttempted'] is terminal['publicationCallSucceeded'] is True
                    and terminal['receiptWritten'] is True,
                    'Native cell lost guards/artifacts or claimed wrong outcome')
            if stop in ('cancel', 'fail'):
                require(terminal['diagnostic'] == {'cancel':'CONTROL_CANCEL',
                    'fail':'INJECTED_PROTOCOL_FAILURE'}[stop], 'Wrong protocol stop diagnostic')
            elif action == 'mtime':
                require(terminal['diagnostic'] == 'FILE_PROPERTIES_CHANGED', 'Mtime conflict was not detected')
            elif action == 'ads':
                require(terminal['diagnostic'] is not None, 'ADS conflict was not detected')
            else:
                require(terminal['diagnostic'] is None and terminal['finalCheckPassed'] is True,
                        'Successful cell did not finish all checks')
            require(terminal['receiptFileFlushSucceeded'] is (expected_count > 0),
                    'First export is not backed by explicit file-flush success')
        actors = row['actors']
        require(len(actors) == (1 if action else 0), 'Wrong native actor count')
        if actors:
            actor = actors[0]
            require(actor['action'] == action and actor['role'] == role
                    and events[actor['eventOrdinal']].get('barrier') == phase
                    and actor['allowed'] is (action not in ('write', 'rename')),
                    'Native actor ran at wrong boundary/role or guard outcome differs')
            require(actor['winError'] is None if actor['allowed'] else
                    type(actor['winError']) is int and actor['winError'] > 0,
                    'Native denial/success lacks error result')
        after = inventories['after']
        extra = {'receipt.record:probe'} if action == 'ads' else set()
        require(set(inventories['before']) == {'source.marker'} and set(after) == NAMES | extra,
                'Native artifacts were removed/added outside finite cell')
        for leaf in ('source.marker', 'output.marker'):
            require(after[leaf]['sha256'] == old.MARKER and after[leaf]['size'] == 65536,
                    'Native source/output bytes changed')
        source_before = dict(inventories['before']['source.marker'])
        source_after = dict(after['source.marker'])
        if role == 'source.marker' and action == 'mtime':
            require(source_before.pop('mtime') != source_after.pop('mtime'), 'Source mtime actor had no effect')
        require(source_before == source_after, 'Native source changed beyond declared property actor')
        require(file_inventory(folder/'transaction.marker') == after,
                'Retained native artifacts differ from raw capture')
        prior = [event['callerContext'] for event in events if 'callerContext' in event][-1]
        bound_prior_records(native_record_files(folder/'transaction.marker'), prior)
        if contexts:
            context = contexts[0][1]
            require(load(folder/'context.private.json') == context,
                    'Retained context differs from actual first export')
            compare_native_context(context, after, stale=name == 'later-stale-context')
            old.bound_records(native_record_files(folder/'transaction.marker'), context)
        else:
            require(not (folder/'context.private.json').exists(), 'Context invented for pre-context cell')
        public.append({'id': name, 'contextCount': len(contexts), 'contextExportOrdinals':
            [ordinal for ordinal, _ in contexts], 'actors': [{'action': item['action'],
            'role': item['role'], 'allowed': item['allowed']} for item in actors],
            'outcome': row['terminal']['outcome'] if row['terminal'] else 'owned-process-terminated',
            'diagnostic': row['terminal']['diagnostic'] if row['terminal'] else None,
            'sourceOutputBytesRetained': True, 'ownedHandlesRemoved': 0})
    return {'schemaVersion': 1, 'observedOn': '2026-10-16', 'data': 'authored markers only',
        'caseCount': 11, 'mode': MODE, 'workerSha256': binding['workerSha256'],
        'inspectorSha256': F869, 'cases': public, 'enabledProfiles': 0,
        'vmOffs': 0, 'timestampRebindingAllowed': False, 'driftCauseEstablished': False,
        **dict.fromkeys(FLAGS, False)}


def ready_proof(proof, binding, transport):
    event, result, hello = proof['readyEvent'], proof['challengeResult'], proof['hello']
    require(all(item in transport for item in (event, result, hello)),
            'Readiness proof is absent from complete transport history')
    ready = event['value']['event']
    require(event['path'] == '/event' and event['value']['id'] == 'ready'
            and type(ready['instance']) is str and len(ready['instance']) == 36,
            'Missing exact agent-instance readiness')
    require(all(ready[key] == binding[key] for key in
            ('actorSha256','observerSha256','inspectorSha256'))
            and ready['scriptSha256'] == binding['guestAgentSha256'],
            'Readiness payload hash differs from frozen role')
    challenge = result['value']['challenge']
    require(type(challenge) is str and len(challenge) == 32
            and all(char in '0123456789abcdef' for char in challenge)
            and result['path'] == '/result' and result['value']['id'] == 'ready-'+challenge
            and result['value']['ready'] == ready, 'Active agent challenge was not satisfied')
    old.hello(hello, binding['guestAgentSha256'])
    require(hello['at'] <= event['at'] < result['at'], 'Readiness challenge precedes payload installation')
    return ready['instance'], result['at']


def guest_binding(root, binary, observer, inspector, frozen, baseline):
    native = native_audit(baseline, binary, inspector, frozen)
    binding = load(root/'source-binding.private.json')
    require(binding == load(root/'source-binding-after.private.json'),
            'Guest source/binary/controller binding changed')
    require(binding['actorSha256'] == sha(binary) == native['workerSha256']
            and binding['observerSha256'] == sha(observer) == OBSERVER
            and binding['inspectorSha256'] == sha(inspector) == F869,
            'Guest role binary differs from qualified exact role')
    require(binding['nativeBaselineSha256'] == sha(baseline/'report.private.json')
            and binding['nativeBindingSha256'] == sha(baseline/'source-binding.private.json')
            and binding['candidateSources'] == load(baseline/'source-binding.private.json')['sources'],
            'Guest candidate lacks exact eleven-cell native/source binding')
    controllers = binding['controllerSources']
    require({'0110-receipt-context/guest.py', '0110-receipt-context/audit.py',
             '0110-receipt-context/console.py', '0106-receipt-properties/qualify.py',
             '0106-receipt-properties/audit_final.py', '0022-ordinary-output/windows_guest.py',
             '0022-ordinary-output/guest_qualify.py'}.issubset(controllers),
            'Guest imported helper/controller binding omitted')
    for relative, digest in controllers.items():
        raw = old.path_under(root/'controller-sources.private', relative)
        canonical = raw.read_bytes().replace(b'\r\n', b'\n')
        require(sha(raw) == digest and b'\r' not in canonical
                and canonical == old.path_under(REPO/'experiments', relative).read_bytes().replace(b'\r\n', b'\n'),
                'Guest captured controller differs from reviewed canonical source')
        require(not relative.startswith('0110-') or b'\r' not in raw.read_bytes(),
                'New guest controller must be canonical LF')
    require(sha(root/'served-agent.private.ps1') == binding['guestAgentSha256'],
            'Served agent bytes differ from declared hash')
    require(not (root/'incomplete.private.json').exists(), 'Guest run is explicitly incomplete')
    require(load(root/'host-before.private.json') == load(root/'host-after.private.json')
            and bool(load(root/'host-before.private.json')['boot']), 'WSL host boot changed')
    windows = [load(root/('windows-host-'+stage+'.private.json')) for stage in ('before','after')]
    require(set(windows[0]) == set(windows[1]) == {'hostBootUtc','observedUtc'}
            and windows[0]['hostBootUtc'] == windows[1]['hostBootUtc']
            and datetime.datetime.fromisoformat(windows[0]['hostBootUtc']) <=
                datetime.datetime.fromisoformat(windows[0]['observedUtc']) <
                datetime.datetime.fromisoformat(windows[1]['observedUtc']),
            'Actual Windows host boot continuity is not established')
    overlay = load(root/'overlay-binding.private.json')
    require(load(root/'base-after.private.json') == overlay
            and all(len(overlay[key]) == 64 for key in ('diskSha256','varsSha256','manifestSha256')),
            'Preserved base disk/firmware/manifest changed')
    return binding


def guest_lifecycle(folder, before, after):
    request = before['request']
    phase = request['stopAt']
    require(request['case'] == before['case'] and request['mode'] == MODE
            and request['action'] == 'run' and phase in ('receipt-written','receipt-file-flushed'),
            'Wrong guest candidate request')
    raw = load(folder/'controller-events.private.json')
    require(raw and [entry['at'] for entry in raw] == sorted(entry['at'] for entry in raw)
            and all(entry['value'].get('id','').startswith(before['case']) for entry in raw),
            'Guest cell history is empty/reordered/unrelated')
    live = [entry for entry in raw if entry['value'].get('id') == request['id']]
    native = [entry['value']['event'] for entry in live if entry['path'] == '/event'
              and not entry['value']['event'].get('supervisorObservation')]
    contexts = event_contract(native)
    expected = PREFIX[:PREFIX.index(phase)+1]
    require([event['barrier'] for event in native if 'barrier' in event] == expected,
            'Guest candidate differs from required held-barrier prefix')
    controls = [entry for entry in live if entry['path'] == '/event'
                and 'supervisorControl' in entry['value']['event']]
    require([entry['value']['event']['supervisorControl']['barrier'] for entry in controls] == expected
            and [entry['value']['event']['supervisorControl']['control'] for entry in controls] ==
                ['continue']*(len(expected)-1)+['held']
            and len({entry['value']['event']['supervisorControl']['processId'] for entry in controls}) == 1
            and controls[0]['value']['event']['supervisorControl']['processId'] > 0
            and before['checkpoint'] == controls[-1], 'Guest did not retain exact owned child at boundary')
    require(not any(entry['path'] == '/result' for entry in live)
            and not any('outcome' in event for event in native), 'VM-off actor continued/completed')
    pre = [entry for entry in live if entry['path'] == '/event'
           and 'preProperties' in entry['value']['event']]
    require(len(pre) == 1 and pre[0]['value']['event']['preProperties'] == before['preProperties']
            and live.index(pre[0]) < live.index(controls[-1]), 'Missing exact pre-fault native observation')
    require(len(contexts) == (0 if phase == 'receipt-written' else 1)
            and before['receiptContext'] == (contexts[0][1] if contexts else None),
            'Guest receipt context is premature/invented/not actual')
    suffixes = ['native-post','rich-before'] + (['inspect'] if contexts else []) + ['rich-after','native-final']
    results = [entry for entry in raw if entry['path'] == '/result'
               and entry['value'].get('id') != before['case']+'-prepare']
    require([entry['value']['id'] for entry in results] == [before['case']+'-'+suffix for suffix in suffixes],
            'Guest has missing/repeated/reordered read-only results')
    values = ([after['postbootProperties'],after['inventoryBefore']] +
        ([after['inspect']] if contexts else []) + [after['inventoryAfter'],after['finalProperties']])
    require([entry['value'] for entry in results] == values, 'Saved guest captures differ from raw transport')
    prior = [event['callerContext'] for event in native if 'callerContext' in event][-1]
    return contexts[0][1] if contexts else None, prior, raw


def guest_audit(root, binary, observer, inspector, frozen, baseline):
    binding = guest_binding(root, binary, observer, inspector, frozen, baseline)
    expected = [('pre-context','receipt-written'),('first-checked-context','receipt-file-flushed')]
    summary = load(root/'summary.private.json')
    require(summary['caseCount'] == summary['vmOffs'] == 2 and summary['enabledProfiles'] == 0
            and summary['hostCachesAlive'] is True and all(summary.get(flag) is False for flag in FLAGS)
            and summary['cases'] == [{'id':name,'barrier':phase,'faultKind':'vm-off','retained':True}
                                    for name,phase in expected], 'Wrong two-cell VM-off schedule')
    transport = load(root/'transport-history.private.json')
    require(transport and [row['at'] for row in transport] == sorted(row['at'] for row in transport),
            'Full readiness/transport history is missing/reordered')
    rows, boots, instances = [], set(), []
    for name, phase in expected:
        folder = root/name
        before, after = load(folder/'before.private.json'), load(folder/'after.private.json')
        require(before['request']['stopAt'] == phase, 'Wrong guest cell boundary')
        old.terminal(before['prepare'], 'owned-source-prepared')
        left = old.hello(before['hello'], binding['guestAgentSha256'])
        right = old.hello(after['hello'], binding['guestAgentSha256'])
        require((right-left).total_seconds() > 5, 'Guest lacks a fresh VM-off boot')
        old.vm_exit(folder, left, right, boots)
        first_instance, first_ready = ready_proof(before['readiness'], binding, transport)
        second_instance, second_ready = ready_proof(after['readiness'], binding, transport)
        require(first_instance != second_instance and before['hello'] == before['readiness']['hello']
                and after['hello'] == after['readiness']['hello'], 'Readiness instance/hello not bound to each boot')
        if instances:
            require(instances[-1] == first_instance, 'Unexpected agent replacement between cells')
        instances += [first_instance,second_instance]
        context, prior, raw = guest_lifecycle(folder, before, after)
        require(all(item in transport for item in raw), 'Cell event absent from full transport history')
        prepare_events = [event for event in raw if event['value'].get('id') == before['case']+'-prepare']
        post_events = [event for event in raw if event['value'].get('id') == before['case']+'-native-post']
        require(prepare_events and first_ready < prepare_events[0]['at'] and post_events
                and before['checkpoint']['at'] < after['readiness']['readyEvent']['at']
                and second_ready < post_events[0]['at'], 'Measurement queued before active hash-bound readiness')
        timeline, within = [], []
        for stage, value in [('pre-fault',before['preProperties']),
            ('post-fault-first-native',after['postbootProperties']),('final-native',after['finalProperties'])]:
            require(value['observerSha256'] == OBSERVER and value['wrapperInventoryPerformed'] is False,
                    'Wrong observer or hidden generic inventory')
            observation, changes = old.properties(value)
            timeline.append((stage, observation))
            within += [{'stage':stage,**change} for change in changes]
        transitions = [{'from':left_label,'to':right_label,
            'changes':old.changed({n:x['after'] for n,x in left.items()},
                                  {n:x['before'] for n,x in right.items()})}
            for (left_label,left),(right_label,right) in zip(timeline,timeline[1:])]
        files, rich_changes = old.rich_pair(after['inventoryBefore'],after['inventoryAfter'])
        internal = old.rich_internal(after['inventoryBefore'],'rich-before-inspection')
        internal += old.rich_internal(after['inventoryAfter'],'rich-after-inspection')
        bound_prior_records(files,prior)
        old.bound_records(files,context) if context else None
        rich_native = old.rich_native(after['inventoryBefore'],timeline[1][1],timeline[2][1],'rich-before-inspection')
        rich_native += old.rich_native(after['inventoryAfter'],timeline[1][1],timeline[2][1],'rich-after-inspection')
        inspection = None
        context_diffs = []
        if context:
            bound = old.context_info(context)
            context_diffs = old.changed(bound,{n:x['before'] for n,x in timeline[0][1].items()})
            context_diffs = [row for row in context_diffs if row['object'] != '.' or
                             row['field'] in ('identity','attributes','creationTime')]
            require(not context_diffs, 'First emitted checked context was already stale before VM-off')
            require(after['inspectRequest'] == {'receiptContext':context}, 'Inspector received adopted/stale replacement context')
            inspection = old.terminal(after['inspect'])
            require(inspection['outcome'] in (SUCCESS,'receipt-inspection-refused')
                    and inspection['effectsAttempted'] is False and inspection['ownedHandlesRemoved'] == 0
                    and inspection['sourceRetained'] is inspection['rootRetained'] is True
                    and after['inspect']['wrapperInventoryPerformed'] is False,
                    'Inspector claimed effects or unexpected outcome')
        else:
            require(after['inspect'] is after['inspectRequest'] is None,
                    'Pre-context cell fabricated an inspector request')
        rows.append({'id':name,'barrier':phase,'contextExported':context is not None,
            'inspection':inspection['outcome'] if inspection else 'not-requested-no-context',
            'inspectionDiagnostic':inspection.get('diagnostic') if inspection else None,
            'nativeDifferences':transitions,'withinObserverDifferences':within,
            'richPropertyDifferences':rich_changes,'richMetadataContentDisagreements':internal,
            'richNativeTimeDisagreements':rich_native,'capturedBytesAndNamesUnchanged':True,
            'reportedSizeInventoriesUnchanged':not any(item['field']=='size' for item in rich_changes),
            'freshBoot':True,'exactReadyChallengeBeforeMeasurements':True,
            **dict.fromkeys(FLAGS,False)})
    shutdown = load(root/'normal-shutdown.private.json')
    require(shutdown == {'method':'ACPI system_powerdown; normal guest shutdown','vmOffFaultCount':2,
        'commandResponse':{},'exactOverlayProcessExitConfirmed':True,'hostActionAttempted':False,
        'retainedOverlay':True}, 'Normal final guest shutdown proof is incomplete')
    require(load(root/'helper-stop.private.json') == {'guestAlreadyNormallyStopped':True,
        'ownedPrivateTransportStopped':True,'ownedPrivateTpmDaemonStopped':True,
        'originalGuestHelpersTouched':False,'noScopedEmulatorOrTransportOrTpmProcessesRemain':True},
        'Scoped helpers did not stop after normal guest shutdown')
    require(len(boots)==2 and len(set(instances))==3, 'Wrong count of fresh boots/agent instances')
    return {'schemaVersion':1,'observedOn':'2026-10-16','data':'authored markers only',
        'caseCount':2,'vmOffs':2,'guestBuild':'26300','mode':MODE,
        'actorSha256':binding['actorSha256'],'observerSha256':OBSERVER,'inspectorSha256':F869,
        'nativeBaselineCaseCount':11,'cases':rows,'sameHostBoot':True,'hostCachesAlive':True,
        'normalGuestShutdownConfirmed':True,'scopedHelpersStopped':True,
        'operatorAssistedReadOnlyRetries':0,'enabledProfiles':0,
        'driftCauseEstablished':False,'timestampRebindingAllowed':False,
        'limits':'Finite checked-context marker observations. VM-off is QMP quit and may drain I/O; host caches remain alive. No cause/fix, durable acknowledgement/custody, complete profile, automatic repair or RAW admission.',
        **dict.fromkeys(FLAGS,False)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['native','guest'])
    for arg in ('root', 'binary', 'inspector', 'frozen', 'public'):
        parser.add_argument('--'+arg, type=Path, required=True)
    parser.add_argument('--observer', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if args.kind == 'native':
        result = native_audit(args.root.resolve(), args.binary.resolve(),
                              args.inspector.resolve(), args.frozen.resolve())
    else:
        if args.observer is None or args.baseline is None:
            parser.error('Guest audit requires --observer and --baseline')
        result = guest_audit(args.root.resolve(), args.binary.resolve(), args.observer.resolve(),
                            args.inspector.resolve(), args.frozen.resolve(), args.baseline.resolve())
    with args.public.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'caseCount': result['caseCount'], 'enabledProfiles': 0}))

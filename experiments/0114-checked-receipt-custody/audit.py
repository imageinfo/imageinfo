"""Independent retained-artifact audit of five checked-custody integrations.

Imports no runtime or collector and invokes no worker, setter or cleanup action.
The accepted #0110 parser/checker is reused only for read-only record validation.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
_spec = importlib.util.spec_from_file_location('checked114_prior_audit',
    HERE.parent/'0110-receipt-context/audit.py')
prior = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prior)
require, sha = prior.require, prior.sha
ACTOR = 'e378d436ed478cc4fe31ec84ff0ab91f27a459d8c6b636fcb55d0c700c11f941'
INSPECTOR = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
MODE = 'ordinary-receipt-checked-flush'
CASES = ['normal', 'terminate-pre-context', 'receipt-property-pre-context',
         'later-output-edit', 'stop-prune']
TOOLING = {
    'experiments/0114-checked-receipt-custody/runtime.py',
    'experiments/0114-checked-receipt-custody/qualify.py',
    'experiments/0114-checked-receipt-custody/audit.py',
    'experiments/0103-process-custody/runtime.py',
    'experiments/0049-cumulative-budget/supervisor.py',
    'experiments/0100-receipt-timestamps/native.py',
    'experiments/0033-owner-rights/actor.py',
    'experiments/0110-receipt-context/audit.py',
    'experiments/0106-receipt-properties/audit_final.py',
}
FLAGS = prior.FLAGS
MARKER = hashlib.sha256(b'3'*65536).hexdigest()
TRANSACTION = {'source.marker', 'candidate.marker', 'output.marker', 'prepared.record',
               'intent.record', 'observation.record', 'receipt.record'}


def load(path):
    path = Path(path)
    require(path.stat().st_size <= 4*1024*1024, 'Private evidence size bound')
    return prior.decode(path.read_text(encoding='utf-8-sig'))


def safe_status(status):
    require(type(status) is dict and all(status.get(flag) is False for flag in FLAGS),
            'Missing/unsafe runtime capability')
    require(status.get('automaticDurableCustody') is False, 'Automatic custody claim')
    require(status.get('actorSha256') == ACTOR and status.get('inspectorSha256') == INSPECTOR
            and status.get('receiptMode') == MODE, 'Runtime actor/mode provenance missing')
    require(status.get('chargedBytes') == 655360 and status.get('operationCount') == 1,
            'Runtime logical admission changed')
    for key, limit in [('custodySnapshots', 4), ('originalEventCount', 128),
                       ('checkedReceiptExports', 2), ('inspectionCount', 8)]:
        require(type(status.get(key)) is int and 0 <= status[key] <= limit,
                'Runtime count missing/unbounded')
    require(type(status.get('checkedReceiptContextEligible')) is bool, 'Eligibility is not a fact')


def inventory_contract(inventory):
    require(type(inventory) is dict and set(inventory) == {'transaction', 'custody'},
            'Unexpected inventory roots')
    for role, entries in inventory.items():
        allowed = TRANSACTION if role == 'transaction' else {f'custody-{n}.record' for n in range(1, 5)}
        require(type(entries) is dict and set(entries) <= allowed, 'Unexpected retained leaf')
        require(not {'candidate.marker', 'output.marker'} <= set(entries), 'Two accepted namespace leaves')
        for value in entries.values():
            require(set(value) == {'retainedBeforeReads', 'freshPath', 'retainedAfterReads',
                                   'sddl', 'sha256', 'bytes'}, 'Wrong native observation shape')
            prior.old.info(value['freshPath'])
            require(value['retainedBeforeReads'] == value['freshPath'] == value['retainedAfterReads'],
                    'Native identity/properties changed during independent read')
            require(type(value['bytes']) is int and 0 <= value['bytes'] <= 65536
                    and value['freshPath']['size'] == value['bytes'], 'Artifact logical-byte bound')
            require(type(value['sha256']) is str and len(value['sha256']) == 64
                    and all(c in '0123456789abcdef' for c in value['sha256']), 'Bad artifact digest')
            require(type(value['sddl']) is str and 0 < len(value['sddl']) <= 32768, 'Missing security observation')


def current_inventory(root, inventory):
    """Compare retained evidence to actual files without invoking the producer."""
    inventory_contract(inventory)
    for role, entries in inventory.items():
        folder = root/(role+'.marker')
        require(folder.exists() == bool(entries) or folder.is_dir(), 'Missing retained directory')
        if not folder.exists():
            require(not entries, 'Missing populated directory')
            continue
        require({path.name for path in folder.iterdir()} == set(entries), 'Actual retained namespace differs')
        for name, observed in entries.items():
            path = folder/name
            stat = path.stat()
            info = observed['freshPath']
            require(path.is_file() and not stat.st_file_attributes & 0x400, 'Foreign artifact kind')
            require(stat.st_size == observed['bytes'] and sha(path) == observed['sha256'],
                    'Actual retained artifact bytes differ')
            require(stat.st_ino == int(info['identity'].split(':')[1], 16)
                    and stat.st_nlink == info['links'] and stat.st_file_attributes == info['attributes']
                    and stat.st_mtime_ns//100 + 116444736000000000 == info['lastWriteTime'],
                    'Actual retained identity/properties differ')


def operation(cell, name):
    found = [item for item in cell['operations'] if item['label'] == name]
    require(len(found) == 1, 'Missing/duplicate caller operation: '+name)
    return found[0]


def refusal(cell, name):
    item = operation(cell, name)
    require(item['result']['error'] is not None and item['result']['returned'] is None,
            'Expected API refusal: '+name)
    require(item['eventStart'] == item['eventEnd'] and item['before'] == item['after'],
            'Refused API launched a worker or changed artifacts')


def checked_contract(events, complete):
    contexts = prior.event_contract(events)
    barriers = [event['barrier'] for event in events if 'barrier' in event]
    require(barriers == prior.PREFIX[:len(barriers)], 'Original worker barriers are not one exact prefix')
    terminals = [event for event in events if 'outcome' in event]
    if complete:
        require(barriers == prior.PREFIX and len(contexts) == 2 and len(terminals) == 1
                and events[-1] == terminals[0] and terminals[0]['outcome'] == prior.SUCCESS,
                'Terminal-only or incomplete checked success')
        require(all(terminals[0].get(key) is True for key in
                    ('receiptFileFlushSucceeded', 'receiptParentFlushSucceeded', 'finalCheckPassed')),
                'Missing final checked facts')
    else:
        require(not contexts, 'Failed/unreleased case obtained a receipt context')
        require(not any(event.get('outcome') == prior.SUCCESS for event in events),
                'Incomplete case reported receipt success')
    return [context for _, context in contexts]


def verify_custody(root, cell, original):
    contexts = [event['callerContext'] for event in original if 'callerContext' in event]
    saved = []
    names = {'captured-save': 'captured', 'stop-save': 'stop-confirmed-before-publication',
             'fence-save': 'publication-release-fenced', 'observed-save': 'publication-observed',
             'renewed-save': 'observation-renewed'}
    for ordinal, entry in enumerate(cell['events']):
        if entry['phase'] not in names or entry['event'].get('outcome') != 'custody-snapshot-recorded':
            continue
        journal = entry['event']['journal']
        require(journal['purpose'] == 'imageinfo-od11-custody-history-v1'
                and 1 <= len(journal['events']) <= 4, 'Wrong bounded custody history')
        if saved:
            require(journal['events'][:-1] == saved[-1][1]['events'], 'Custody history is not one whole prefix')
        require(journal['events'][-1]['event'] == names[entry['phase']], 'Save acknowledgement phase differs')
        for item in journal['events']:
            if 'context' in item:
                require(item['context'] in contexts, 'Saved context not emitted by actual owned child')
        number = len(journal['events'])
        snapshot = root/'custody.marker'/f'custody-{number}.record'
        require(snapshot.stat().st_size <= 65536 and load(snapshot) == journal,
                'Retained actual custody snapshot differs from acknowledgement')
        saved.append((ordinal, journal))
    expected = ['captured', 'stop-confirmed-before-publication'] if cell['id'] == 'stop-prune' else [
        'captured', 'publication-release-fenced', 'publication-observed', 'observation-renewed']
    require(len(saved) == len(expected) and [row[1]['events'][-1]['event'] for row in saved] == expected,
            'Wrong finite custody saves')
    lifecycle = [(i, e['event'].get('runtimeEvent')) for i, e in enumerate(cell['events']) if e['phase'] == 'runtime']
    notice = lambda name: [i for i, value in lifecycle if value == name]
    if cell['id'] != 'stop-prune':
        continued = notice('publication-continuation-sent')
        require(len(continued) == 1 and saved[1][0] < continued[0], 'Publication before completed release fence')
    else:
        exited = notice('owned-child-exit-confirmed-before-release')
        pruned = notice('prune-invocation-started')
        require(len(exited) == len(pruned) == 1 and exited[0] < saved[1][0] < pruned[0]
                and not notice('publication-continuation-sent'), 'Prune lacks actual stop/save order')
    return len(saved)


def verify_context_files(root, context, inventory, edited=False):
    bound = prior.old.context_info(context)
    entries = inventory['transaction']
    require(set(entries) == prior.NAMES, 'Receipt context has missing/extra retained artifacts')
    for name in entries:
        observed = entries[name]
        if edited and name == 'output.marker':
            require(observed['freshPath']['identity'] == bound[name]['identity']
                    and observed['sha256'] != MARKER and observed['bytes'] == 65536,
                    'Later edit is not an ordinary same-object bounded output edit')
        else:
            require(observed['freshPath'] == bound[name], 'Native artifact properties differ from actual context')
    files = {}
    for name in prior.NAMES:
        data = (root/'transaction.marker'/name).read_bytes()
        files[name] = {'sha256': hashlib.sha256(data).hexdigest(),
                       'recordBytesBase64': base64.b64encode(data).decode('ascii')}
    require(files['source.marker']['sha256'] == MARKER
            and files['receipt.record']['sha256'] == context['receipt']['sha256'], 'Context byte binding differs')
    if not edited:
        require(files['output.marker']['sha256'] == MARKER, 'Output marker changed')
    prior.bound_prior_records(files, context['prior'])


def audit_cell(parent, cell):
    name = cell['id']
    require(name in CASES and type(cell['events']) is list and len(cell['events']) <= 640,
            'Wrong case/event bound')
    root = parent/name/'runtime.marker'
    for entry in cell['events']:
        require(type(entry) is dict and set(entry) == {'phase', 'event'}, 'Unexpected event wrapper')
        if entry['phase'] == 'runtime':
            safe_status(entry['event'])
        else:
            prior.old.safe(entry['event'])
    original = [e['event'] for e in cell['events'] if e['phase'] == 'original']
    complete = name in ('normal', 'later-output-edit')
    contexts = checked_contract(original, complete)
    source = None
    observations = 0
    for item in cell['operations']:
        require(0 <= item['eventStart'] <= item['eventEnd'] <= len(cell['events']), 'Bad operation event interval')
        safe_status(item['status'])
        for inventory in (item['before'], item['after']):
            inventory_contract(inventory)
            current = inventory['transaction'].get('source.marker')
            if current is not None:
                require(current['bytes'] == 65536 and current['sha256'] == MARKER, 'Source marker bytes differ')
                if source is None:
                    source = current
                require(current == source, 'Source identity/properties/security changed')
                observations += 1
    require(source is not None and original, 'No actual source/child evidence')
    caller = next(e['callerContext'] for e in original if 'callerContext' in e)
    require(caller['source'] == source['freshPath'], 'Caller source binding differs from native observer')
    for status in (cell['statusBeforeClose'], cell['statusAfterClose']):
        safe_status(status)
    require(cell['ownedChildAfterClose'] is not None
            and type(cell['ownedChildAfterClose']['exitCode']) is int, 'Owned child exit unconfirmed')
    require(cell['statusAfterClose']['checkedReceiptContextEligible'] is False
            and cell['statusAfterClose']['state'] == 'closed-retained', 'Close left context eligible')
    require(cell['finalBeforeClose'] == cell['finalAfterClose'], 'Close changed retained artifacts')
    current_inventory(root, cell['finalAfterClose'])
    snapshots = verify_custody(root, cell, original)
    refusal(cell, 'inspect-after-close')
    if name == 'stop-prune':
        for label in ('inspect-before-release', 'prune-again', 'inspect-after-prune'):
            refusal(cell, label)
        terminal = operation(cell, 'prune')['result']['returned']
        require(terminal and terminal['outcome'] == 'owned-unpublished-handles-pruned'
                and terminal['ownedHandlesRemoved'] == 3, 'Exact unpublished prune not observed')
        require(set(cell['finalBeforeClose']['transaction']) == {'source.marker'}, 'Prune removed wrong names')
        require(operation(cell, 'stop')['ownedChild']['exitCode'] is not None, 'Stop did not confirm exact child exit')
    else:
        refusal(cell, 'prune-after-release')
        require(set(cell['finalBeforeClose']['transaction']) == prior.NAMES,
                'Postpublication artifacts not retained')
        require(operation(cell, 'release')['ownedChild']['exitCode'] is not None,
                'Released/failing child exit unconfirmed')
    inspect_events = [e['event'] for e in cell['events'] if e['phase'] == 'receipt-inspect']
    inspection = operation(cell, 'inspect') if name != 'stop-prune' else None
    if complete:
        released = operation(cell, 'release')
        require(released['result']['error'] is None and released['ownedChild']['exitCode'] == 0
                and released['status']['checkedReceiptContextEligible'] is True,
                'Checked release not completed under actual child custody')
        require(len([e for e in inspect_events if 'outcome' in e]) == 1,
                'Missing/duplicate actual inspection terminal')
        require(inspection['before'] == inspection['after'], 'Read-only inspector changed artifacts')
        terminal = inspect_events[-1]
        expected = prior.SUCCESS if name == 'normal' else 'receipt-inspection-refused'
        require(terminal['outcome'] == expected and terminal['ownedHandlesRemoved'] == 0,
                'Wrong actual fresh inspector outcome')
        verify_context_files(root, contexts[0], cell['finalBeforeClose'], edited=name != 'normal')
    elif name != 'stop-prune':
        require(operation(cell, 'release')['result']['error'] is not None
                and not inspect_events and not cell['statusBeforeClose']['checkedReceiptContextEligible'],
                'Failed context boundary gained inspection eligibility')
        refusal(cell, 'inspect')
    controls = cell['controls']
    exceptional = [item for item in controls if item['choice'] != 'continue']
    require(cell['callerInterruptionApplied'] is (name == 'terminate-pre-context'), 'Wrong interruption provenance')
    require(len(exceptional) == int(name == 'terminate-pre-context')
            and all(item['choice'] == 'caller-exception-kill-wait' and item['phase'] == 'original'
                    and item['barrier'] == 'receipt-written' for item in exceptional), 'Unlabelled protocol fault')
    if name == 'terminate-pre-context':
        require(operation(cell, 'release')['result']['error']['type'] == 'QualificationStop'
                and original[-1].get('barrier') == 'receipt-written'
                and operation(cell, 'release')['ownedChild']['exitCode'] != 0,
                'Actual pre-context owned-process termination not observed')
    if name == 'receipt-property-pre-context':
        require(len(cell['actors']) == 1, 'Missing property actor')
        actor = cell['actors'][0]
        require(actor['action'] == 'receipt-last-write'
                and actor['before']['freshPath']['identity'] == actor['after']['freshPath']['identity']
                and actor['before']['freshPath']['lastWriteTime'] != actor['after']['freshPath']['lastWriteTime']
                and actor['before']['sha256'] == actor['after']['sha256'], 'Native property conflict not observed')
    if name == 'later-output-edit':
        require(len(cell['actors']) == 1 and cell['actors'][0]['action'] == 'ordinary-owner-output-edit',
                'Missing ordinary-owner edit')
        actor = cell['actors'][0]
        require(actor['before']['sha256'] == MARKER and actor['after']['sha256'] != MARKER
                and actor['before']['freshPath']['identity'] == actor['after']['freshPath']['identity'],
                'Later actor did not edit the same output object')
    if name == 'normal':
        for label in ('inspect-before-begin', 'existing-root'):
            refusal(cell, label)
        require([item['label'] for item in cell['admissionRefusals']] == [
            'wrong-actor', 'wrong-inspector', 'below-budget'], 'Missing pre-effect admission checks')
        require(all(item['error'] and item['rootExists'] is False for item in cell['admissionRefusals']),
                'Unsupported admission created a root')
        require(not any((parent/name/(item['label']+'.marker')).exists() for item in cell['admissionRefusals']),
                'Unsupported admission left target artifacts')
    elif cell['admissionRefusals']:
        raise ValueError('Unexpected admission trial')
    return {'id': name, 'originalNativeEvents': len(original), 'checkedContextExports': len(contexts),
            'custodySnapshots': snapshots, 'sourceObservationsUnchanged': observations,
            'inspectorInvocations': int(bool(inspect_events)),
            'inspectionOutcome': inspect_events[-1]['outcome'] if inspect_events else None,
            'ownedHandlesRemoved': 3 if name == 'stop-prune' else 0,
            'callerExceptionTerminatedOwnedChild': name == 'terminate-pre-context',
            'nativePropertyConflict': name == 'receipt-property-pre-context',
            'ordinaryOwnerEditConflict': name == 'later-output-edit',
            'postCloseArtifactsRetained': True}


def audit(root):
    root = Path(root)
    require(not (root/'failed.private.json').exists(), 'Run explicitly failed/incomplete')
    binding = load(root/'bindings.private.json')
    require(binding['schema'] == 'imageinfo-checked-custody-qualification-v1'
            and binding['actorSha256'] == ACTOR and binding['inspectorSha256'] == INSPECTOR
            and binding['mode'] == MODE and binding['schedule'] == CASES, 'Wrong fixed binding')
    require(set(binding['tooling']) == TOOLING, 'Missing/unexpected executed tooling binding')
    require(sha(binding['actorPath']) == ACTOR and sha(binding['inspectorPath']) == INSPECTOR,
            'Actual actor/inspector bytes differ')
    for relative, expected in binding['tooling'].items():
        captured = root/'tooling.private'/relative
        require(sha(captured) == expected == sha(REPO/relative), 'Executed tooling changed after freeze')
        if relative.startswith('experiments/0114-'):
            require(b'\r' not in captured.read_bytes(), 'New execution tooling must be canonical LF')
    require(load(root/'complete.private.json') == {'cases': CASES, 'after': {
        'actorSha256': ACTOR, 'inspectorSha256': INSPECTOR, 'tooling': binding['tooling']}},
        'Missing completion/source closure')
    rows = [audit_cell(root, load(root/(name+'.private.json'))) for name in CASES]
    require([row['id'] for row in rows] == CASES, 'Duplicate/reordered case identities')
    return {'schemaVersion': 1, 'observedOn': '2026-10-16', 'data': 'authored markers only',
            'caseCount': len(rows), 'actorSha256': ACTOR, 'inspectorSha256': INSPECTOR,
            'mode': MODE, 'host': binding['host'], 'tooling': binding['tooling'], 'cases': rows,
            'claim': 'process-local checked provenance and read-only inspection integration',
            'nativeStorageErrors': False, 'vmFaults': 0, 'automaticDurableCustody': False,
            'enabledProfiles': 0, **dict.fromkeys(FLAGS, False)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--public', type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    if args.public:
        args.public.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'caseCount': result['caseCount'], 'independentAudit': 'passed'}))

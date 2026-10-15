"""Independent reconciliation of actual process-owned custody qualification."""
import argparse
import hashlib
import json
from pathlib import Path

WORKER = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
MARKER = hashlib.sha256(b'3' * 65536).hexdigest()
FLAGS = ['committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed']
CASES = ['stop-prune', 'captured-no-authority', 'released-no-prune', 'original-failure',
         'captured-save-failure', 'stop-save-failure', 'fence-save-failure', 'foreign-extra',
         'candidate-substitution', 'partial-prune', 'existing-root', 'below-budget']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def operation(cell, label):
    found = [item for item in cell['operations'] if item['label'] == label]
    require(len(found) == 1, 'Missing or duplicate operation')
    return found[0]


def no_events_on_refusal(cell, label):
    item = operation(cell, label)
    require(item['result']['error'] is not None, 'API refusal required')
    require(item['eventStart'] == item['eventEnd'], 'Refused API launched or controlled a worker')
    require(item['before'] == item['after'], 'Refused API changed artifacts')


def lifecycle(entry):
    if entry['phase'] != 'runtime':
        return None
    return entry['event'].get('runtimeEvent')


def audit(root):
    root = Path(root)
    bindings = load(root / 'bindings.private.json')
    require(bindings['workerSha256'] == WORKER and bindings['schedule'] == CASES, 'Wrong fixed profile')
    require(load(root / 'complete.private.json') == {'cases': 12, 'workerUnchanged': True}, 'Incomplete run')
    repo = Path(__file__).resolve().parents[2]
    for name, expected in bindings['tooling'].items():
        require(sha(repo / name) == expected, 'Qualification/implementation source changed')
    rows = []
    for name in CASES:
        cell = load(root / f'{name}.private.json')
        require(cell['id'] == name, 'Case identity mismatch')
        events = cell['events']
        if name == 'below-budget':
            require(cell['constructorError'] is not None and cell['runtimeRootExists'] is False
                    and not events and not cell['controls'] and not cell['operations'],
                    'Below-budget construction had effects')
            rows.append({'id': name, 'constructorRefused': True, 'runtimeRootCreated': False,
                         'nativeWorkerEventCount': 0, 'sourceUnchanged': None,
                         'ownedHandlesRemoved': 0, 'protocolInjectedFailures': 0})
            continue
        for entry in events:
            if entry['phase'] != 'runtime':
                require(all(entry['event'].get(flag) is False for flag in FLAGS), 'Unsafe native flag')
        statuses = [item['status'] for item in cell['operations']] + [cell['statusBeforeClose']]
        require(all(status.get(flag) is False for status in statuses for flag in FLAGS), 'Unsafe runtime flag')
        require(all(status['automaticDurableCustody'] is False for status in statuses), 'Automatic custody claim')
        source = None
        source_observations = 0
        for item in cell['operations']:
            for inventory in [item['before'], item['after']]:
                current = inventory['transaction'].get('source.marker')
                if current:
                    require(current['bytes'] == 65536 and current['sha256'] == MARKER, 'Source bytes changed')
                    if source is None:
                        source = current
                    require(current == source, 'Source identity/properties changed')
                    source_observations += 1
        require(name == 'below-budget' or source is not None, 'Missing actual source observation')
        for item in cell['operations']:
            require(0 <= item['eventStart'] <= item['eventEnd'] <= len(events), 'Invalid event interval')
        native_prune = [entry['event'] for entry in events if entry['phase'] == 'prune']
        prune_terminal = next((event for event in reversed(native_prune) if 'outcome' in event), None)
        lifecycle_names = [lifecycle(entry) for entry in events if entry['phase'] == 'runtime']
        original_contexts = [entry['event']['callerContext'] for entry in events
                             if entry['phase'] == 'original' and 'callerContext' in entry['event']]
        saved_journals = []
        for phase in ['captured-save', 'stop-save', 'fence-save', 'observed-save', 'renewed-save']:
            saved = [entry['event'] for entry in events if entry['phase'] == phase
                     and entry['event'].get('outcome') == 'custody-snapshot-recorded']
            require(len(saved) <= 1, 'Repeated custody construction phase')
            for terminal_save in saved:
                journal = terminal_save['journal']
                require(journal['purpose'] == 'imageinfo-od11-custody-history-v1', 'Wrong custody journal')
                for history_event in journal['events']:
                    if 'context' in history_event:
                        require(history_event['context'] in original_contexts,
                                'Saved history adopted a context not actually emitted by owned child')
                require(journal['events'][0]['event'] == 'captured'
                        and journal['events'][0]['context']['stage'] == 'before-publication'
                        and journal['events'][0]['context']['stoppedBeforePublication'] is False,
                        'Wrong initial actual caller context')
                saved_journals.append(journal)
                snapshot_number = len(journal['events'])
                snapshot_path = root / name / 'runtime.marker/custody.marker' / f'custody-{snapshot_number}.record'
                require(snapshot_path.stat().st_size <= 65536 and load(snapshot_path) == journal,
                        'Actual saved snapshot does not match native acknowledgement')
        if source and original_contexts:
            require(original_contexts[0]['source'] == source['freshPath'],
                    'Actual caller source binding differs from independent object observation')
        injected = [item for item in cell['controls'] if item['choice'] != 'continue']
        require(all(item['choice'] == 'fail' for item in injected), 'Unlabelled control action')
        intended_fault = name in ['original-failure', 'captured-save-failure', 'stop-save-failure',
                                  'fence-save-failure', 'partial-prune']
        require(len(injected) == int(intended_fault) and cell['injectionApplied'] is intended_fault,
                'Fault provenance mismatch')
        if name == 'stop-prune':
            require(prune_terminal and prune_terminal['outcome'] == 'owned-unpublished-handles-pruned'
                    and prune_terminal['ownedHandlesRemoved'] == 3, 'Expected exact owned prune')
            require(set(cell['finalBeforeClose']['transaction']) == {'source.marker'}, 'Prune removed wrong names')
            require(operation(cell, 'stop')['status']['ownedChildExited'] is True, 'Exact owned child not stopped')
            no_events_on_refusal(cell, 'second-prune-denied')
        elif name == 'captured-no-authority':
            no_events_on_refusal(cell, 'prune-denied-live-child')
            no_events_on_refusal(cell, 'arbitrary-context-keyword-denied')
            require(operation(cell, 'begin')['status']['ownedChildExited'] is False, 'Child not live at capture')
        elif name == 'released-no-prune':
            no_events_on_refusal(cell, 'prune-denied-after-release-attempt')
            status = operation(cell, 'release')['status']
            require(status['releaseAttempted'] and status['publicationReleasePossible']
                    and status['releaseContinuationSent'], 'Release state missing')
            require('output.marker' in cell['finalBeforeClose']['transaction'], 'No actual publication observation')
        elif name in ['original-failure', 'captured-save-failure', 'below-budget']:
            require(operation(cell, 'begin')['result']['error'] is not None, 'Expected failed begin')
            no_events_on_refusal(cell, 'prune-denied-after-begin-failure')
            if name == 'below-budget':
                require(not events and not source and not cell['finalBeforeClose']['transaction']
                        and not cell['finalBeforeClose']['custody'], 'Below-budget run had effects')
        elif name in ['stop-save-failure', 'fence-save-failure']:
            method = 'stop' if name == 'stop-save-failure' else 'release'
            require(operation(cell, method)['result']['error'] is not None, 'Expected incomplete save failure')
            if name == 'fence-save-failure':
                no_events_on_refusal(cell, 'prune-denied-after-release-attempt')
                require(not operation(cell, 'release')['status']['releaseContinuationSent'], 'Released after failed fence')
            else:
                no_events_on_refusal(cell, 'prune')
        elif name in ['foreign-extra', 'candidate-substitution']:
            require(prune_terminal and prune_terminal['ownedHandlesRemoved'] == 0
                    and prune_terminal['effectsAttempted'] is False, 'Unsafe adversarial prune')
            require(operation(cell, 'prune')['before'] == operation(cell, 'prune')['after'], 'Refusal changed inventory')
            if name == 'foreign-extra':
                require('foreign.marker' in cell['finalBeforeClose']['transaction'], 'Foreign extra removed')
            else:
                actor = cell['actors'][0]
                require(actor['before']['sha256'] == actor['replacement']['sha256'] == MARKER,
                        'Not a same-byte substitution')
                require(actor['before']['freshPath']['identity'] != actor['replacement']['freshPath']['identity'],
                        'Substitution did not change object')
        elif name == 'partial-prune':
            require(prune_terminal and prune_terminal['ownedHandlesRemoved'] == 1
                    and prune_terminal['cleanupPending'] is True, 'Partial prune not actually observed')
            no_events_on_refusal(cell, 'second-prune-denied')
        elif name == 'existing-root':
            no_events_on_refusal(cell, 'existing-root-recreation-denied')
            no_events_on_refusal(cell, 'prune-denied-original-still-live')
        if name not in ['released-no-prune']:
            require(not any(entry['phase'] == 'original' and entry['event'].get('barrier') == 'published'
                            for entry in events), 'Unexpected original publication')
        if native_prune:
            names = ['captured-save-complete', 'owned-child-exit-confirmed-before-release',
                     'stop-save-complete', 'prune-invocation-started']
            require(all(value in lifecycle_names for value in names), 'Missing actual custody lifecycle proof')
            require([lifecycle_names.index(value) for value in names]
                    == sorted(lifecycle_names.index(value) for value in names), 'Custody lifecycle order wrong')
            require(not any(operation_status['publicationReleasePossible'] for operation_status in statuses),
                    'Prune after possible release')
            require(any([item['event'] for item in journal['events']]
                        == ['captured', 'stop-confirmed-before-publication'] for journal in saved_journals),
                    'No actual complete stop snapshot before prune')
        if name == 'released-no-prune':
            require('fence-save-complete' in lifecycle_names and 'publication-continuation-sent' in lifecycle_names
                    and lifecycle_names.index('fence-save-complete') < lifecycle_names.index('publication-continuation-sent'),
                    'Release preceded complete fence save')
        rows.append({'id': name, 'sourceObservationsChecked': source_observations,
                     'sourceUnchanged': source is not None if name != 'below-budget' else None,
                     'nativeWorkerEventCount': sum(entry['phase'] != 'runtime' for entry in events),
                     'runtimeLifecycle': lifecycle_names, 'protocolInjectedFailures': len(injected),
                     'pruneOutcome': prune_terminal['outcome'] if prune_terminal else None,
                     'ownedHandlesRemoved': prune_terminal['ownedHandlesRemoved'] if prune_terminal else 0,
                     'retainedTransactionLeaves': sorted(cell['finalBeforeClose']['transaction']),
                     'retainedCustodyLeaves': sorted(cell['finalBeforeClose']['custody']),
                     'finalStatus': cell['statusBeforeClose'],
                     'operationOutcomes': [{'label': item['label'], 'refusedOrFailed': item['result']['error'] is not None}
                                           for item in cell['operations']]})
    return {'schemaVersion': 1, 'ticket': 103, 'observationDate': '2026-10-15',
            'scope': 'process-local live caller custody, authored markers only',
            'workerSha256': WORKER, 'sourceRevision': bindings['sourceRevision'],
            'host': bindings['host'], 'tooling': bindings['tooling'], 'cases': rows,
            'limitations': ['no supervisor reload or arbitrary JSON authority', 'no OS restart authority',
                            'no automatic durable custody', 'logical bytes are not a physical quota',
                            'no production profile or independent format admission'],
            **{flag: False for flag in FLAGS}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.root)
    with args.output.open('xb') as stream:
        stream.write((json.dumps(value, indent=2) + '\n').encode())
    print('Independently audited twelve actual process-owned custody cases')


if __name__ == '__main__':
    main()

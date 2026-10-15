"""Reconcile actual native marker observations, retaining timestamp differences."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

WORKER = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
MARKER = hashlib.sha256(b'3' * 65536).hexdigest()
FLAGS = ['committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def invariant(value):
    result = copy.deepcopy(value)
    for field in ['retainedBeforeReads', 'freshPath', 'retainedAfterReads']:
        result[field].pop('lastWriteTime')
    return result


def observation(value):
    require(value['bytes'] <= 65536 and value['bytes'] > 0, 'Bounded observed bytes required')
    first = value['retainedBeforeReads']
    require(first['identity'] == value['freshPath']['identity']
            == value['retainedAfterReads']['identity'], 'Handle/path identity disagreement')
    require(first['size'] == value['bytes'] == value['freshPath']['size']
            == value['retainedAfterReads']['size'], 'Observed size disagreement')
    require(first['links'] == 1, 'Unexpected file links')
    return {'freshPathMinusRetainedBeforeTicks': value['freshPath']['lastWriteTime'] - first['lastWriteTime'],
            'retainedAfterReadsMinusBeforeTicks': value['retainedAfterReads']['lastWriteTime'] - first['lastWriteTime']}


def terminal(result):
    require(all(event.get(flag) is False for event in result['events'] for flag in FLAGS), 'Unsafe worker flag')
    require(set(result['controls']) <= {'continue'}, 'Unexpected control or protocol injection')
    return next((event for event in reversed(result['events']) if 'outcome' in event), None)


def inventory_pair(before, after):
    require(set(before) == set(after), 'Inspection changed namespace')
    drifts = []
    for name in before:
        observation(before[name])
        observation(after[name])
        require(invariant(before[name]) == invariant(after[name]), 'Inspection changed non-mtime invariant')
        delta = after[name]['retainedBeforeReads']['lastWriteTime'] - before[name]['retainedBeforeReads']['lastWriteTime']
        if delta:
            drifts.append({'name': name, 'deltaTicks': delta})
    return drifts


def audit(root):
    root = Path(root)
    bindings = load(root / 'bindings.private.json')
    require(bindings['workerSha256'] == WORKER, 'Wrong frozen worker')
    require(bindings['sourceRevision'] == 'b819f54533c495b332c3d4dbb0caccef49923036', 'Wrong frozen source')
    require(bindings['observer']['access'] == 0x80020000 and bindings['observer']['sharing'] == 7
            and bindings['observer']['creation'] == 3 and bindings['observer']['flags'] == 0x00200000,
            'Unexpected observer contract')
    repo = Path(__file__).resolve().parents[2]
    for path, expected in bindings['tooling'].items():
        require(sha(repo / path) == expected, 'Qualification tooling changed')
    require(load(root / 'complete.private.json') == {'cells': 12, 'workerUnchanged': True}, 'Incomplete schedule')
    cells = load(root / 'cells.private.json')
    require(len(cells) == 12, 'Incomplete cell evidence')
    rows = []
    expected_schedule = [('frozen-worker', phase, completion)
                         for phase in ['receipt-written', 'receipt-file-flushed', 'final-checked']
                         for completion in ['continue', 'terminate']]
    expected_schedule += [('authored-actor', write_through, boundary)
                          for write_through in [False, True] for boundary in ['write', 'flush', 'close']]
    for index, cell in enumerate(cells):
        views = cell['observations']
        read_deltas = [{'stage': value['stage'], **observation(value['value'])} for value in views]
        first = views[0]['value']
        require(all(invariant(item['value']) == invariant(first) for item in views),
                'Non-mtime lifecycle invariant changed')
        if cell['kind'] == 'frozen-worker':
            key = (cell['kind'], cell['phase'], cell['completion'])
            require(expected_schedule[index] == key, 'Wrong cell order')
            require(terminal(cell['prepare'])['outcome'] == 'owned-source-prepared', 'Prepare failed')
            end = terminal(cell['worker'])
            contexts = [event['receiptContext'] for event in cell['worker']['events'] if 'receiptContext' in event]
            require(cell['phaseContext'] in contexts and cell['latestContext'] == contexts[-1],
                    'Context was not actually emitted by worker')
            require(first['retainedBeforeReads'] == cell['phaseContext']['receipt']['info'],
                    'Live context/observer metadata disagreement')
            require(first['sha256'] == cell['phaseContext']['receipt']['sha256'], 'Live context bytes disagree')
            if cell['completion'] == 'continue':
                require(cell['worker']['exitCode'] == 0 and end is not None
                        and end['outcome'] == 'observed-receipt-recovery-required'
                        and end['ownedHandlesRemoved'] == 0, 'Unexpected normal worker terminal')
            else:
                require(cell['worker']['exitCode'] != 0 and end is None, 'Process was not terminated at barrier')
            inspections = []
            require(len(cell['inspections']) == 2, 'Both actual context inspections required')
            for inspection in cell['inspections']:
                inspected = terminal(inspection['result'])
                require(inspection['result']['exitCode'] == 0 and inspected is not None
                        and inspected['effectsAttempted'] is False and inspected['ownedHandlesRemoved'] == 0,
                        'Inspector attempted mutation')
                require(inspection['actualEmittedContext'] in contexts, 'Fabricated inspector context')
                drifts = inventory_pair(inspection['before'], inspection['after'])
                require(set(inspection['after']) == {'source.marker', 'output.marker', 'prepared.record',
                        'intent.record', 'observation.record', 'receipt.record'}, 'Unexpected retained namespace')
                for name in ['source.marker', 'output.marker']:
                    require(inspection['after'][name]['sha256'] == MARKER
                            and inspection['after'][name]['bytes'] == 65536, 'Source/output bytes changed')
                inspections.append({'contextKind': inspection['contextKind'], 'outcome': inspected['outcome'],
                                    'diagnostic': inspected.get('diagnostic'), 'mtimeObservationDrifts': drifts,
                                    'nonMtimeInventoryUnchanged': True})
            delta = views[1]['value']['retainedBeforeReads']['lastWriteTime'] - first['retainedBeforeReads']['lastWriteTime']
            rows.append({'kind': cell['kind'], 'phase': cell['phase'], 'completion': cell['completion'],
                         'afterExitMinusBarrierMtimeTicks': delta, 'readObservationDeltas': read_deltas,
                         'inspections': inspections, 'nonMtimeLifecycleInvariantsUnchanged': True})
        else:
            require(expected_schedule[index] == (cell['kind'], cell['writeThrough'], cell['bindingBoundary']),
                    'Wrong actor cell order')
            require(cell['namespace'] == ['authored.marker'] and first['sha256'] == MARKER
                    and first['bytes'] == 65536, 'Unexpected authored marker bytes/namespace')
            post = cell['freshPostCloseBinding']
            repeated = cell['repeatedPostCloseObservation']
            observation(post)
            observation(repeated)
            require(invariant(post) == invariant(first) == invariant(repeated), 'Post-close invariant changed')
            rows.append({'kind': cell['kind'], 'writeThrough': cell['writeThrough'],
                         'bindingBoundary': cell['bindingBoundary'],
                         'postCloseMinusPhaseBindingMtimeTicks': post['retainedBeforeReads']['lastWriteTime']
                            - cell['phaseBinding']['retainedBeforeReads']['lastWriteTime'],
                         'freshPostCloseRepeatedMtimeDeltaTicks': repeated['retainedBeforeReads']['lastWriteTime']
                            - post['retainedBeforeReads']['lastWriteTime'],
                         'readObservationDeltas': read_deltas,
                         'nonMtimeLifecycleInvariantsUnchanged': True})
    return {'schemaVersion': 1, 'observationDate': '2026-10-15', 'ticket': 100,
            'scope': 'native marker timestamp lifecycle only', 'workerSha256': WORKER,
            'sourceRevision': bindings['sourceRevision'], 'host': bindings['host'],
            'tooling': bindings['tooling'], 'observer': bindings['observer'],
            'tickUnit': '100 nanoseconds FILETIME; differences only', 'cells': rows,
            'workerMtimeDriftCells': sum(row.get('afterExitMinusBarrierMtimeTicks', 0) != 0 for row in rows),
            'actorPreCloseBindingDriftCells': sum(row.get('postCloseMinusPhaseBindingMtimeTicks', 0) != 0 for row in rows),
            'postCloseRepeatedDriftCells': sum(row.get('freshPostCloseRepeatedMtimeDeltaTicks', 0) != 0 for row in rows),
            'unqualified': ['historical #0047 crash timestamp cause', 'OS crash/restart', 'physical power loss',
                            'storage persistence', 'qualified namespace acknowledgement', 'full profile', 'RAW admission'],
            **{flag: False for flag in FLAGS}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    with args.output.open('xb') as stream:
        stream.write((json.dumps(result, indent=2) + '\n').encode())
    print('Audited twelve actual native lifecycle cells; no crash causality inferred')


if __name__ == '__main__':
    main()

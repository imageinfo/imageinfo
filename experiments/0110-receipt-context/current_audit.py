"""Audit eleven current-worker/current-inspector CI regression cells.

This is separate from the frozen F869-inspector qualification. It imports the
unchanged core's pure checks, never changes its constants and runs no worker.
"""
import argparse
import json
from pathlib import Path

import audit as core


def run(root, binary, source_root):
    core.source_binding(root,binary,source_root)
    report = core.load(root/'report.private.json')
    digest = core.sha(binary)
    core.require(report['caseCount'] == 11 and report['mode'] == core.MODE
        and report['workerSha256'] == report['inspectorSha256'] == digest
        and report['enabledProfiles'] == 0
        and all(report.get(flag) is False for flag in core.FLAGS), 'Wrong current regression binding')
    rows = report['cases']
    core.require(len(rows) == 11 and len({row['id'] for row in rows}) == 11
        and {row['id'] for row in rows} == set(core.MATRIX)|{'unchanged-inspector-stale-refusal'},
        'Wrong current eleven-cell set')
    for row in rows:
        name = row['id']
        folder = root/name
        core.require(row == core.load(folder/'case.private.json'), 'Current case row differs from capture')
        inventories = core.load(folder/'inventories.private.json')
        if name == 'unchanged-inspector-stale-refusal':
            events = core.native_events(folder/'inspect')
            ending = events[-1]
            argv = core.load(folder/'inspect/argv.private.json')
            core.require(Path(argv[0]).resolve() == binary and argv[2] == 'ordinary-receipt-inspect'
                and Path(argv[1]).resolve() == (root/'later-stale-context/transaction.marker').resolve()
                and row['inspectorSha256'] == digest and row['terminal'] == ending
                and row['exitCode'] == core.load(folder/'inspect/exit.json')['exitCode'] == 0
                and ending['outcome'] == 'receipt-inspection-refused'
                and ending['diagnostic'] == 'FILE_PROPERTIES_CHANGED'
                and ending['effectsAttempted'] is False and ending['ownedHandlesRemoved'] == 0
                and inventories['before'] == inventories['after'] ==
                    core.file_inventory(root/'later-stale-context/transaction.marker'),
                'Current inspector did not retain/refuse the stale original context')
            core.require(core.load(folder/'inspect-input.private.json') ==
                core.load(root/'later-stale-context/context.private.json'), 'Current inspector adopted replacement context')
            continue
        stop,action,phase,role = core.MATRIX[name]
        events = core.native_events(folder/'worker')
        contexts = core.event_contract(events)
        bad = bool(stop) or action in ('mtime','ads')
        barriers = [event['barrier'] for event in events if 'barrier' in event]
        core.require(barriers == (core.PREFIX[:core.PREFIX.index(phase)+1] if bad else core.PREFIX),
            'Current actor barrier sequence differs')
        expected = 1 if name == 'later-stale-context' else 0 if bad else 2
        core.require(len(contexts) == row['contextCount'] == expected
            and row['contextOrdinals'] == [ordinal for ordinal,_ in contexts]
            and row['mode'] == core.MODE and row['phase'] == phase and row['stop'] == stop,
            'Current context count/order differs')
        controls = ['continue']*(len(barriers)-(1 if stop else 0))
        if stop in ('cancel','fail'):
            controls.append(stop)
        core.require(core.load(folder/'worker/controls.json') == controls, 'Current controls differ')
        argv = core.load(folder/'worker/argv.private.json')
        core.require(Path(argv[0]).resolve() == binary and argv[2] == core.MODE
            and Path(argv[1]).resolve() == (folder/'transaction.marker').resolve(), 'Wrong current worker command')
        endings = [event for event in events if 'outcome' in event]
        code = core.load(folder/'worker/exit.json')['exitCode']
        core.require(code == row['exitCode'], 'Current exit capture differs')
        if stop == 'kill':
            core.require(code != 0 and not endings and row['terminal'] is None, 'Current terminated actor completed')
        else:
            core.require(code == 0 and endings == [row['terminal']]
                and endings[0]['outcome'] == ('recovery-required' if bad else core.SUCCESS)
                and endings[0]['ownedHandlesRemoved'] == 0
                and endings[0]['sourceRetained'] is endings[0]['rootRetained'] is True
                and endings[0]['receiptFileFlushSucceeded'] is (expected > 0),
                'Current terminal/effects differ')
        core.require(len(row['actors']) == (1 if action else 0), 'Current actor count differs')
        for actor in row['actors']:
            core.require(actor['action'] == action and actor['role'] == role
                and actor['allowed'] is (action not in ('write','rename'))
                and events[actor['eventOrdinal']].get('barrier') == phase, 'Current actor guard outcome differs')
        after = inventories['after']
        core.require(set(inventories['before']) == {'source.marker'}
            and set(after) == core.NAMES|({'receipt.record:probe'} if action == 'ads' else set())
            and after == core.file_inventory(folder/'transaction.marker'), 'Current retained artifact inventory differs')
        for leaf in ('source.marker','output.marker'):
            core.require(after[leaf]['sha256'] == core.old.MARKER and after[leaf]['size'] == 65536,
                'Current source/output bytes differ')
        source_before,source_after = dict(inventories['before']['source.marker']),dict(after['source.marker'])
        if role == 'source.marker' and action == 'mtime':
            core.require(source_before.pop('mtime') != source_after.pop('mtime'), 'Current source actor had no effect')
        core.require(source_before == source_after, 'Current source changed beyond its declared actor')
        prior = [event['callerContext'] for event in events if 'callerContext' in event][-1]
        files = core.native_record_files(folder/'transaction.marker')
        core.bound_prior_records(files,prior)
        if contexts:
            context = contexts[0][1]
            core.require(core.load(folder/'context.private.json') == context, 'Current saved context differs')
            core.compare_native_context(context,after,stale=name=='later-stale-context')
            core.old.bound_records(files,context)
        else:
            core.require(not (folder/'context.private.json').exists(), 'Current preflush context was invented')
    return {'schemaVersion':1,'evidenceKind':'current-worker-current-inspector-ci-regression',
        'caseCount':11,'workerSha256':digest,'inspectorSha256':digest,
        'frozenF869Qualification':False,'guestInterruptionRuns':0,'enabledProfiles':0,
        **dict.fromkeys(core.FLAGS,False)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('root','binary','public'):
        parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--source-root',type=Path,default=core.REPO)
    args = parser.parse_args()
    result = run(args.root.resolve(),args.binary.resolve(),args.source_root.resolve())
    with args.public.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'currentRegressionCells':11,'enabledProfiles':0}))

"""Supplement #0110's frozen core audit with explicit sign-in assistance.

The core verifier and original controller remain unchanged. This adds no guest
access, retries or observations; it checks retained completion evidence only.
"""
import argparse
import datetime
import json
from pathlib import Path

import audit as core


def sign_in(proof, folder, before, after):
    expected = {'stage':'waiting-for-fresh-agent-readiness','controllerStillRunning':True,
        'measurementRequestsQueued':False,'bootstrapPerformed':False,'actorReplayed':False,
        'faultReplayed':False,'extraVmOffs':0,'pendingCell':folder.name,
        'originalRequestCheckpoint':'before.private.json'}
    core.require(all(type(proof.get(key)) is type(value) and proof[key] == value
                     for key,value in expected.items()), 'Assisted sign-in exceeded its pending scope')
    screenshot = core.old.path_under(folder, proof['screenshot'])
    core.require(core.sha(screenshot) == proof['screenshotSha256'], 'Assisted sign-in screenshot changed')
    screen = datetime.datetime.fromisoformat(proof['observedScreenUtc']).timestamp()
    observed = datetime.datetime.fromisoformat(proof['continuationObservedUtc']).timestamp()
    core.require(before['checkpoint']['at'] < screen <= observed
            and screen < after['readiness']['challengeResult']['at'],
            'Assisted sign-in observation is outside the pending postfault interval')
    core.require(proof['authorization'] ==
        'Parent authorized login-only continuation; no bootstrap/replacement/replay'
        and proof['action'] == 'Dismiss visible incorrect-password dialog, clear password field, enter retained fixture password; login only',
        'Unexpected assisted sign-in action/authority')
    # The completion time is an observation after the operator command, not an
    # invented exact command start or a causal boundary for timestamp changes.
    return {'operatorAssistedSignIn':True,'readOnlyRequestRetried':False,
            'bootstrapReplacedAfterFault':False,'writerOrFaultReplayed':False}


def complete(root, result):
    core.require(result['operatorAssistedReadOnlyRetries'] == 0, 'Unexpected read-only retry')
    final = core.load(root/'windows-host-final-after.private.json')
    before = core.load(root/'windows-host-before.private.json')
    previous = core.load(root/'windows-host-after.private.json')
    transport = core.load(root/'transport-history.private.json')
    core.require(set(final) == {'hostBootUtc','observedUtc'}
        and final['hostBootUtc'] == before['hostBootUtc'] == previous['hostBootUtc']
        and datetime.datetime.fromisoformat(final['observedUtc']) >=
            datetime.datetime.fromisoformat(previous['observedUtc'])
        and datetime.datetime.fromisoformat(final['observedUtc']).timestamp() >
            max(event['at'] for event in transport), 'Final Windows host proof precedes completed observations')
    assisted = 0
    for row in result['cases']:
        folder = root/row['id']
        proof = folder/'sign-in-continuation.private.json'
        if proof.exists():
            row.update(sign_in(core.load(proof), folder,
                core.load(folder/'before.private.json'),core.load(folder/'after.private.json')))
            assisted += 1
        else:
            row.update({'operatorAssistedSignIn':False,'readOnlyRequestRetried':False,
                        'bootstrapReplacedAfterFault':False,'writerOrFaultReplayed':False})
    core.require(assisted == 1 and result['cases'][0]['operatorAssistedSignIn'] is True
            and result['cases'][1]['operatorAssistedSignIn'] is False,
            'Actual one-cell assisted sign-in history differs')
    result['operatorAssistedSignIns'] = assisted
    result['unassistedExactSchedule'] = False
    result['finalHostObservationAfterMeasurements'] = True
    result['independentCompletionVerifierSha256'] = core.sha(Path(__file__))
    result['limits'] += (' One postfault sign-in needed explicit login-only assistance before '
        'any artifact job was queued. No agent replacement, read-only request retry, extra '
        'artifact observer, writer replay or additional VM-off is inferred.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('root','binary','observer','inspector','frozen','baseline','public'):
        parser.add_argument('--'+arg,type=Path,required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    result = complete(root,core.guest_audit(root,args.binary.resolve(),args.observer.resolve(),
        args.inspector.resolve(),args.frozen.resolve(),args.baseline.resolve()))
    with args.public.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'caseCount':2,'vmOffs':2,'operatorAssistedSignIns':1,
                      'readOnlyRequestRetries':0,'enabledProfiles':0}))

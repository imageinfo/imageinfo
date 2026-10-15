"""Audit the exact assisted #0106 captures without changing their frozen sources.

The original controller/auditor remain bound to their actual collection bytes.
The separately hashed final auditor corrects observation validation; this module
adds the two individually reviewed read-only retries and their explicit limits.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import audit_final as core

APPROVED = {
    'vm-off-receipt-written-native-first': {
        'suffix': 'rich-before', 'mode': 'ordinary-inventory',
        'helperSha256': '52206c6fc56bb9ce10bdd5e27736deadfa0f09de7e6631a639aa76a1121aba8c',
        'possibleField': 'possiblyPartialExtraRichObservation',
        'observation': 'rich content/property inventory'},
    'vm-off-receipt-file-flushed-native-first': {
        'suffix': 'native-post', 'mode': 'ordinary-receipt-properties',
        'helperSha256': '47c87a23b1db29729c1d9242d66e241e63afda94aab4828d9a2b6721f2af42ee',
        'possibleField': 'possiblyPartialExtraNativeObservation',
        'observation': 'native metadata query'},
}


def validate(proof, helper, before, raw, approval, agent_hash):
    mandatory = {'observedAtUnix', 'originalRequestFromFrozenController', 'retryRequest',
        'reason', 'dequeueEvidenceAvailable', 'writerReplayed', 'faultReplayed',
        'operatorAssisted', 'pendingHistory', 'operatorHelperSha256', approval['possibleField']}
    core.require(type(proof) is dict and mandatory.issubset(proof),
                 'Missing/malformed read-only continuation proof')
    core.require(hashlib.sha256(helper).hexdigest() == proof['operatorHelperSha256']
                 == approval['helperSha256'], 'Unreviewed or changed continuation helper')
    case = before['case']
    request = {'id': case + '-' + approval['suffix'], 'action': 'run',
               'case': case, 'mode': approval['mode']}
    core.require(proof['originalRequestFromFrozenController'] == proof['retryRequest'] == request,
                 'Continuation is not the exact reviewed read-only request')
    core.require(proof['dequeueEvidenceAvailable'] is proof['writerReplayed']
                 is proof['faultReplayed'] is False
                 and proof['operatorAssisted'] is proof[approval['possibleField']] is True,
                 'Continuation claims an unsupported action or certainty')
    core.require(type(proof['reason']) is str and proof['reason'], 'Continuation reason missing')
    if approval['suffix'] == 'rich-before':
        core.require(proof.get('interpretationCorrection') ==
            'No dequeue or child-start evidence exists for the original missing request. '
            'It had no completed result across agent replacement; its execution may have '
            'been partial or absent. Consumed is an inference, not an observed fact.',
            'Original rich-request inference was not explicitly corrected')
    instant = proof['observedAtUnix']
    core.require(type(instant) in (int, float) and math.isfinite(instant) and instant > 0,
                 'Invalid continuation observation time')
    pending = proof['pendingHistory']
    core.require(type(pending) is list and 0 < len(pending) <= 1000,
                 'Missing/bounded pending controller history required')
    core.require([entry['at'] for entry in pending] == sorted(entry['at'] for entry in pending)
                 and max(entry['at'] for entry in pending) <= instant,
                 'Pending history was reordered or postdates continuation')
    core.require(not any(entry['path'] == '/result' and
                         entry['value'].get('id') == request['id'] for entry in pending),
                 'Continuation duplicated a previously completed request')
    if approval['suffix'] == 'rich-before':
        core.require(sum(entry['path'] == '/result' and
                         entry['value'].get('id') == case + '-native-post'
                         for entry in pending) == 1, 'Preceding native observation missing')
    hellos = [entry for entry in pending if entry['path'] == '/hello'
              and entry['at'] > before['checkpoint']['at']]
    core.require(len(hellos) >= 2, 'Agent replacement lacks retained hello observations')
    left, right = hellos[-2:]
    first, second = core.hello(left, agent_hash), core.hello(right, agent_hash)
    # Guest boot strings are estimates from UTC minus uptime. Multiple agents
    # in one boot need a bounded comparison, not exact timestamp identity.
    core.require(abs((second - first).total_seconds()) < 5
                 and right['value']['uptimeMilliseconds'] > left['value']['uptimeMilliseconds'],
                 'Replacement does not have same-boot/increasing-uptime evidence')
    completed = [entry for entry in raw if entry['path'] == '/result'
                 and entry['value'].get('id') == request['id']]
    core.require(len(completed) == 1 and completed[0]['at'] >= instant,
                 'Continuation has missing/duplicate/out-of-order completion')
    return {'operatorAssisted': True, 'readOnlyRetryCount': 1,
        'retryMode': approval['mode'], 'possiblyPartialExtraRichObservation':
            approval['possibleField'] == 'possiblyPartialExtraRichObservation',
        'possiblyPartialExtraNativeObservation':
            approval['possibleField'] == 'possiblyPartialExtraNativeObservation',
        'originalRequestExecution': 'partial-or-absent; exact work unknown',
        'dequeueEvidenceAvailable': False, 'writerReplayed': False, 'faultReplayed': False,
        'operatorHelperSha256': approval['helperSha256'],
        'assistanceLimit': 'An additional uncompleted ' + approval['observation'] +
            ' may have run before replacement. First observed differences remain '
            'bounded by that unknown work; no causal attribution follows.'}


def controls(proof, helper, before, raw, approval, agent_hash):
    candidates = [(None, helper)]
    malformed = deepcopy(proof)
    malformed.pop('pendingHistory')
    candidates.append((malformed, helper))
    unsafe = deepcopy(proof)
    unsafe['retryRequest']['mode'] = 'ordinary-receipt'
    candidates.append((unsafe, helper))
    candidates.append((deepcopy(proof), helper + b'\n'))
    fabricated = deepcopy(proof)
    fabricated['writerReplayed'] = True
    candidates.append((fabricated, helper))
    for candidate, source in candidates:
        try:
            validate(candidate, source, before, raw, approval, agent_hash)
        except ValueError:
            continue
        raise ValueError('Malformed/missing/unsafe continuation control was accepted')
    return len(candidates)


def audit(root, actor, observer, frozen, baseline):
    result = core.audit(root, actor, observer, frozen, baseline)
    binding = core.load(root / 'source-binding.private.json')
    found = {path.parent.name for path in root.glob('*/operator-continuation.private.json')}
    core.require(found == set(APPROVED), 'Missing/unreviewed assisted cell')
    shutdown = core.load(root / 'normal-shutdown.private.json')
    core.require(shutdown['method'] == 'ACPI system_powerdown; normal guest shutdown'
                 and shutdown['vmOffFaultCount'] == 4 and shutdown['commandResponse'] == {}
                 and shutdown['exactOverlayProcessExitConfirmed'] is shutdown['retainedOverlay'] is True
                 and shutdown['hostActionAttempted'] is False, 'Normal scoped shutdown not confirmed')
    stopped = core.load(root / 'helper-stop.private.json')
    core.require(stopped == {'guestAlreadyNormallyStopped': True,
        'ownedPrivateTransportStopped': True, 'ownedPrivateTpmDaemonStopped': True,
        'originalGuestHelpersTouched': False,
        'noScopedEmulatorOrTransportOrTpmProcessesRemain': True}, 'Scoped helper stop proof differs')
    negative_controls = 0
    for row in result['cases']:
        name = row['id']
        row.update({'operatorAssisted': False, 'readOnlyRetryCount': 0,
                    'possiblyPartialExtraRichObservation': False,
                    'possiblyPartialExtraNativeObservation': False})
        if name not in APPROVED:
            continue
        folder = root / name
        before = core.load(folder / 'before.private.json')
        raw = core.load(folder / 'controller-events.private.json')
        proof = core.load(folder / 'operator-continuation.private.json')
        helper = (folder / 'operator-helper.private.py').read_bytes()
        row.update(validate(proof, helper, before, raw, APPROVED[name], binding['guestAgentSha256']))
        negative_controls += controls(proof, helper, before, raw, APPROVED[name], binding['guestAgentSha256'])
    # Independently reject jitter-sized boot-estimate changes as a fresh boot.
    for row in result['cases']:
        if row['faultKind'] != 'vm-off':
            continue
        folder = root / row['id']
        first = core.hello(core.load(folder / 'before.private.json')['hello'], binding['guestAgentSha256'])
        second = core.hello(core.load(folder / 'after.private.json')['hello'], binding['guestAgentSha256'])
        core.require((second - first).total_seconds() > 5, 'VM-off lacks a distinct boot estimate')
    source_root = Path(__file__).resolve().parents[2]
    paths = (Path(__file__).resolve(), Path(core.__file__).resolve())
    result.update({'operatorAssistedCells': 2, 'readOnlyRetryRequests': 2,
        'unassistedOriginalMatrix': False, 'continuationNegativeControls': negative_controls,
        'normalGuestShutdownConfirmed': True, 'scopedHelpersStopped': True,
        'independentAuditSources': {path.relative_to(source_root).as_posix(): core.sha(path) for path in paths}})
    result['limits'] += (' Two cells required individually reviewed read-only retries after agent '
        'replacement. One may include an extra partial/absent rich inventory; the other may '
        'include an extra partial/absent native metadata query. No dequeue proof, writer '
        'replay or extra VM-off is inferred. The earliest observations do not establish cause.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('root', 'actor', 'observer', 'frozen', 'baseline', 'public'):
        parser.add_argument('--' + argument, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.actor.resolve(), args.observer.resolve(),
                   args.frozen.resolve(), args.baseline.resolve())
    with args.public.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('caseCount', 'vmOffs',
        'nativeMismatchCells', 'richMetadataContentDisagreementCells',
        'operatorAssistedCells', 'continuationNegativeControls', 'enabledProfiles')}))

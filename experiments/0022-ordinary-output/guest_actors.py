"""Bounded ordinary-owner actor checks in the existing disposable Windows guest."""
import argparse
import hashlib
import json
import pathlib
import time
from guest_qualify import assert_reports, hello, job, queue, state, verify_guest_token, wait_event


def run(root):
    root = pathlib.Path(root).resolve()
    verify_guest_token(hello()['value'])
    captures = root / ('actors-' + str(int(time.time())))
    captures.mkdir()
    results = []
    for name, actor, phase, allowed in [
        ('source-data', 'write-source', 'source-guarded', False),
        ('candidate-data', 'write-candidate', 'candidate-flushed', False),
        ('source-time-dotnet', 'time-source', 'before-property-check', False),
        ('foreign-winner', 'collision', 'before-namespace-call', True),
        ('owner-edit', None, None, None),
    ]:
        case = name + '-' + str(int(time.time()))
        prepared = job(case + '-prepare', case, 'ordinary-prepare')
        assert_reports(prepared)
        request = {'id': case + '-run', 'action': 'run', 'case': case, 'mode': 'ordinary'}
        if actor:
            request.update(actor=actor, actorAt=phase)
        queue(request)
        worker = wait_event(lambda e: e['path'] == '/result' and e['value'].get('id') == case + '-run')['value']
        terminal = assert_reports(worker)[-1]
        actor_result = None
        if actor:
            actor_result = next(e['value']['event'] for e in reversed(state()) if e['path'] == '/event' and e['value'].get('id') == case + '-run' and e['value']['event'].get('actor') == actor)
            assert actor_result['allowed'] == allowed
        if name == 'foreign-winner':
            assert terminal['publicationAttempted'] and not terminal['publicationCallSucceeded']
            winner = next(f for f in worker['files'] if f['name'] == 'output.marker')
            assert winner['sha256'] == hashlib.sha256(b'foreign-winner').hexdigest()
        else:
            assert terminal['publicationCallSucceeded'] and terminal['installedCheckPassed']
        inspect_request = {'id': case + '-inspect', 'action': 'run', 'case': case, 'mode': 'ordinary-inspect'}
        if name == 'owner-edit':
            inspect_request['postActor'] = 'write-output'
        queue(inspect_request)
        inspection = wait_event(lambda e: e['path'] == '/result' and e['value'].get('id') == case + '-inspect')['value']
        report = assert_reports(inspection)[0]
        expected = {'foreign-winner': {'candidate-and-output-conflict', 'uninspectable'}, 'owner-edit': {'output-conflict'}}.get(name, {'matching-output-recovery-required'})
        # The foreign winner can have a different inherited/default DACL;
        # refusing its property check also grants no repair or overwrite.
        assert report['outcome'] in expected
        if name == 'owner-edit':
            actor_result = next(e['value']['event'] for e in reversed(state()) if e['path'] == '/event' and e['value'].get('id') == case + '-inspect' and e['value']['event'].get('actor') == 'write-output')
            assert actor_result['allowed']
        capture = {'prepare': prepared, 'run': worker, 'actor': actor_result, 'inspect': inspection}
        (captures / (name + '.private.json')).write_text(json.dumps(capture, indent=2), encoding='utf-8')
        results.append({'id': name, 'actorAllowed': actor_result['allowed'], 'inspection': report['outcome'], 'committed': False})
    refusals = []
    expected_files = sorted(inspection['files'], key=lambda f: f['name'])
    for mode in ['ordinary-admit', 'ordinary-finalize', 'ordinary-prune']:
        result = job(mode + '-' + str(int(time.time())), case, mode)
        assert assert_reports(result)[0]['outcome'] == 'refused-before-effects'
        assert sorted(result['files'], key=lambda f: f['name']) == expected_files
        refusals.append(mode)
        (captures / (mode + '.private.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    summary = {'cases': results, 'refusedModes': refusals, 'committed': False, 'repairAllowed': False, 'productionPublicationAllowed': False}
    (captures / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'captures': str(captures), **summary}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    run(args.root)

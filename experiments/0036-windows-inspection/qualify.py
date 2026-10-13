"""Read-only restart classification of actual #0032 Windows marker transactions."""
import argparse
import csv
import hashlib
from importlib.util import spec_from_file_location, module_from_spec
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = spec_from_file_location('capture_process', HERE.parent/'0034-source-oplocks'/'qualify.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)
Process = module.Process
BARRIERS = ['root-created', 'candidate-flushed', 'prepared-record-flushed',
            'intent-record-flushed', 'validated-before-publish', 'published',
            'output-file-flushed', 'directory-flush-attempted', 'observation-record-flushed']


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        stat = path.stat()
        row = {'mtimeNs': stat.st_mtime_ns, 'identity': [stat.st_dev, stat.st_ino], 'directory': path.is_dir()}
        if path.is_file():
            row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        result[str(path.relative_to(root))] = row
    return result


def worker(binary, case, stop=None, cancel=False):
    root = case/'transaction'
    p = Process([binary, root, 'absolute'], case/'worker')
    try:
        for barrier in BARRIERS:
            event = p.next()
            assert event['barrier'] == barrier
            if barrier == stop:
                if cancel:
                    p.controls.append('cancel')
                    p.proc.stdin.write('cancel\n')
                    p.proc.stdin.flush()
                else:
                    p.stop()
                p.finish()
                return root
            p.send()
        assert p.next()['outcome'] == 'recovery-required'
        assert p.finish() == 0
        return root
    finally:
        p.stop()
        p.timer.cancel()
        if not p.capture.exists():
            p.finish()


def inspect(binary, root, capture):
    before = inventory(root)
    p = Process([binary, root, 'inspect'], capture)
    assert p.finish() == 0
    report = json.loads(''.join(p.lines))
    assert all(report[name] is False for name in ['committed', 'repairAllowed', 'cleanupAllowed', 'namespaceAcknowledged', 'productionPublicationAllowed'])
    assert report['observationOnly']
    after = inventory(root)
    assert before == after
    (capture/'inventory-before.private.json').write_text(json.dumps(before), encoding='utf-8')
    (capture/'inventory-after.private.json').write_text(json.dumps(after), encoding='utf-8')
    return report


def change_body(root, transform, name='prepared.record'):
    path = root/name
    envelope = json.loads(path.read_text())
    body = json.loads(envelope['body'])
    transform(body)
    envelope['body'] = json.dumps(body, separators=(',', ':'))
    envelope['sha256'] = hashlib.sha256(envelope['body'].encode()).hexdigest()
    path.write_text(json.dumps(envelope), encoding='utf-8')


def run(binary, parent):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        for mode in ['inspect', 'finalize', 'prune']:
            result = subprocess.run([binary, parent/'absent', mode], capture_output=True, text=True, timeout=15)
            assert result.returncode == 5 and json.loads(result.stderr)['diagnostic'] == 'WINDOWS_BACKEND_UNVERIFIED'
        assert not (parent/'absent').exists()
        print(json.dumps({'unsupportedPlatformRefused': True}))
        return
    scratch = Path(tempfile.mkdtemp(prefix='windows-inspection-', dir=parent))
    identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, check=True, timeout=15)
    sid = next(csv.reader(identity.stdout.decode('utf-8', errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(part.isdigit() for part in sid[2:].split('-'))
    policy = subprocess.run(['icacls', str(scratch), '/inheritance:r', '/grant:r', '*'+sid+':(OI)(CI)F'], capture_output=True, check=True, timeout=15)
    (scratch/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    cases = []
    try:
        for cancel in [False, True]:
            for index, barrier in enumerate(BARRIERS):
                case = scratch/(('cancel-' if cancel else 'kill-')+barrier)
                case.mkdir()
                root = worker(binary, case, barrier, cancel)
                report = inspect(binary, root, case/'inspection')
                expected = 'unattributed-artifacts' if index < 2 else 'candidate-retained-output-absent' if index < 5 else 'matching-output-recovery-required'
                assert report['outcome'] == expected, report
                cases.append({'id': case.name, 'report': report, 'inventoryUnchanged': True})
        normal = scratch/'normal'
        normal.mkdir()
        root = worker(binary, normal)
        report = inspect(binary, root, normal/'inspection')
        assert report['outcome'] == 'matching-output-recovery-required'
        cases.append({'id': 'normal', 'report': report, 'inventoryUnchanged': True})
        changes = [
            ('checksum', lambda r: (r/'prepared.record').write_text('{"body":"changed","sha256":"wrong"}'), 'RECORD_CHECKSUM_INVALID'),
            ('unknown-field', lambda r: change_body(r, lambda b: b.update(extra=True)), 'RECORD_BODY_INVALID'),
            ('untrusted-path', lambda r: change_body(r, lambda b: b.update(target='../../original.cr3')), 'RECORD_SCOPE_INVALID'),
            ('commit-flag', lambda r: change_body(r, lambda b: b.update(committed=True)), 'RECORD_SCOPE_INVALID'),
            ('root-id', lambda r: change_body(r, lambda b: b['root'].update(identity='f:f')), 'RECORD_ROOT_BINDING_CONFLICT'),
            ('records-disagree', lambda r: change_body(r, lambda b: b['candidate'].update(lastWriteTime=1), 'observation.record'), 'RECORDS_DISAGREE'),
            ('missing-prepared', lambda r: (r/'prepared.record').unlink(), 'RECORD_SEQUENCE_INVALID'),
            ('unexpected-entry', lambda r: (r/'unrelated.bin').write_bytes(b'foreign'), 'UNEXPECTED_ROOT_ENTRY'),
            ('oversized-record', lambda r: (r/'prepared.record').write_bytes(b' '*65537), 'ARTIFACT_SIZE_BOUND'),
            ('multilink-output', lambda r: os.link(r/'output.bin', r.parent/'alias.bin'), 'MULTILINK_ARTIFACT_REFUSED'),
        ]
        for name, action, expected in changes:
            case = scratch/name
            case.mkdir()
            root = worker(binary, case)
            action(root)
            report = inspect(binary, root, case/'inspection')
            assert report['outcome'] == 'uninspectable' and report['diagnostic'] == expected, report
            cases.append({'id': name, 'report': report, 'inventoryUnchanged': True})
        for name in ['missing-output', 'changed-output', 'self-consistent-record']:
            case = scratch/name
            case.mkdir()
            root = worker(binary, case)
            target = root/'output.bin'
            if name == 'missing-output':
                target.unlink()
            else:
                target.write_bytes(b'F'*65536)
                if name == 'self-consistent-record':
                    stamp = target.stat().st_mtime_ns//100+116444736000000000
                    for record in ['prepared.record', 'intent.record', 'observation.record']:
                        def update(body):
                            body['candidate']['lastWriteTime'] = stamp
                            body['candidateSha256'] = hashlib.sha256(b'F'*65536).hexdigest()
                        change_body(root, update, record)
            report = inspect(binary, root, case/'inspection')
            expected = {'missing-output': 'candidate-missing-output-absent', 'changed-output': 'output-conflict', 'self-consistent-record': 'matching-output-recovery-required'}[name]
            assert report['outcome'] == expected, report
            cases.append({'id': name, 'report': report, 'inventoryUnchanged': True})
        for mode in ['admit', 'finalize', 'prune']:
            case = scratch/mode
            case.mkdir()
            p = Process([binary, case/'absent', mode], case/'inspection')
            assert p.finish() == 0
            report = json.loads(''.join(p.lines))
            assert report['outcome'] == 'refused-before-effects' and not (case/'absent').exists()
            assert not report['committed'] and not report['productionPublicationAllowed']
            cases.append({'id': mode, 'report': report, 'workerArtifacts': 0})
        report = {'schemaVersion': 1, 'caseCount': len(cases), 'cases': cases, 'productionPublicationAllowed': False, 'enabledProfiles': 0}
        (scratch/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'root': str(scratch), 'caseCount': len(cases)}))
    except BaseException:
        (scratch/'failed-report.private.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
        print('Retained attempt: '+str(scratch), file=sys.stderr)
        raise


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification assertions require Python without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--parent', required=True)
    args = parser.parse_args()
    run(args.binary, args.parent)

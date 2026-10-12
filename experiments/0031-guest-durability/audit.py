"""Verify retained guest captures and write a sanitized public observation ledger."""
import argparse
import hashlib
import json
from pathlib import Path
from guest_suite import inventory


def audit(root, build, public):
    root, build = Path(root).resolve(), Path(build).resolve()
    report = json.loads((root/'report.json').read_text())
    assert len(report['cases']) == report['caseCount']
    assert len({case['id'] for case in report['cases']}) == report['caseCount']
    assert not report['productionPublicationAllowed'] and report['enabledProfiles'] == 0
    for name, expected in report['buildHashes'].items():
        assert hashlib.sha256((build/name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((build/'root/probe').read_bytes()).hexdigest() == report['probeSha256']
    for name, expected in report['sourceHashes'].items():
        assert hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() == expected
    capture_count = 0
    for case in report['cases']:
        folder = root/case['id']
        assert json.loads((folder/'result.json').read_text()) == case
        assert (folder/'data.raw').is_file() and not (folder/'data.raw').is_symlink()
        for capture in folder.iterdir():
            if not capture.is_dir():
                continue
            argv = json.loads((capture/'argv.json').read_text())
            assert '-net' in argv and argv[argv.index('-net')+1] == 'none'
            assert '-nodefaults' in argv and '-no-user-config' in argv
            assert not any('virtfs' in arg or 'host_device' in arg for arg in argv)
            raw = (capture/'serial.log').read_text()
            assert '6.18.52-0-virt' in raw and '/dev/vda /data ext4' in raw
            events = json.loads((capture/'events.json').read_text())
            controls = json.loads((capture/'controls.json').read_text())
            parsed = [json.loads(line) for line in raw.splitlines() if line.startswith('{')]
            assert all(event in parsed for event in events)
            assert all(not event.get('committed',False) and not event.get('productionPublicationAllowed',False) for event in parsed)
            if case.get('guestPanicObserved') and capture.name == 'worker':
                assert 'Kernel panic' in raw
            if capture.name == 'worker' and case.get('interruption') != 'normal' and 'phase' in case:
                assert any(event.get('barrier') == case['phase'] for event in events)
            if case.get('interruption') == 'worker-kill' and capture.name == 'worker':
                assert controls[-1] == 'kill-worker' and 'IMAGEINFO_WORKER_KILLED' in raw
            if case.get('interruption') == 'cooperative-cancel' and capture.name == 'worker':
                assert controls[-1] == 'cancel' and any(event.get('issue') == 'CONTROL_STOP' for event in events)
            if capture.name in ['restart','actor']:
                assert any(event.get('classification') == case['classification'] for event in events)
                assert sum(event.get('outcome') == 'refused-before-mutation' for event in events) == 3
                parts = inventory(raw)
                assert parts[0] == parts[1]
            capture_count += 1
    manifest = {str(file.relative_to(root)):hashlib.sha256(file.read_bytes()).hexdigest()
                for file in root.rglob('*') if file.is_file() and file.name != 'capture-manifest.private.json'}
    (root/'capture-manifest.private.json').write_text(json.dumps(manifest,indent=2)+'\n')
    ledger = {key:value for key,value in report.items() if key not in ['buildHashes','probeSha256','sourceHashes']}
    ledger.update({'schemaVersion':1,'observedOn':'2026-10-12','captureCount':capture_count,
                   'captureAuditPassed':True,'repairOrPruneExecuted':False,
                   'windowsGuestCrashRuns':0,'originalMediaInputs':0})
    Path(public).write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({'cases':report['caseCount'],'captures':capture_count,'retainedFiles':len(manifest),'auditPassed':True}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit requires Python without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root','build','public']:
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    audit(args.root,args.build,args.public)

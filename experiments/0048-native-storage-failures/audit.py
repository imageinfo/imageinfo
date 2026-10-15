"""Audit actual private guest captures; emit only bounded public observations."""
import argparse
import hashlib
import json
from pathlib import Path
import re

if not __debug__:
    raise RuntimeError('Audit requires enabled assertions')

FLAGS = ('committed', 'namespaceAcknowledged', 'repairAllowed',
         'productionPublicationAllowed')
IDS = ['normal-control', 'candidate-full', 'candidate-partial-attempt',
       'prepared-record-full', 'receipt-full']
WORKER = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
MARKER = hashlib.sha256(b'3' * 65536).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def events(result):
    for event in result['events']:
        assert all(event.get(flag) is False for flag in FLAGS), event
    assert set(result['controls']) <= {'continue'}
    return result['events']


def terminal(result):
    return next((event for event in reversed(events(result)) if 'outcome' in event), {})


def inventory(items):
    assert len(items) == len({item['name'] for item in items})
    return {item['name']: item for item in items}


def audit(folder):
    supervisor = read(folder / 'supervisor.private.json')
    assert supervisor['guestNormallyShutdown'] is True
    assert supervisor['hostBootUnchanged'] is True
    assert supervisor['hostBootBefore']['bootTicks'] == supervisor['hostBootAfter']['bootTicks']
    assert supervisor['guestDiskRetained'] is True and supervisor['secondaryDiskRetained'] is True
    config = supervisor['secondaryConfig']
    assert config['architecture'] == 'x86_64'
    assert config['queryBlockCache'] == {'writeback': False, 'direct': False, 'no-flush': False}
    assert sorted(node['driver'] for node in config['namedBlockNodes']) == ['file', 'raw']
    assert all(node['cache'] == {'writeback': True, 'direct': False, 'no-flush': False}
               for node in config['namedBlockNodes'])
    qualify = Path(__file__).with_name('qualify.ps1')
    assert hashlib.sha256(qualify.read_bytes()).hexdigest() == supervisor['served']['/qualify.ps1']
    for name, expected in supervisor['privateCaptures'].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected
    binding = read(folder / 'binding.private.json')
    preflight = read(folder / 'preflight.private.json')
    assert preflight['os']['Version'] == '10.0.26300'
    assert read(folder / 'bootstrap-complete.private.json')['hadError'] is False
    assert binding['workerSha256'] == WORKER
    assert binding['sourceRevision'] == 'b819f54533c495b332c3d4dbb0caccef49923036'
    assert binding['driveFormat'] == 'NTFS'
    assert 64 * 1024**2 <= binding['volumeBytes'] <= 128 * 1024**2
    assert binding['partition']['IsBoot'] is False and binding['partition']['IsSystem'] is False
    assert binding['fixture']['schema'] == 'imageinfo-native-errors-fixture-v1'
    assert read(folder / 'complete.private.json')['cases'] == 5
    cases = read(folder / 'cases.private.json')
    assert [case['id'] for case in cases] == IDS
    rows = []
    for case in cases:
        before = inventory(case['beforeInspection'])
        assert set(before) <= {'source.marker', 'candidate.marker', 'output.marker',
                               'prepared.record', 'intent.record', 'observation.record',
                               'receipt.record'}, 'Unexpected retained namespace'
        assert all(0 <= item['size'] <= 65536 for item in before.values())
        file_ids = []
        for item in before.values():
            assert item['fileIdQueryExitCode'] == 0, 'Actual file ID query required'
            match = re.search(r'0x[0-9a-fA-F]+', item['fileIdQuery'])
            assert match, 'Missing actual file identity'
            file_ids.append(match.group().lower())
        assert len(file_ids) == len(set(file_ids)), 'Aliased retained files'
        assert before == inventory(case['afterInspection']), 'Inspector changed artifacts'
        assert before['source.marker'] == inventory(case['sourceBefore'])['source.marker']
        assert before['source.marker']['sha256'] == MARKER
        assert before['source.marker']['size'] == 65536
        end = terminal(case['worker'])
        inspection = terminal(case['inspection'])
        assert end and inspection, 'Finite terminal reports required'
        assert end['ownedHandlesRemoved'] == 0
        assert end['sourceRetained'] is True and end['rootRetained'] is True
        assert case['worker']['exitCode'] == 0
        assert case['inspection']['exitCode'] == 0
        diagnostic = end.get('diagnostic') or ''
        assert not re.search(r'[A-Za-z]:[\\/]|\\\\', diagnostic), 'Private path in public diagnostic'
        native_codes = sorted(set(int(value) for value in re.findall(r'os error (\d+)', diagnostic)))
        if case['id'] == 'normal-control':
            assert not case['worker']['fill']
            assert end['outcome'] == 'observed-receipt-recovery-required'
            assert inspection['outcome'] == end['outcome']
            assert case['receiptContextAvailable'] is True
        else:
            fill = case['worker']['fill']
            assert fill['provenance'] == 'actual-native-filler-io'
            # HRESULT's low word records the real Windows storage-full status.
            assert fill['failure']['hresult'] & 0xffff in (39, 112)
            assert fill['fillerLength'] <= 128 * 1024**2
            assert 'INJECTED' not in diagnostic and 'CONTROL_' not in diagnostic
            assert end['outcome'] != 'observed-receipt-recovery-required'
            assert any(code in (39, 112) for code in native_codes), diagnostic
            assert case['receiptContextAvailable'] is False
            assert inspection['outcome'] == 'receipt-inspection-refused'
            assert inspection.get('effectsAttempted') is False
            assert not end['finalCheckPassed']
        if 'output.marker' in before:
            assert before['output.marker']['size'] == 65536
            assert before['output.marker']['sha256'] == MARKER
        rows.append({'id': case['id'], 'fillAtBarrier': case['phase'] or None,
                     'outcome': end['outcome'], 'diagnostic': diagnostic or None,
                     'actualWorkerNativeErrorCodes': native_codes,
                     'fillerNativeErrorCode': (case['worker']['fill']['failure']['hresult'] & 0xffff)
                     if case['worker']['fill'] else None,
                     'retainedArtifacts': [{'name': item['name'], 'bytes': item['size'],
                                            'sha256': item['sha256']} for item in before.values()],
                     'sourceUnchanged': True, 'inspectionInventoryUnchanged': True,
                     'retainedFileIdentitiesChecked': True,
                     'inspectionOutcome': inspection['outcome'],
                     'inspectionHasActualReceiptContext': case['receiptContextAvailable'],
                     'ownedHandlesRemoved': end['ownedHandlesRemoved'],
                     'publicationAttempted': end['publicationAttempted'],
                     'publicationCallSucceeded': end['publicationCallSucceeded'],
                     'cleanupPending': end['cleanupPending'],
                     **{flag: False for flag in FLAGS}})
    return {'schema': 'imageinfo-native-storage-failures-v1',
            'sourceRevision': binding['sourceRevision'], 'workerSha256': WORKER,
            'qualifierSha256': supervisor['served']['/qualify.ps1'],
            'auditorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'privateCaptureManifestSha256': hashlib.sha256((folder / 'supervisor.private.json').read_bytes()).hexdigest(),
            'observationDate': '2026-10-15',
            'os': {'edition': 'Windows 11 Enterprise Evaluation', 'version': '10.0.26300',
                   'architecture': 'x86_64', 'standardUser': True},
            'fixture': {'filesystem': 'NTFS', 'volumeBytes': binding['volumeBytes'],
                        'secondaryDisposableOnly': True, 'systemOrBoot': False,
                        'rawImageBytes': supervisor['fixture']['bytes'],
                        'partitionStartLba': 2048, 'partitionType': '07',
                        'imageDriver': 'raw', 'underlyingDriver': 'file',
                        'device': 'usb-storage', 'controller': 'qemu-xhci',
                        'explicitCacheFlagsSupplied': False,
                        'queryBlockCache': config['queryBlockCache'],
                        'namedBlockNodeCaches': config['namedBlockNodes'],
                        'initialImageSha256': supervisor['fixture']['initialDiskSha256'],
                        'retainedFinalImageSha256': supervisor['secondaryFinalSha256']},
            'guestNormallyShutdown': True, 'hostBootUnchanged': True,
            'hostCachesRemainAlive': True,
            'cases': rows,
            'unqualified': ['actual native read failure', 'actual native device flush failure',
                            'isolated metadata-only exhaustion', 'physical power loss',
                            'production profile', 'RAW admission'],
            'partialCandidateObserved': any(0 < item['bytes'] < 65536 for row in rows
                                            for item in row['retainedArtifacts']
                                            if item['name'] == 'candidate.marker'),
            **{flag: False for flag in FLAGS}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('captures', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = audit(args.captures)
    wire = json.dumps(value, indent=2) + '\n'
    if args.output:
        args.output.write_bytes(wire.encode('utf-8'))
    else:
        print(wire, end='')


if __name__ == '__main__':
    main()

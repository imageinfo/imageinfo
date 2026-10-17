"""Authored retained-report rejection controls; no process/resource measurement."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import audit_reader_byte_boundaries as a


def main():
    with tempfile.TemporaryDirectory(prefix='imageinfo-byte-audit-', dir=os.environ.get('IMAGEINFO_TEST_TMP')) as folder:
        root = Path(folder)
        witness = {'schemaVersion': 1, 'binary': str((root / 'authored-probe.exe').resolve()),
                   'binarySha256': '1' * 64, 'files': {k: '2' * 64 for k in a.REQUIRED_BINDINGS}}
        freeze = root / 'freeze.json'
        freeze.write_text(json.dumps(witness), encoding='utf-8')
        freeze_hash = hashlib.sha256(freeze.read_bytes()).hexdigest()
        attempts, values = [], []
        for index, (axis, delta) in enumerate((axis, d) for axis in ('metadata', 'block') for d in (-1, 0, 1)):
            lengths = [1048576] * 7 + [1048576 + delta] if axis == 'metadata' else [1048576 + delta]
            if axis == 'metadata' and delta == 1:
                lengths = [1048576] * 7 + [1048575, 2]
            planned = [{'offset': 0, 'requested': n, 'returned': n} for n in lengths]
            prefix, total = [], 0
            for r in planned:
                if total + r['requested'] > 8388608 or r['requested'] > 1048576:
                    break
                prefix.append(r)
                total += r['requested']
            values.append({'axis': axis, 'delta': delta, 'plannedRequests': planned,
                'sourceBytes': 1048577, 'plannedRequestedBytes': sum(lengths),
                'largestRequestBytes': max(lengths), 'requests': prefix,
                'underlyingRequestedBytes': total, 'sourceUnchanged': True,
                'sourceSha256': '0' * 64, 'complete': delta <= 0,
                'status': 'OK' if delta <= 0 else 'LIMIT_EXCEEDED',
                'reportedChargedBytes': total if delta <= 0 else None, 'readElapsedNs': 1})
            metric_values = {key: 100 for key in a.METRICS}
            metric_values['physicalIoBytes'] = None
            samples = [{'beginOffsetNs': begin, 'endOffsetNs': begin + 1,
                        'final': final, 'values': copy.deepcopy(metric_values),
                        'errors': {'physicalIoBytes': 'not instrumented; logical transfers are not device traffic'}}
                       for begin, final in [(1, False), (3, True)]]
            attempts.append({'axis': axis, 'delta': delta, 'captureStem': f'{index:02d}-{axis}-{delta}',
                'argv': [witness['binary'], axis, str(delta)],
                'process': {'outcome': 'exited', 'exitCode': 0, 'censored': False, 'errorClass': None,
                    'stderrSha256': hashlib.sha256(b'').hexdigest(), 'stderrBytes': 0,
                    'stderrCapturedBytes': 0, 'elapsedNs': 10},
                'telemetry': {'valid': True, 'membership': 'direct-only-observed', 'pid': 123,
                    'requestedIntervalMs': 1, 'maxSamples': 2048, 'errors': [], 'stopReason': None,
                    'observedDescendantPids': [], 'observerWallNs': 2, 'samples': samples,
                    'sampledMaxima': {'workingSetBytes': 100, 'privateCommitBytes': 100}}})
        original = {'schemaVersion': 1, 'scope': 'six authored native default-byte-boundary cells',
                    'limits': {'metadataBytes': 8388608, 'blockBytes': 1048576},
                    'freezeSha256': freeze_hash, 'binding': witness, 'attempts': attempts}

        def save(campaign, reports):
            for row, report in zip(campaign['attempts'], reports):
                raw = json.dumps(report).encode()
                (root / (row['captureStem'] + '.stdout')).write_bytes(raw)
                (root / (row['captureStem'] + '.stderr')).write_bytes(b'')
                row['process'].update(stdoutSha256=hashlib.sha256(raw).hexdigest(),
                                      stdoutBytes=len(raw), stdoutCapturedBytes=len(raw))
            (root / 'campaign.json').write_text(json.dumps(campaign), encoding='utf-8')
        save(copy.deepcopy(original), values)
        assert a.audit(root, freeze, freeze_hash)['status'] == 'passed'
        controls = [
            lambda c, v: c['attempts'].pop(),
            lambda c, v: v[0].update(plannedRequestedBytes=0),
            lambda c, v: v[2].update(complete=True),
            lambda c, v: v[0]['requests'].pop(),
            lambda c, v: v[3].update(reportedChargedBytes=None),
            lambda c, v: v[0].update(sourceUnchanged=False),
            lambda c, v: c['attempts'][0]['telemetry'].update(valid=False),
            lambda c, v: c['attempts'][0]['process'].update(censored=True),
            lambda c, v: c['attempts'][0]['telemetry']['samples'][-1].update(values={}),
            lambda c, v: c['attempts'][0]['telemetry']['samples'][-1]['values'].update(userCpuNs=None),
            lambda c, v: c['attempts'][0]['telemetry']['samples'][-1]['values'].update(readTransferBytes=-1),
            lambda c, v: c['attempts'][0]['telemetry'].update(sampledMaxima={}),
            lambda c, v: c['attempts'][0]['telemetry']['sampledMaxima'].update(workingSetBytes=999),
            lambda c, v: c['attempts'][0]['telemetry']['samples'][-1].update(endOffsetNs=11),
            lambda c, v: c['attempts'][0]['telemetry']['samples'][0].update(final=True),
            lambda c, v: c['attempts'][0]['telemetry'].update(errors=['counter-setup']),
            lambda c, v: c['attempts'][0]['telemetry'].update(stopReason='telemetry-limit'),
            lambda c, v: c['attempts'][0]['telemetry']['samples'][-1]['values'].update(systemCpuNs=1),
            lambda c, v: c['attempts'][0]['process'].update(elapsedNs=0),
            lambda c, v: v[0].update(readElapsedNs=11),
            lambda c, v: c.update(binding={}),
            lambda c, v: c['binding'].update(binarySha256='f' * 64),
            lambda c, v: c['binding']['files'].pop('tests/support/byte_budget_fixtures.rs'),
            lambda c, v: c['binding']['files'].update({'src/reader/bounded.rs': 'f' * 64}),
            lambda c, v: c['attempts'][0].update(argv=[witness['binary'], 'block', '1']),
            lambda c, v: c.update(freezeSha256='f' * 64),
            lambda c, v: c.update(limits={'metadataBytes': 0, 'blockBytes': 1048576}),
        ]
        for mutate in controls:
            campaign, reports = copy.deepcopy(original), copy.deepcopy(values)
            mutate(campaign, reports)
            save(campaign, reports)
            try:
                a.audit(root, freeze, freeze_hash)
            except (ValueError, KeyError):
                pass
            else:
                raise AssertionError('accepted invalid retained-report control')
        save(copy.deepcopy(original), values)
        try:
            a.audit(root, freeze, 'f' * 64)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted changed independent witness hash')
    print(f'Byte-boundary retained-output auditor: authored valid report and {len(controls)+1} rejection controls passed; no resource measurement.')


if __name__ == '__main__':
    main()

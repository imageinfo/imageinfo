"""#0137: direct real-shell checks of four bounded authored operations."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

from check_native_paths import quote
from check_preview_pair_arguments import inventory, check as check_preview
from check_read_arguments import run

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/legacy-compatibility/command-shells'
LEDGER = PACKAGE / 'cases.json'
PLATFORM = {'win32': 'windows', 'linux': 'linux', 'darwin': 'macos'}.get(sys.platform)
PREVIEWS = {'ThumbnailImage': b'\xff\xd8\xff\xe0\x00\x03T\xff\xd9',
            'PreviewImage': b'\xff\xd8\xff\xe0\x00\x09PREVIEW\xff\xd9',
            'JpgFromRaw': b'\xff\xd8\xff\xe0\x00\x0bFULL-JPEG\xff\xd9'}
SESSION_LIMITS = dict(maxFrames=256, maxInputFrameBytes=524288, maxInputs=4,
                      maxMetadataBytes=8388608, maxOutputFrameBytes=16777728,
                      maxQueuedRequests=0, maxResultBytes=16777216,
                      maxTokenBytes=32768, maxTokens=128, maxTotalTokenBytes=65536)


def fixture(folder, captures):
    """Own three distinguishable authored resources; never change shared fixtures."""
    source = folder / 'fixture.rs'
    support = json.dumps((ROOT / 'tests/support/mod.rs').as_posix())
    resources = ','.join('vec![' + ','.join(map(str, value)) + ']'
                         for value in PREVIEWS.values())
    source.write_text(f'#[allow(dead_code)] #[path={support}] mod support;\n'
                      'fn main() { let d=std::path::PathBuf::from('
                      'std::env::args_os().nth(1).unwrap());'
                      'let f=support::fixture_with_previews('
                      f'"Firmware Version 2.2.1",{resources}).bytes;'
                      'std::fs::write(d.join("source.cr3"),f).unwrap(); }',
                      encoding='utf-8', newline='\n')
    executable = folder / ('fixture.exe' if os.name == 'nt' else 'fixture')
    assert run(['rustc', '--edition=2024', str(source), '-o', str(executable)],
               ROOT, captures / 'fixture-build', 60)[0] == 0
    assert run([str(executable), str(folder)], ROOT, captures / 'fixture-export')[0] == 0
    data = (folder / 'source.cr3').read_bytes()
    assert len(set(PREVIEWS.values())) == 3
    assert all(data.count(value) == 1 for value in PREVIEWS.values())
    return data


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(tokens, shell, payload=None):
    text = ' '.join(quote(token, shell) for token in tokens)
    if shell == 'powershell':
        text = '& ' + text
        if payload is not None:
            text = quote(payload, shell) + ' | ' + text
    elif payload is not None:
        text = "printf '%s\\n' " + quote(payload, shell) + ' | ' + text
    return text


def script(binary, argv, shell, witness, payload):
    observer = command([sys.executable, str(PACKAGE / 'argv_witness.py'),
                        str(witness), *argv], shell, payload)
    actual = command([str(binary), *argv], shell, payload)
    if shell == 'powershell':
        return ("$ErrorActionPreference = 'Stop'\n"
                '$OutputEncoding = [Console]::OutputEncoding = '
                '[System.Text.UTF8Encoding]::new($false)\n'
                + observer + '\nif ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }\n'
                + actual + '\nexit $LASTEXITCODE\n')
    return 'set -o pipefail\n' + observer + '\nstatus=$?\n' \
        + '[ "$status" -eq 0 ] || exit "$status"\n' + actual + '\nexit $?\n'


def inputs(case):
    name = case['name']
    source = name + '.cr3'
    sidecar = name + '.xmp'
    output = name + '.jpg'
    operation = case['operation']
    if operation == 'extraction':
        argv = ['--output=json', 'binary', 'extract', '--tag=PreviewImage',
                '--output-file=' + output, '--', source]
    elif operation == 'date-preview':
        argv = ['--output=json', 'preview', 'date-time-original', '--value',
                '2000:02:29 23:59:59', '--', source]
    elif operation == 'pair':
        argv = ['--output=json', 'sidecar', 'pair', '--sidecar', sidecar, '--', source]
    else:
        assert operation == 'session'
        argv = ['session', 'read']
    payload = None
    if operation == 'session':
        frames = [dict(protocolVersion=1, kind='read', id='literal',
                       tokens=['metadata', 'read', '--tag', 'Model', '--', source]),
                  dict(protocolVersion=1, kind='close', id='done')]
        payload = '\n'.join(json.dumps(frame, ensure_ascii=False,
                                       separators=(',', ':')) for frame in frames)
    return source, sidecar, output, argv, payload


def verify(case, status, out, err, work, data, offset):
    source, sidecar, output, _, _ = inputs(case)
    operation = case['operation']
    assert b'\x1b' not in out + err
    assert status == case['status'], status
    assert bool(err) == (status != 0)
    if operation == 'session':
        assert out.endswith(b'\n') and b'\r' not in out, 'noncanonical JSONL'
        frames = [json.loads(line) for line in out.splitlines()]
        assert [frame['kind'] for frame in frames] == [
            'session-ready', 'read-result', 'session-complete']
        assert all(frame['protocolVersion'] == 1 for frame in frames)
        assert frames[0] == dict(protocolVersion=1, kind='session-ready',
                                 allowApply=False, limits=SESSION_LIMITS)
        assert frames[1]['id'] == 'literal'
        assert frames[2]['reason'] == 'close' and frames[2]['closeId'] == 'done'
        assert frames[2] == dict(protocolVersion=1, kind='session-complete',
                                 reason='close', closeId='done', exitStatus=0,
                                 frames=2, results=1)
        value = frames[1]['result']
    else:
        value = json.loads(out)
    request_id = value['requestId']
    assert isinstance(request_id, str) and request_id
    if operation == 'session':
        assert request_id == 'literal'
    expected_operation = {'extraction': 'binary extract', 'pair': 'sidecar pair',
                          'date-preview': 'preview date-time-original',
                          'session': 'metadata read'}[operation]
    assert value['schemaVersion'] == 1
    assert value['request'] == dict(schemaVersion=1, kind='request', requestId=request_id,
                                    operation=expected_operation,
                                    mode='preview' if operation == 'date-preview' else 'read',
                                    issues=[])
    state = 'refused' if status else 'read'
    artifacts = ([dict(kind='extraction', path=output, retainedPath=None, state='committed',
                       transactionId=None, recoveryIds=[])] if operation == 'extraction' else [])
    assert value['summary'] == dict(schemaVersion=1, kind='summary', requestId=request_id,
                                    exitStatus=status, selectionComplete=True,
                                    counts=dict(discovered=1, excluded=0, deduplicated=0,
                                                byState={state: 1}), artifacts=artifacts,
                                    issues=[], interrupted=False, outputComplete=True)
    assert len(value['files']) == 1
    file = value['files'][0]
    assert file['schemaVersion'] == 1 and file['kind'] == 'file'
    assert file['requestId'] == request_id and file['inputId'] == 'input-0'
    assert file['path'] == source and (work / file['path']).samefile(work / source)
    assert file['state'] == state and file['transactionId'] is None
    assert file['effects'] == dict(publicationMayHaveOccurred=False, changed=False,
                                   cleanupPending=False, recoveryIds=[], notes=[])
    expected_codes = (['OPAQUE_DEPENDENCY_UNPROVEN'] if operation == 'date-preview'
                      else ['COVERAGE_PARTIAL'] if operation == 'session'
                      else [case['code']] if case.get('code') else [])
    assert [issue['code'] for issue in file['issues']] == expected_codes
    if case.get('code') == 'PAIRING_NAME_UNSUPPORTED':
        assert value['request']['operation'] == 'sidecar pair'
        assert value['summary']['exitStatus'] == 1 and value['summary']['artifacts'] == []
        assert len(value['files']) == 1
        file = value['files'][0]
        assert file['path'] == source and file['state'] == 'refused'
        assert file['snapshot'] is None
        assert [issue['code'] for issue in file['issues']] == ['PAIRING_NAME_UNSUPPORTED']
    elif operation in ('date-preview', 'pair'):
        check_preview(dict(status=status, check='preview' if operation == 'date-preview'
                           else 'pair', channel='json', input=source, sidecar=sidecar),
                      status, out, err, work, data, offset)
    else:
        assert value['schemaVersion'] == 1 and value['summary']['exitStatus'] == 0
        assert len(value['files']) == 1
        file = value['files'][0]
        assert file['path'] == source and (work / file['path']).samefile(work / source)
        assert file['state'] == 'read'
        if operation == 'session':
            assert value['summary']['artifacts'] == []
            assert [item['tag']['name'] for item in file['snapshot']['occurrences']] == ['Model']
            snapshot = file['snapshot']
            assert snapshot['kind'] == 'metadata-snapshot' and snapshot['basis'] == 'observed'
            assert snapshot['issues'] == []
            assert snapshot['sources'] == [dict(
                byteLength=str(len(data)), displayPath=source, id='src-raw', role='raw',
                identity=dict(kind='unavailable', reason='Bounded metadata reading does not '
                              'hash the complete source; this snapshot cannot authorize mutations.'))]
            occurrence = snapshot['occurrences'][0]
            assert occurrence['tag'] == dict(name='Model', namespace='exif', nativeId='272',
                definitionRef='r5-read-slice-2026-10-11.1:exif:272')
            assert occurrence['documentRef'] == 'doc-raw'
            assert occurrence['id'] == 'occ-3' and occurrence['ordinal'] == 3
            assert occurrence['groups'] == [dict(axis='metadata-family', label='exif')]
            assert occurrence['issueRefs'] == [] and occurrence['capabilityRefs'] == []
            assert occurrence['origin'] == dict(kind='stored', byteOrder='little',
                                                  encoding='ASCII', resourceRef='value-3')
            assert occurrence['values'] == dict(
                raw=dict(state='present', value=dict(kind='string', text='Canon EOS R5')),
                normalized=dict(state='present', value=dict(kind='string', text='Canon EOS R5')),
                display=dict(state='unavailable', reason='Not requested'),
                normalization=dict(assumptions=[], dependencies=[], reversibility='exact',
                                   ruleRef='identity-exact-stored-value', unit=None))
            assert data.count(b'Canon EOS R5\0') == 1
            resource = next(item for item in snapshot['resources'] if item['id'] == 'value-3')
            assert resource == dict(id='value-3', byteLength='13', mediaType=None, sha256=None,
                content=dict(kind='source-ranges', ranges=[dict(length='13',
                    offset=str(data.index(b'Canon EOS R5\0')), ref='src-raw', space='source')]))
        else:
            assert value['summary']['artifacts'] == [dict(
                kind='extraction', path=output, retainedPath=None, state='committed',
                transactionId=None, recoveryIds=[])]
            assert file['snapshot'] is None
            assert (work / output).read_bytes() == PREVIEWS['PreviewImage']


def reject_false_reports(case, status, out, err, work, data, offset):
    """Independent one-field capture corruptions; never add executable cases."""
    session = case['operation'] == 'session'
    original = ([json.loads(line) for line in out.splitlines()] if session
                else json.loads(out))
    prefix = [1, 'result'] if session else []
    mutations = [
        ('wrong-input', prefix + ['files', 0, 'path'], 'decoy.cr3'),
        ('wrong-request-operation', prefix + ['request', 'operation'], 'metadata list'),
        ('wrong-request-mode', prefix + ['request', 'mode'], 'apply'),
        ('wrong-file-request-id', prefix + ['files', 0, 'requestId'], 'wrong'),
        ('wrong-file-input-id', prefix + ['files', 0, 'inputId'], 'input-99'),
        ('false-source-effect', prefix + ['files', 0, 'effects', 'changed'], True),
        ('wrong-discovered', prefix + ['summary', 'counts', 'discovered'], 12345),
        ('wrong-excluded', prefix + ['summary', 'counts', 'excluded'], 1),
        ('wrong-deduplicated', prefix + ['summary', 'counts', 'deduplicated'], 1),
        ('wrong-by-state', prefix + ['summary', 'counts', 'byState'], {'failed': 12345}),
        ('incomplete-selection', prefix + ['summary', 'selectionComplete'], False),
        ('interrupted-summary', prefix + ['summary', 'interrupted'], True),
        ('incomplete-output', prefix + ['summary', 'outputComplete'], False),
    ]
    if session:
        occurrence = prefix + ['files', 0, 'snapshot', 'occurrences', 0]
        mutations += [
            ('wrong-ready-limit', [0, 'limits', 'maxFrames'], 12345),
            ('wrong-completion-frames', [2, 'frames'], 12345),
            ('wrong-completion-results', [2, 'results'], 12345),
            ('wrong-close-id', [2, 'closeId'], 'wrong'),
            ('wrong-read-id', [1, 'id'], 'wrong'),
            ('wrong-model-raw', occurrence + ['values', 'raw', 'value', 'text'], 'Other camera'),
            ('wrong-model-normalized', occurrence + ['values', 'normalized', 'value', 'text'],
             'Other camera'),
            ('wrong-model-type', occurrence + ['values', 'raw', 'value', 'kind'], 'integer'),
            ('wrong-model-namespace', occurrence + ['tag', 'namespace'], 'xmp'),
            ('wrong-model-native-id', occurrence + ['tag', 'nativeId'], '271'),
            ('wrong-model-view', occurrence + ['values', 'display'],
             dict(state='present', value=dict(kind='string', text='Canon EOS R5'))),
            ('wrong-resource-binding', occurrence + ['origin', 'resourceRef'], 'preview-0'),
            ('wrong-source-length', prefix + ['files', 0, 'snapshot', 'sources', 0, 'byteLength'],
             str(len(data) + 1)),
        ]
    elif case['operation'] == 'extraction':
        mutations.append(('wrong-output-artifact', ['summary', 'artifacts', 0, 'path'],
                          'wrong.jpg'))
    elif case['operation'] == 'date-preview':
        mutations.append(('wrong-proposed-byte',
                          ['files', 0, 'snapshot', 'preview', 'proposed_bytes', 0], 0))
    else:
        mutations.append(('wrong-sidecar-binding', ['files', 0, 'snapshot', 'pair', 'sidecar_path'],
                          str(work / 'decoy.cr3')))
    rejected = []
    for name, path, wrong_value in mutations:
        value = deepcopy(original)
        target = value
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = wrong_value
        wrong = (b''.join((json.dumps(frame) + '\n').encode() for frame in value)
                 if session else json.dumps(value).encode())
        try:
            verify(case, status, wrong, err, work, data, offset)
        except AssertionError:
            rejected.append(case['id'] + '-' + name + '-rejected')
        else:
            raise AssertionError('false-report oracle mutation accepted: ' + name)
    if case['operation'] == 'extraction':
        output = work / inputs(case)[2]
        for other in ('ThumbnailImage', 'JpgFromRaw'):
            output.write_bytes(PREVIEWS[other])
            try:
                try:
                    verify(case, status, out, err, work, data, offset)
                except AssertionError:
                    rejected.append(case['id'] + '-wrong-' + other + '-bytes-rejected')
                else:
                    raise AssertionError('wrong extracted resource accepted: ' + other)
            finally:
                output.write_bytes(PREVIEWS['PreviewImage'])
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--shell', type=Path)
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    assert PLATFORM, 'declared platforms: Windows, Linux, macOS'
    binary = args.binary.resolve(strict=True)
    shell_kind = 'powershell' if os.name == 'nt' else 'bash'
    shell = str(args.shell.resolve(strict=True)) if args.shell else shutil.which(
        'pwsh' if os.name == 'nt' else 'bash')
    assert shell, 'declared shell unavailable'
    cases = json.loads(LEDGER.read_text(encoding='utf-8'))['cases']
    assert len(cases) == 32 and len({case['id'] for case in cases}) == 32
    for op in ('extraction', 'date-preview', 'pair', 'session'):
        assert sum(case['operation'] == op for case in cases) == 8
    scratch = ROOT / '.local/command-shells'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=scratch)).resolve()
    captures = folder / 'captures'
    captures.mkdir()
    version = ([shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command',
                '$PSVersionTable.PSVersion.ToString()'] if os.name == 'nt' else [shell, '--version'])
    status, out, err = run(version, ROOT, captures / 'shell-version')
    assert status == 0 and not err
    shell_version = out.decode('utf-8').splitlines()[0]
    assert shell_version.startswith('7.' if os.name == 'nt' else 'GNU bash, version ')
    data = fixture(folder, captures)
    offset = data.index(b'2026:01:02 03:04:05\0')
    sources = ['src/cli.rs', 'src/app.rs', 'src/read_session.rs', 'src/read_request.rs',
               'src/preview.rs', 'src/pairing.rs', 'src/reader/wire.rs', 'Cargo.lock',
               'tests/support/mod.rs', 'scripts/check_read_arguments.py',
               'scripts/check_preview_pair_arguments.py', 'scripts/check_native_paths.py']
    report = dict(schemaVersion=1, ticket=137, platform=PLATFORM,
                  observedAtUtc=datetime.now(timezone.utc).isoformat(),
                  osRelease=platform.release(), shell=shell_kind, shellVersion=shell_version,
                  binarySha256=sha(binary), checkerSha256=sha(Path(__file__)),
                  ledgerSha256=sha(LEDGER), witnessSha256=sha(PACKAGE / 'argv_witness.py'),
                  sourceSha256={name: sha(ROOT / name) for name in sources},
                  fixtureSha256=hashlib.sha256(data).hexdigest(), cases=[], oracleControls=[])
    for case in cases:
        if PLATFORM not in case['platforms']:
            report['cases'].append(dict(id=case['id'], state='not-applicable'))
            continue
        work = folder / case['id']
        work.mkdir()
        source, sidecar, output, argv, payload = inputs(case)
        (work / source).write_bytes(data)
        (work / sidecar).write_bytes(b'authored opaque sidecar; not parsed')
        (work / 'decoy.cr3').write_bytes(b'wrong-input decoy')
        before = inventory(work)
        witness = captures / (case['id'] + '.argv.json')
        script_path = captures / (case['id'] + ('.ps1' if os.name == 'nt' else '.bash'))
        script_path.write_text(script(binary, argv, shell_kind, witness, payload),
                               encoding='utf-8', newline='\n')
        launch = ([shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(script_path)]
                  if os.name == 'nt' else [shell, '--noprofile', '--norc', str(script_path)])
        try:
            status, out, err = run(launch, work, captures / case['id'])
            observed = json.loads(witness.read_text(encoding='utf-8'))
            assert observed['argv'] == argv, 'shell argv differs from independent literal binding'
            stdin = bytes.fromhex(observed['stdinHex'])
            expected_stdin = b'' if payload is None else (payload + '\n').encode('utf-8')
            # PowerShell native pipeline encodes each string as UTF-8 plus platform newline.
            if os.name == 'nt' and payload is not None:
                expected_stdin = (payload + '\r\n').encode('utf-8')
            assert stdin == expected_stdin, 'shell input differs from exact authored binding'
            verify(case, status, out, err, work, data, offset)
            if case['id'].endswith('01'):
                report['oracleControls'].extend(reject_false_reports(
                    case, status, out, err, work, data, offset))
            after = inventory(work)
            if case['operation'] == 'extraction':
                assert after.keys() == before.keys() | {output}
                after.pop(output)
            assert after == before, 'source/sidecar/decoy identity, properties or bytes changed'
            result = dict(id=case['id'], state='passed', argv=argv, status=status,
                          stdinSha256=observed['stdinSha256'], stdinBytes=len(stdin),
                          stdoutBytes=len(out), stderrBytes=len(err),
                          shellScriptSha256=sha(script_path),
                          beforeInventory=before, afterInventory=inventory(work),
                          classification='advisory-refusal' if case['operation'] == 'date-preview'
                          else 'named-boundary-refusal' if case.get('code')
                          else 'positive-authored-operation')
        except Exception as error:
            result = dict(id=case['id'], state='failed', failure=str(error))
        report['cases'].append(result)
        (folder / 'results.json').write_text(json.dumps(report, indent=2, ensure_ascii=True)
                                            + '\n', encoding='utf-8', newline='\n')
    failures = [case for case in report['cases'] if case['state'] == 'failed']
    print(json.dumps(dict(platform=PLATFORM, cases=sum(c['state'] != 'not-applicable'
                     for c in report['cases']), failures=failures, retained=str(folder))))
    if not failures and args.public_results:
        # Native identity/time inventories are retained privately; publish equality and effects.
        for case in report['cases']:
            if case['state'] == 'passed':
                case.pop('beforeInventory')
                case.pop('afterInventory')
                case['effects'] = ('exact-new-preview-only' if case['id'].startswith('CS-E')
                                   else 'unchanged-byte-name-property-identity-inventory')
        args.public_results.write_text(json.dumps(report, indent=2, ensure_ascii=True)
                                       + '\n', encoding='utf-8', newline='\n')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())

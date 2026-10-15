"""Exact capture comparison; caller must retain the returned private ledger.

No field-name, platform, path or filesystem normalization is implicit. Exclusions
are exact JSON pointers declared before execution; their values remain recorded.
This compares observations, not independent correctness or media usability.
"""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import argparse
import re


class Refused(ValueError):
    pass


def verify_descriptor(descriptor):
    """Rehash an explicitly named artifact; never trust a ledger's boolean."""
    path = Path(descriptor['path'])
    digest = hashlib.sha256()
    length = 0
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            length += len(block)
            digest.update(block)
    if (str(length) != str(descriptor['byteLength']) or
            digest.hexdigest() != descriptor['sha256']):
        raise Refused('Artifact descriptor mismatch')
    return path


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refused('Duplicate JSON member')
            result[key] = value
        return result

    def constant(_value):
        raise Refused('Nonfinite JSON number')

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant,
                      parse_float=Decimal)


def json_safe(value):
    """Retain exact decimal evidence without binary-float serialization loss."""
    if isinstance(value, Decimal):
        return {'kind': 'exact-json-decimal', 'text': str(value)}
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def pointer_part(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def differences(left, right, path=''):
    """Preserve array order, object membership and primitive JSON types."""
    # JSON has one numeric kind. Decimal avoids rounding, and bool must remain
    # distinct despite Python's bool subclassing int.
    if type(left) in (int, Decimal) and type(right) in (int, Decimal):
        return [] if left == right else [{'path': path, 'kind': 'value', 'left': left, 'right': right}]
    if type(left) is not type(right):
        return [{'path': path, 'kind': 'type', 'left': left, 'right': right}]
    result = []
    if isinstance(left, dict):
        for key in sorted(left.keys() | right.keys()):
            child = path + '/' + pointer_part(key)
            if key not in left:
                result.append({'path': child, 'kind': 'right-only', 'right': right[key]})
            elif key not in right:
                result.append({'path': child, 'kind': 'left-only', 'left': left[key]})
            else:
                result.extend(differences(left[key], right[key], child))
    elif isinstance(left, list):
        if len(left) != len(right):
            # Retain full arrays: missing occurrences must not shift-match silently.
            result.append({'path': path, 'kind': 'array-length', 'left': left, 'right': right})
        else:
            for index, (a, b) in enumerate(zip(left, right)):
                result.extend(differences(a, b, path + '/' + str(index)))
    elif left != right:
        result.append({'path': path, 'kind': 'value', 'left': left, 'right': right})
    return result


def pointer_value(document, pointer):
    if pointer == '':
        return document
    if not pointer.startswith('/'):
        raise Refused('Exclusion must be an exact JSON pointer')
    current = document
    for part in pointer[1:].split('/'):
        # Reject noncanonical escaping rather than aliasing two declarations.
        token = part.replace('~1', '/').replace('~0', '~')
        if pointer_part(token) != part:
            raise Refused('Invalid JSON pointer escape')
        if isinstance(current, list):
            if not token.isdigit() or str(int(token)) != token:
                raise Refused('Invalid array index')
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise Refused('Pointer traverses a scalar')
    return current


def compare_capture(left, right, kind, exclusions=()):
    """Compare bytes or strict JSON, retaining every excluded observation.

    Exclusions are mappings with exact ``path`` and nonempty ``reason``. Each
    must resolve on both sides. Whole-document exclusions are refused. The caller
    owns checking a pre-execution policy hash; this helper does not attest timing.
    """
    result = {'kind': kind, 'byteEqual': left == right,
              'leftSha256': hashlib.sha256(left).hexdigest(),
              'rightSha256': hashlib.sha256(right).hexdigest()}
    if kind == 'bytes':
        if exclusions:
            raise Refused('Binary comparisons cannot exclude bytes')
        return {**result, 'equalAfterDeclaredExclusions': left == right,
                'excluded': [], 'differences': [] if left == right else
                [{'kind': 'bytes', 'leftLength': len(left), 'rightLength': len(right)}]}
    if kind != 'json':
        raise Refused('Unknown capture comparison kind')
    a, b = strict_json(left), strict_json(right)
    declared = {}
    observed = []
    for item in exclusions:
        path, reason = item['path'], item['reason']
        if not path or path in declared or not isinstance(reason, str) or not reason.strip():
            raise Refused('Invalid or duplicate exclusion')
        try:
            av, bv = pointer_value(a, path), pointer_value(b, path)
        except (KeyError, IndexError) as error:
            raise Refused('Exclusion absent from one capture') from error
        if isinstance(av, (dict, list)) or isinstance(bv, (dict, list)):
            raise Refused('Exclusions must name scalar observations')
        declared[path] = reason
        observed.append({'path': path, 'reason': reason, 'left': av, 'right': bv})
    delta = differences(a, b)
    retained = [item for item in delta if item['path'] not in declared]
    return {**result, 'equalAfterDeclaredExclusions': not retained,
            'excluded': observed, 'differences': retained}


def audit_ledger(ledger_path):
    """Independently recompute a completed replay's private comparisons."""
    ledger_path = Path(ledger_path).resolve()
    ledger = strict_json(ledger_path.read_bytes())
    if ledger['schemaVersion'] != 1 or ledger['completed'] is not True:
        raise Refused('Incomplete replay')
    for name in ('environment', 'policy', 'sourceManifest', 'baselineOracle',
                 'baselineIndex', 'runner', 'selectionManifest', 'probes'):
        verify_descriptor(ledger[name])
    environment = strict_json(Path(ledger['environment']['path']).read_bytes())
    policy = strict_json(Path(ledger['policy']['path']).read_bytes())
    if policy['exclusions'] != []:
        raise Refused('This audit requires the declared empty exclusion policy')
    if policy['declaredAt'] > ledger['startedAt']:
        raise Refused('Policy was declared after replay start')
    if not environment['uname'][0] == 'Linux' or '5.32.1' in environment['perlConfig']:
        raise Refused('Second runtime not demonstrated')
    if any(environment['environment'].get(key) != value for key, value in
           {'LC_ALL': 'C', 'LC_CTYPE': 'C', 'LANG': 'C', 'TZ': 'UTC0'}.items()):
        raise Refused('Declared locale/timezone controls differ')
    for name in ('runtime', 'source'):
        if environment[name + 'Before'] != environment[name + 'After']:
            raise Refused('Component inventory changed')
        for artifact in environment[name + 'After']:
            verify_descriptor(artifact)
    verify_descriptor(environment['driver'])
    verify_descriptor(environment['driverAfter'])
    if environment['driver'] != environment['driverAfter']:
        raise Refused('Observer changed during replay')
    verify_descriptor(environment['configurationSentinel'])
    probes = strict_json(Path(ledger['probes']['path']).read_bytes())
    hostile_observed = False
    suppressed_observed = False
    for probe in probes:
        verify_descriptor(probe['stdout'])
        verify_descriptor(probe['stderr'])
        stderr = Path(probe['stderr']['path']).read_bytes()
        stdout = Path(probe['stdout']['path']).read_bytes()
        if not probe['startedAt'] <= probe['finishedAt'] <= ledger['startedAt']:
            raise Refused('Setup probe chronology differs')
        if b'imageinfo_config_sentinel' in stderr:
            hostile_observed = True
        elif probe['termination'] != {'kind': 'exit', 'code': 0}:
            raise Refused('Unexpected setup probe failure')
        if ('-config' in probe['arguments'] and stdout.strip() == b'13.59' and
                not stderr and probe['termination'] == {'kind': 'exit', 'code': 0}):
            suppressed_observed = True
    if not hostile_observed or not suppressed_observed or environment['configurationSuppressionVerified'] is not True:
        raise Refused('Configuration suppression probes are incomplete')
    def linux_path(value):
        if re.match(r'^[A-Za-z]:[\\/]', value):
            return str(Path('/mnt') / value[0].lower() / value[3:].replace('\\', '/'))
        return value

    manifest = strict_json(Path(ledger['sourceManifest']['path']).read_bytes())
    source_root = Path(linux_path(manifest['root']))
    expected_source = {str((source_root / entry['path']).resolve()):
                       (entry['sha256'], str(entry['byteLength'])) for entry in manifest['files']}
    actual_source = {entry['path']: (entry['sha256'], str(entry['byteLength']))
                     for entry in environment['sourceBefore']}
    if expected_source != actual_source:
        raise Refused('Pinned source manifest membership differs')
    records_root = Path(ledger['baselineOracle']['path']).parent
    selected = strict_json(Path(ledger['selectionManifest']['path']).read_bytes())
    if ledger['originalsBefore'] != ledger['originalsAfter']:
        raise Refused('Original source changed during replay')
    originals = {item['fixtureId']: item for item in ledger['originalsAfter']}
    if len(originals) != len(selected):
        raise Refused('Original source accounting differs')
    for item in selected:
        original = originals[item['id']]
        verify_descriptor(original)
        if (original['path'] != linux_path(item['privateSource']) or
                original['sha256'] != item['sha256'] or
                original['mtimeNs'] != item['sourceMtimeNs'] or
                original['mtimeNs'] != str(Path(original['path']).stat().st_mtime_ns)):
            raise Refused('Original acquisition binding differs')
    expected = []
    for path in (records_root / 'experiments').glob('*.json'):
        record = strict_json(path.read_bytes())
        if record['reference']['tool']['reportedVersion'] == '13.59':
            expected.append((path, record))
    expected.sort(key=lambda item: (item[1]['reference']['startedAt'], item[1]['id']))
    if [record['id'] for _, record in expected] != [item['id'] for item in ledger['attempts']]:
        raise Refused('Replay invocation set or order differs')
    fixture_ids = set()
    fixtures = {}
    for fixture in ledger['fixtures']:
        if fixture['id'] in fixture_ids:
            raise Refused('Duplicate fixture')
        fixture_ids.add(fixture['id'])
        fixtures[fixture['id']] = fixture
        verify_descriptor(fixture)
        verify_descriptor(fixture['manifest'])
        verify_descriptor(fixture['provenance'])
        if fixture['before'] != fixture['sha256'] or fixture['after'] != fixture['sha256']:
            raise Refused('Immutable fixture changed')
        provenance = strict_json(Path(fixture['provenance']['path']).read_bytes())
        permissions = provenance['rights']['permissions']
        if (provenance['review']['state'] != 'approved' or
                any(permissions[key] != 'allowed' for key in ('store', 'analyze')) or
                permissions['publishReports'] != 'denied'):
            raise Refused('Unexpected fixture grant')
    comparisons = []
    index = strict_json(Path(ledger['baselineIndex']['path']).read_bytes())
    roots = {name: Path(linux_path(value)) for name, value in index['roots'].items()}
    substitutions = {}
    for (_, record), attempt in zip(expected, ledger['attempts']):
        args = record['reference']['arguments']
        if '-o' in args:
            if len(attempt['outputs']) != 1:
                raise Refused('Generated artifact accounting differs')
            substitutions[linux_path(args[args.index('-o') + 1])] = attempt['outputs'][0]['path']
        if '-b' in args:
            capture = record['reference']['stdout']
            historical = str((roots[capture['root']] / capture['path']).resolve())
            substitutions[historical] = attempt['stdout']['path']
    source_paths = {item['path'] for item in environment['sourceAfter']}
    runtime_paths = {item['path'] for item in environment['runtimeAfter']}
    for attempt, (baseline_path, record) in zip(ledger['attempts'], expected):
        verify_descriptor(attempt['baselineRecord'])
        if Path(attempt['baselineRecord']['path']) != baseline_path.resolve():
            raise Refused('Baseline record binding differs')
        tool = record['reference']['tool']
        original_argv = record['reference']['arguments']
        expected_kind = ('api-json' if linux_path(original_argv[3]).endswith('/reference_api.pl')
                         else 'binary' if '-b' in original_argv
                         else 'write-status' if '-o' in original_argv else 'cli-json')
        if attempt['kind'] != expected_kind:
            raise Refused('Capture comparison kind differs')
        if (tool['sourceRevision'] != '2200871d9cef988051d2a99d67df3bda6cbb30a8' or
                tool['distributionManifest']['sha256'] != ledger['sourceManifest']['sha256']):
            raise Refused('Historical source binding differs')
        if attempt['kind'] == 'api-json' and tool['driver']['sha256'] != environment['driver']['sha256']:
            raise Refused('Historical observer driver binding differs')
        if attempt['termination'] != {'kind': 'exit', 'code': 0}:
            raise Refused('Replay attempt did not complete successfully')
        historical_args = [substitutions.get(linux_path(value), linux_path(value))
                           for value in record['reference']['arguments'][1:]]
        if attempt['arguments'][1:] != historical_args:
            raise Refused('Replay changed a command beyond declared path substitution')
        if str(Path(attempt['arguments'][0]).resolve()) not in runtime_paths:
            raise Refused('Invoked interpreter is outside runtime inventory')
        with Path(attempt['arguments'][0]).open('rb') as interpreter:
            if interpreter.read(4) != b'\x7fELF':
                raise Refused('Invoked interpreter is not a native Linux ELF executable')
        if not policy['declaredAt'] <= attempt['startedAt'] <= attempt['finishedAt']:
            raise Refused('Invalid attempt chronology')
        for name in ('stdout', 'stderr', 'baselineStdout', 'baselineStderr'):
            verify_descriptor(attempt[name])
        for stream in ('stdout', 'stderr'):
            historical_capture = record['reference'][stream]
            current_capture = attempt['baseline' + stream.capitalize()]
            if (current_capture['sha256'] != historical_capture['sha256'] or
                    str(current_capture['byteLength']) != str(historical_capture['byteLength']) or
                    current_capture['path'] != str((roots[historical_capture['root']] /
                                                   historical_capture['path']).resolve())):
                raise Refused('Historical capture binding differs')
        before, after = attempt['inputHashesBefore'], attempt['inputHashesAfter']
        baseline_inputs = record['reference']['inputHashesBefore']
        if not len(before) == len(after) == len(baseline_inputs):
            raise Refused('Input accounting differs')
        for a, b, historical in zip(before, after, baseline_inputs):
            verify_descriptor(a)
            verify_descriptor(b)
            if (a['fixtureId'] != b['fixtureId'] or a['path'] != b['path'] or
                    a['sha256'] != b['sha256'] or a['fixtureId'] != historical['fixtureId'] or
                    a['baselineSha256'] != historical['sha256']):
                raise Refused('Input identity or preservation differs')
            if not a['regenerated'] and a['sha256'] != historical['sha256']:
                raise Refused('Original input differs from historical binding')
            fixture = fixtures[a['fixtureId']]
            expected_path = substitutions.get(fixture['path'], fixture['path'])
            if (a['path'] != expected_path or a['regenerated'] != (expected_path != fixture['path']) or
                    a['matchesBaseline'] != (a['sha256'] == historical['sha256'])):
                raise Refused('Input path substitution differs')
        for artifact in attempt['outputs']:
            verify_descriptor(artifact)
        left = Path(attempt['baselineStdout']['path']).read_bytes()
        right = Path(attempt['stdout']['path']).read_bytes()
        replay_stderr = Path(attempt['stderr']['path']).read_bytes()
        if b'imageinfo_config_sentinel' in right or b'imageinfo_config_sentinel' in replay_stderr:
            raise Refused('Replay configuration suppression failed')
        mode = 'json' if attempt['kind'] in ('api-json', 'cli-json') else 'bytes'
        stdout = compare_capture(left, right, mode)
        stderr = compare_capture(Path(attempt['baselineStderr']['path']).read_bytes(),
                                 replay_stderr, 'bytes')
        if attempt['kind'] == 'api-json':
            observation = strict_json(right)
            if observation['version'] != '13.59':
                raise Refused('API version differs')
            for module, path in observation['loadedModules'].items():
                path = str(Path(path).resolve())
                if path not in source_paths | runtime_paths:
                    raise Refused('Loaded module is outside inventoried components')
                if module.startswith('Image/ExifTool') and path not in source_paths:
                    raise Refused('ExifTool module loaded outside pinned tree')
        comparisons.append({'id': attempt['id'], 'stdout': stdout, 'stderr': stderr})
    auditor = Path(__file__).resolve()
    return {'schemaVersion': 1, 'kind': 'private-reference-replay-audit',
            'auditor': {'path': str(auditor), 'sha256': hashlib.sha256(auditor.read_bytes()).hexdigest(),
                        'byteLength': str(auditor.stat().st_size)},
            'ledger': {'path': str(ledger_path), 'sha256': hashlib.sha256(ledger_path.read_bytes()).hexdigest()},
            'policy': ledger['policy'], 'exclusions': [], 'comparisons': comparisons,
            'limits': 'Reference repeatability only; all differences retained; no independent media validation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    destination = options.output.resolve()
    if '.local' not in destination.parts or destination.exists():
        raise Refused('Use a fresh private .local output path')
    report = audit_ledger(options.ledger)
    destination.write_text(json.dumps(json_safe(report), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

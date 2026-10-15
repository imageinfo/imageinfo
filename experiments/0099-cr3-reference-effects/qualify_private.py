"""Private reference-write characterization; never a production mutation path.

All camera-derived records, including aggregate findings, remain in the explicit
private root. There is deliberately no public-report output option.
"""
import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

MAX_SOURCE = 256 * 1024 * 1024
MAX_SOURCES = 8  # Declared workload cap, not a camera-derived result.
MAX_BOXES = 4096
MAX_ENTRIES = 4096
MAX_RUNS = 65536
MAX_RUN_SAMPLES = 256
DATE = b'2001:02:03 04:05:06\0'
CANON = bytes.fromhex('85c0b687820f11e08111f4ce462b6a48')
WIDTHS = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1,
          8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}


class Refused(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def read_json(path):
    return strict_json(Path(path).read_text(encoding='utf-8'))


def strict_json(text):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique)


def checked(offset, length, end):
    require(offset >= 0 and length >= 0 and offset + length <= end, 'Out-of-bounds range')
    return offset, offset + length


def layout(data):
    """Bounded independent BMFF/CMT allocation inventory, not semantic decoding."""
    require(len(data) <= MAX_SOURCE, 'Source exceeds 256 MiB')
    boxes = []
    allocations = []
    structures = []

    def scan(start, end, parents, depth):
        require(depth <= 16, 'Box nesting ceiling')
        position = start
        counts = Counter()
        while position < end:
            require(len(boxes) < MAX_BOXES, 'Box count ceiling')
            checked(position, 8, end)
            size, kind = struct.unpack_from('>I4s', data, position)
            header = 8
            if size == 1:
                checked(position, 16, end)
                size = struct.unpack_from('>Q', data, position + 8)[0]
                header = 16
            elif size == 0:
                size = end - position
            require(size >= header, 'Invalid BMFF size')
            _, finish = checked(position, size, end)
            name = kind.decode('latin1')
            path = parents + [(name, counts[name])]
            counts[name] += 1
            body = position + header
            box = {'kind': name, 'start': position, 'body': body, 'end': finish,
                   'path': path, 'canon': False}
            boxes.append(box)
            structures.append((position, body, 'bmff-header'))
            if kind == b'moov':
                scan(body, finish, path, depth + 1)
            elif kind == b'uuid':
                checked(body, 16, finish)
                if data[body:body + 16] == CANON:
                    box['canon'] = True
                    structures.append((body, body + 16, 'canon-uuid-header'))
                    scan(body + 16, finish, path, depth + 1)
            elif kind in (b'CMT1', b'CMT2', b'CMT3', b'CMT4'):
                require(any(p[0] == 'uuid' for p in parents), 'CMT outside UUID')
                allocations.extend(tiff_inventory(data, body, finish, name, structures))
            position = finish
        require(position == end, 'Box extent mismatch')

    scan(0, len(data), [], 0)
    targets = [a for a in allocations if a['block'] == 'CMT2' and a['tag'] == 0x9003]
    require(len(targets) == 1, 'Expected unique existing CMT2 DateTimeOriginal')
    target = targets[0]
    require(target['format'] == 2 and target['length'] == 20, 'Expected ASCII20 date')
    require(data[target['offset']:target['offset'] + 20][-1] == 0, 'Missing date terminator')
    for allocation in allocations:
        if allocation is not target:
            require(not overlaps(target['offset'], target['offset'] + 20,
                                 allocation['offset'], allocation['offset'] + allocation['length']),
                    'Unselected allocation aliases the date')
    for start, end, _ in structures:
        require(not overlaps(target['offset'], target['offset'] + 20, start, end),
                'Date overlaps a structure')
    return {'boxes': boxes, 'allocations': allocations, 'structures': structures, 'target': target}


def tiff_inventory(data, base, end, block, structures):
    checked(base, 8, end)
    order = {b'II': '<', b'MM': '>'}.get(bytes(data[base:base + 2]))
    require(order is not None, 'Unknown TIFF byte order')
    require(struct.unpack_from(order + 'H', data, base + 2)[0] == 42, 'Invalid TIFF magic')
    structures.append((base, base + 8, block + '-tiff-header'))
    pending = [(struct.unpack_from(order + 'I', data, base + 4)[0], 0)]
    visited = set()
    result = []
    while pending:
        relative, depth = pending.pop()
        if relative == 0:
            continue
        require(depth <= 16 and relative not in visited, 'Cyclic/deep TIFF directory')
        visited.add(relative)
        directory = base + relative
        checked(directory, 2, end)
        count = struct.unpack_from(order + 'H', data, directory)[0]
        require(count <= MAX_ENTRIES and len(result) + count <= MAX_ENTRIES, 'TIFF entry ceiling')
        _, table_end = checked(directory, 6 + count * 12, end)
        structures.append((directory, table_end, block + '-ifd-table'))
        for index in range(count):
            entry = directory + 2 + index * 12
            tag, kind, number, value = struct.unpack_from(order + 'HHII', data, entry)
            require(kind in WIDTHS, 'Unknown TIFF storage width')
            length = WIDTHS[kind] * number
            offset = entry + 8 if length <= 4 else base + value
            checked(offset, length, end)
            result.append({'block': block, 'ifd': relative, 'ordinal': index, 'tag': tag,
                           'format': kind, 'count': number, 'offset': offset, 'length': length,
                           'byteOrder': 'little' if order == '<' else 'big'})
            if tag in (0x8769, 0x8825, 0xa005):
                require(kind == 4 and number == 1, 'Unsupported directory pointer')
                pending.append((value, depth + 1))
        pending.append((struct.unpack_from(order + 'I', data, table_end - 4)[0], depth + 1))
    return result


def overlaps(a, b, c, d):
    return a < d and c < b


def iter_differing_runs(before, after):
    """Exact runs at common offsets; unequal suffixes are explicit length effects."""
    opened = None
    common = min(len(before), len(after))
    for block in range(0, common, 65536):
        end = min(common, block + 65536)
        if before[block:end] == after[block:end]:
            if opened is not None:
                yield opened, block - opened
                opened = None
            continue
        for position in range(block, end):
            if before[position] != after[position]:
                if opened is None:
                    opened = position
            elif opened is not None:
                yield opened, position - opened
                opened = None
    if opened is not None:
        yield opened, common - opened
    if len(before) != len(after):
        yield common, max(len(before), len(after)) - common


def differing_runs(before, after):
    """Full-list helper for bounded authored controls, not private large reports."""
    result = []
    for run in iter_differing_runs(before, after):
        require(len(result) < MAX_RUNS, 'Differing-run ceiling')
        result.append(run)
    return result


def summarize_runs(before, after, sample_limit=MAX_RUN_SAMPLES):
    """Consume every run, retain bounded samples and hash the complete sequence."""
    samples, count, changed = [], 0, 0
    digest = hashlib.sha256()
    for offset, length in iter_differing_runs(before, after):
        digest.update(struct.pack('>QQ', offset, length))
        count += 1
        changed += length
        if len(samples) < sample_limit:
            samples.append((offset, length))
    return {'runCount': count, 'changedBytes': changed, 'samples': samples,
            'retainedRunListComplete': count <= sample_limit,
            'completeRunSequenceSha256': digest.hexdigest(),
            'runSequenceEncoding': 'ordered-u64be-offset-u64be-length-v1'}


def partition(data, inventory):
    """Account for every file byte exactly once without overlapping parents."""
    regions = []
    for box in inventory['boxes']:
        key = tuple(tuple(part) for part in box['path'])
        regions.append((box['start'], box['body'], (key, 'header')))
        if box['canon']:
            regions.append((box['body'], box['body'] + 16, (key, 'uuid-prefix')))
        elif box['kind'] != 'moov' and box['body'] < box['end']:
            regions.append((box['body'], box['end'], (key, 'payload')))
    regions.sort()
    position = 0
    for start, end, _ in regions:
        require(start == position, 'Independent partition has gaps/overlap')
        position = end
    require(position == len(data), 'Independent partition does not cover complete file')
    require(len({key for _, _, key in regions}) == len(regions), 'Duplicate partition key')
    return {key: (start, end) for start, end, key in regions}


def aligned_regions(before, after, old_inventory, new_inventory):
    old, new = partition(before, old_inventory), partition(after, new_inventory)
    result = []
    for key in sorted(old.keys() | new.keys()):
        left, right = old.get(key), new.get(key)
        old_bytes = before[left[0]:left[1]] if left else b''
        new_bytes = after[right[0]:right[1]] if right else b''
        equal = old_bytes == new_bytes and left is not None and right is not None
        result.append({'path': key[0], 'part': key[1],
                       'sourceRange': left, 'candidateRange': right,
                       'contentEqual': equal,
                       'equalContentMoved': equal and left != right,
                       'sourceSha256': hashlib.sha256(old_bytes).hexdigest() if left else None,
                       'candidateSha256': hashlib.sha256(new_bytes).hexdigest() if right else None,
                       'relativeByteChanges': None if equal else summarize_runs(old_bytes, new_bytes)})
    return result


def labels(offset, length, inventory):
    end = offset + length
    found = set()
    target = inventory['target']
    if overlaps(offset, end, target['offset'], target['offset'] + target['length']):
        found.add('selected-date-allocation')
    for a in inventory['allocations']:
        if a is not target and overlaps(offset, end, a['offset'], a['offset'] + a['length']):
            found.add('other-' + a['block'] + '-allocation')
    for start, finish, name in inventory['structures']:
        if overlaps(offset, end, start, finish):
            found.add(name)
    for box in inventory['boxes']:
        if box['kind'] == 'mdat' and overlaps(offset, end, box['body'], box['end']):
            found.add('mdat-payload')
    return sorted(found or {'other-or-unmapped-bytes'})


def compare(before, after, old_inventory, new_inventory):
    run_summary = summarize_runs(before, after)
    target = old_inventory['target']
    exact_fixed_patch = (len(before) == len(after)
                         and before[:target['offset']] == after[:target['offset']]
                         and before[target['offset'] + 20:] == after[target['offset'] + 20:]
                         and after[target['offset']:target['offset'] + 20] == DATE)

    def mdats(data, inventory):
        return [hashlib.sha256(data[b['body']:b['end']]).hexdigest()
                for b in inventory['boxes'] if b['kind'] == 'mdat']

    return {'beforeLength': len(before), 'afterLength': len(after),
            'exactFixedDatePatch': exact_fixed_patch,
            'mdatPayloadsEqualInOrder': mdats(before, old_inventory) == mdats(after, new_inventory),
            'completePositionalSummary': {key: value for key, value in run_summary.items() if key != 'samples'},
            'runSampleLimit': MAX_RUN_SAMPLES,
            'runs': [{'offset': at, 'length': size,
                      'sourceClasses': labels(at, size, old_inventory),
                      'candidateClasses': labels(at, size, new_inventory)} for at, size in run_summary['samples']],
            'alignedRegions': aligned_regions(before, after, old_inventory, new_inventory)}


def metadata_changes(before, after):
    changes = []
    for key in sorted(before.keys() | after.keys()):
        if before.get(key) == after.get(key) and (key in before) == (key in after):
            continue
        category = ('source-locator' if key == 'SourceFile' else
                    'filesystem-observation' if ':System:' in key else
                    'derived-composite' if key.startswith('Composite:') else 'stored-or-other')
        changes.append({'key': key, 'class': category,
                        'beforePresent': key in before, 'afterPresent': key in after,
                        'before': before.get(key), 'after': after.get(key)})
    return changes


def fingerprint(path):
    path = Path(path)
    return sha(path), path.stat().st_mtime_ns


def run_tool(root, name, argv, inputs, records, env, timeout=120):
    before = {str(p): fingerprint(p) for p in inputs}
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    process = subprocess.run([str(arg) for arg in argv], capture_output=True,
                             timeout=timeout, env=env, cwd=root)
    require(before == {str(p): fingerprint(p) for p in inputs}, 'Tool changed an existing input')
    stdout, stderr = root / (name + '.stdout'), root / (name + '.stderr')
    stdout.write_bytes(process.stdout)
    stderr.write_bytes(process.stderr)
    records.append({'id': name, 'argv': [str(arg) for arg in argv], 'startedAt': started,
                    'exitCode': process.returncode, 'inputsBefore': before,
                    'stdoutSha256': sha(stdout), 'stderrSha256': sha(stderr)})
    dump(root / 'runs.private.json', records)
    return process


def validate_grants(manifest, repository):
    """Bind every actual source to the revised #21 differential admission."""
    reviews = []
    require(1 <= len(manifest['sources']) <= MAX_SOURCES, 'Expected 1..8 explicitly admitted sources')
    for source in manifest['sources']:
        fixture_path = repository / '.local/candidate-preservation-20261011-publish/records/fixtures' / (source['id'] + '.json')
        review_path = repository / '.local/candidate-preservation-20261011-publish/records/provenance' / ('PV-' + source['id'] + '.json')
        fixture, review = read_json(fixture_path), read_json(review_path)
        require(fixture['admission'] == 'admitted' and fixture['artifact']['sha256'] == source['sha256'], 'Source admission binding mismatch')
        require({'reference-characterization', 'differential'} <= set(fixture['allowedPhases']), 'Missing source phase')
        require(fixture['rights']['analyze'] and fixture['rights']['modify'], 'Missing private derivative rights')
        require(review['review']['state'] == 'approved', 'Source review not approved')
        permissions = review['rights']['permissions']
        require(permissions['analyze'] == permissions['modify'] == 'allowed', 'Missing reviewed private rights')
        require(permissions['publishReports'] == 'denied', 'This driver is scoped to private-only results')
        require(fingerprint(source['path'])[0] == source['sha256'], 'Source hash changed')
        require(Path(source['baselineDecoded']).is_file(), 'Prior independently decoded baseline missing')
        baseline_record = read_json(fixture_path.with_name(source['id'] + '-baseline-PGM.json'))
        require(sha(source['baselineDecoded']) == baseline_record['artifact']['sha256'], 'Decoded baseline identity changed')
        reviews.append({'id': source['id'], 'fixturePath': str(fixture_path), 'fixtureSha256': sha(fixture_path),
                        'reviewPath': str(review_path), 'reviewSha256': sha(review_path),
                        'sourceSha256': source['sha256'], 'baselineDecodedSha256': sha(source['baselineDecoded']),
                        'publishReports': 'denied'})
    return reviews


def verify_distribution(manifest_path, expected_hash):
    require(sha(manifest_path) == expected_hash, 'Distribution manifest identity changed')
    manifest = read_json(manifest_path)
    root = Path(manifest['root']).resolve()
    for entry in manifest['files']:
        path = (root / entry['path']).resolve()
        require(path.is_relative_to(root), 'Distribution entry escapes its root')
        require(path.is_file() and sha(path) == entry['sha256'], 'Distribution component changed')
        require(path.stat().st_size == int(entry['byteLength']), 'Distribution component length changed')
    return {'path': str(manifest_path), 'sha256': expected_hash,
            'root': str(root), 'verifiedFileCount': len(manifest['files'])}


def validate_tool_closures(repository, manifest, guard):
    oracle = read_json(repository / '.local/corpus/records/oracle-13.59.json')
    require(oracle['tool']['reportedVersion'] == '13.59', 'Unexpected reference version')
    tool_root = repository / '.local/tools'
    bindings = [oracle['tool']['distributionManifest']]
    bindings.extend(item['identityArtifact'] for item in oracle['tool']['runtimeComponents'])
    closures = [verify_distribution(tool_root / binding['path'], binding['sha256']) for binding in bindings]
    require(Path(manifest['reference']['path']).resolve().parent == Path(closures[0]['root']), 'Reference launcher is outside pinned source tree')
    require(Path(manifest['perl']['path']).resolve().parent == Path(closures[1]['root']), 'Interpreter is outside pinned runtime tree')
    reviewed = read_json(repository / '.local/candidate-preservation-20261011-publish/tool-identities.private.json')['libraw']
    decoder_root = Path(manifest['decoder']['path']).parent.parent
    for entry in reviewed['files']:
        require(sha(decoder_root / entry['path']) == entry['sha256'], 'Reviewed LibRaw component/notice changed')
    closures.append({'name': 'LibRaw', 'version': reviewed['version'], 'root': str(decoder_root), 'files': reviewed['files']})
    closures.append({'name': 'source-guard', 'path': str(guard), 'sha256': sha(guard),
                     'sourcePath': str(repository / 'experiments/0021-cr3-candidate/src/bin/source_guard.rs'),
                     'sourceSha256': sha(repository / 'experiments/0021-cr3-candidate/src/bin/source_guard.rs')})
    return closures


def qualify(manifest_path, root, guard, repository):
    require(os.name == 'nt', 'Actual run requires the researched Windows source-share guard')
    require(root.is_dir() and not root.is_symlink() and not list(root.iterdir()), 'Fresh private empty root required')
    require(shutil.disk_usage(root).free >= 8 * 1024 ** 3, 'Require 8 GiB free private scratch')
    manifest = read_json(manifest_path)
    grants = validate_grants(manifest, repository)
    closures = validate_tool_closures(repository, manifest, guard)
    tools = {name: manifest[name] for name in ('candidate', 'perl', 'reference', 'decoder')}
    for tool in tools.values():
        require(sha(tool['path']) == tool['sha256'], 'Pinned tool identity changed')
    # The caller has already applied owner-only inheritance to this fresh root.
    # Record the actual descriptor for audit; this helper never edits source ACLs.
    descriptor = subprocess.run(['icacls', str(root)], capture_output=True, check=True)
    (root / 'root-acl.private.txt').write_bytes(descriptor.stdout)
    (root / 'qualify_private.source.py').write_bytes(Path(__file__).read_bytes())
    dump(root / 'scoped-review.private.json', {
        'ticket': 99, 'basis': 'Current authorized #0099 plus Terry private metadata-analysis/test-derivative grant; revised #0021 phases bound below.',
        'scope': 'Pinned reference write into fresh private output may resize/rewrite; compare against native fixed patch and decoded baseline. Never alter originals or existing outputs.',
        'disclosure': 'All camera-derived results, counts, Boolean observations, values, hashes and inventories remain private; no public aggregate report.',
        'admissionManifest': {'path': str(manifest_path), 'sha256': sha(manifest_path)},
        'grants': grants, 'tools': tools, 'toolClosures': closures,
        'sourceGuard': {'path': str(guard), 'sha256': sha(guard)},
        'driverSha256': sha(root / 'qualify_private.source.py'),
        'methodRevision': '0099-reference-effects-2026-10-15.2',
        'productionMutationAllowed': False})
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if key in os.environ}
    env.update(PATH=str(Path(tools['perl']['path']).parent) + os.pathsep + str(Path(os.environ['SYSTEMROOT']) / 'System32'),
               PERL5LIB=manifest['perlLibrary'], LC_ALL='C', LANG='C', TZ='UTC0')
    dump(root / 'environment.private.json', env)
    records, results = [], []
    for source in manifest['sources']:
        path = Path(source['path'])
        original_fingerprint = fingerprint(path)
        holder = subprocess.Popen([str(guard), str(path)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            require(holder.stdout.readline() == b'guard-open\n', 'Source guard did not acquire')
            data = path.read_bytes()
            inventory = layout(data)
            field = inventory['target']
            require(data[field['offset']:field['offset'] + 20] != DATE, 'Source already has fixed date')
            prefix = source['id']
            native = root / (prefix + '.native.candidate.cr3')
            reference = root / (prefix + '.reference.cr3')
            require(not native.exists() and not reference.exists(), 'Candidate path already exists')

            def read_reference(label, input_path):
                process = run_tool(root, prefix + '-' + label,
                    [tools['perl']['path'], tools['reference']['path'], '-config', '', '-j', '-a', '-u', '-G0:1:4:5', '-s', '-n', '-api', 'RequestAll=3', input_path],
                    [path, input_path], records, env)
                require(process.returncode == 0 and not process.stderr, 'Reference read failed')
                values = strict_json(process.stdout)
                require(len(values) == 1, 'Unexpected reference row count')
                return values[0]

            before_values = read_reference('source-read', path)
            target_keys = [key for key in before_values if key.endswith(':DateTimeOriginal')]
            require(len(target_keys) == 1 and target_keys[0].startswith('EXIF:ExifIFD:'), 'Reference selector not unique exact ExifIFD date')
            require(before_values[target_keys[0]].encode('ascii') + b'\0' == data[field['offset']:field['offset'] + 20], 'Reference target differs from physical field')
            native_process = run_tool(root, prefix + '-native-stage', [tools['candidate']['path'], 'stage', path, native], [path], records, env)
            require(native_process.returncode == 0 and native.is_file(), 'Native candidate failed')
            require(strict_json(native_process.stdout).get('published') is False, 'Native stage did not report private-only candidate')
            require(native.stat().st_size <= MAX_SOURCE, 'Native candidate exceeds bound')
            native_bytes = native.read_bytes()
            native_layout = layout(native_bytes)
            native_comparison = compare(data, native_bytes, inventory, native_layout)
            require(native_comparison['exactFixedDatePatch'], 'Native candidate exceeded exact intent')
            write = run_tool(root, prefix + '-reference-write',
                [tools['perl']['path'], tools['reference']['path'], '-config', '', '-ExifIFD:DateTimeOriginal=' + DATE[:-1].decode('ascii'), '-o', reference, path],
                [path, native], records, env)
            result = {'id': prefix, 'sourceInventory': inventory, 'nativeComparison': native_comparison,
                      'referenceSelector': 'ExifIFD:DateTimeOriginal', 'referenceTargetKey': target_keys[0],
                      'referenceWriteExit': write.returncode, 'referenceOutputExists': reference.exists(),
                      'productionMutationAllowed': False, 'opaqueDependencyAbsenceEstablished': False}
            native_values = read_reference('native-read', native)
            result['nativeMetadataChanges'] = metadata_changes(before_values, native_values)
            if write.returncode != 0 or not reference.is_file():
                result['outcome'] = 'reference-write-refused-or-incomplete'
            else:
                require(reference.stat().st_size <= MAX_SOURCE, 'Reference output exceeds bound')
                reference_bytes = reference.read_bytes()
                reference_layout = layout(reference_bytes)
                result['referenceInventory'] = reference_layout
                result['referenceComparison'] = compare(data, reference_bytes, inventory, reference_layout)
                result['nativeReferenceBytesEqual'] = native_bytes == reference_bytes
                reference_values = read_reference('reference-read', reference)
                result['referenceMetadataChanges'] = metadata_changes(before_values, reference_values)
                result['nativeReferenceMetadataChanges'] = metadata_changes(native_values, reference_values)
                result['referenceTargetValueMatches'] = reference_values.get(target_keys[0]) == DATE[:-1].decode('ascii')
                result['outcome'] = 'reference-output-characterized'
                for label, candidate in [('native', native), ('reference', reference)]:
                    decoded = Path(str(candidate) + '.pgm')
                    require(not decoded.exists(), 'Decoded output collision')
                    process = run_tool(root, prefix + '-' + label + '-unpack', [tools['decoder']['path'], candidate], [path, native, reference], records, env)
                    require(process.returncode == 0 and not process.stderr and b'Unpacked' in process.stdout and decoded.is_file(), 'Independent RAW unpack incomplete')
                    result[label + 'DecodedBaselineEqual'] = sha(decoded) == sha(source['baselineDecoded'])
            require(original_fingerprint == fingerprint(path), 'Source content or mtime changed')
            results.append(result)
            dump(root / 'results.private.json', results)
            dump(root / 'directory-inventory.private.json', [p.name for p in root.iterdir()])
        finally:
            if holder.poll() is None:
                holder.communicate(b'release\n', timeout=10)
            require(holder.returncode == 0, 'Source guard did not exit cleanly')
    summary = {'ticket': 99, 'completedCases': len(results), 'runCount': len(records),
               'outcomes': dict(Counter(row['outcome'] for row in results)),
               'productionMutationAllowed': False, 'formatAdmissionEnabled': False,
               'publicReportsPermitted': False, 'resultsPrivateOnly': True}
    dump(root / 'summary.private.json', summary)
    dump(root / 'capture-manifest.private.json', {p.name: sha(p) for p in root.iterdir() if p.is_file()})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--guard', type=Path, required=True)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    qualify(args.manifest.resolve(), args.root.resolve(), args.guard.resolve(), args.repository.resolve())
    print('Private characterization finished; inspect the explicitly selected private root.')

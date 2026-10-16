"""Independent byte/dependency witness for authored #0113 controls.

This module never executes a writer or decoder and accepts no media input list.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import struct


MAX_BYTES = 65536
CANON = bytes.fromhex('85c0b687820f11e08111f4ce462b6a48')
WIDTHS = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1,
          8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
ORIGINAL = b'2001:02:03 04:05:06\0'
CHANGED = b'2007:08:09 10:11:12\0'
UNKNOWN = 0xdffe
INLINE = bytes.fromhex('91725334')
OUTLINE = b'AUTHORED-0113\0'
PINS = {'exiftool-13.59.json': 'b55345e4b02d221ffa4cc7c444858337329b433d2d4877ce7a6dc03cce2827ed',
        'installed-perl.json': '6f4eb552f97a25039ba1c786765a61cd6a1419f5837e75e25da0191f9e91e691',
        'json-pp.json': 'dcb168d2cb67fe46d6de6c540e23b0f97ac3fa7b7a6d04b8f0c0f28d6ecb1fb2'}


class Refused(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def bounded(start, length, end):
    require(0 <= start <= end and 0 <= length <= end - start,
            'Extent escapes container')
    return start + length


def parse_tiff(data, base=0, end=None):
    """Read TIFF ownership, including aliases; never infer semantic independence."""
    end = len(data) if end is None else end
    bounded(base, 8, end)
    order = {b'II': '<', b'MM': '>'}.get(data[base:base + 2])
    require(order is not None, 'Unknown TIFF byte order')
    require(struct.unpack_from(order + 'H', data, base + 2)[0] == 42,
            'Unsupported TIFF magic')
    first = struct.unpack_from(order + 'I', data, base + 4)[0]
    require(first != 0, 'Missing authored root directory')
    pending = [(first, ('root',))]
    seen, structures, values, entries = set(), [(base, base + 8)], [], []
    while pending:
        relative, route = pending.pop()
        require(relative not in seen and len(route) <= 8, 'Shared/cyclic/deep TIFF directory')
        seen.add(relative)
        start = base + relative
        bounded(start, 2, end)
        count = struct.unpack_from(order + 'H', data, start)[0]
        require(count <= 64 and len(entries) + count <= 128, 'TIFF entry ceiling')
        finish = bounded(start, 6 + 12 * count, end)
        structures.append((start, finish))
        duplicate = Counter()
        for index in range(count):
            at = start + 2 + 12 * index
            tag, kind, number = struct.unpack_from(order + 'HHI', data, at)
            require(kind in WIDTHS, 'Unknown TIFF storage width')
            length = number * WIDTHS[kind]
            pointer = struct.unpack_from(order + 'I', data, at + 8)[0]
            offset = at + 8 if length <= 4 else base + pointer
            bounded(offset, length, end)
            if length > 4:
                values.append((offset, offset + length))
            item = {'route': list(route), 'tag': tag, 'duplicate': duplicate[tag],
                    'type': kind, 'count': number, 'offset': offset,
                    'length': length, 'valueHex': data[offset:offset + length].hex()}
            entries.append(item)
            duplicate[tag] += 1
            if tag in (0x8769, 0x8825, 0xa005):
                require(kind == 4 and number == 1 and pointer != 0,
                        'Unsupported directory pointer')
                pending.append((pointer, route + (f'tag:{tag}:{item["duplicate"]}',)))
        following = struct.unpack_from(order + 'I', data, finish - 4)[0]
        if following:
            pending.append((following, route + ('next',)))
    for index, (start, finish) in enumerate(structures):
        require(all(finish <= other_start or other_end <= start
                    for other_start, other_end in structures[:index]),
                'Overlapping TIFF structures')
    for start, finish in values:
        require(all(finish <= other_start or other_end <= start
                    for other_start, other_end in structures),
                'Value overlaps TIFF structure')
    # A physical interval has one byte denominator and all logical owners. The
    # observer accepts aliases so it can measure whether a writer splits them;
    # this inspection policy never changes the native mutation refusal.
    owners = [(start, finish, f'structure:{index}')
              for index, (start, finish) in enumerate(structures)]
    owners += [(entry['offset'], entry['offset'] + entry['length'], f'value:{index}')
               for index, entry in enumerate(entries) if entry['length']]
    boundaries = sorted({base, end} | {point for start, finish, _ in owners
                                     for point in (start, finish)})
    partition, gaps = [], []
    for start, finish in zip(boundaries, boundaries[1:]):
        roles = sorted(name for left, right, name in owners if left <= start and finish <= right)
        item = {'offset': start, 'length': finish - start,
                'owners': roles, 'hex': data[start:finish].hex()}
        partition.append(item)
        if not roles:
            gaps.append({key: item[key] for key in ('offset', 'length', 'hex')})
    require(sum(item['length'] for item in partition) == end - base,
            'Incomplete TIFF physical partition')
    return {'order': order, 'base': base, 'end': end, 'entries': entries,
            'gaps': gaps, 'partition': partition}


def inspect(data):
    require(isinstance(data, bytes) and len(data) <= MAX_BYTES, 'Authored byte bound')
    boxes, cmts = [], {}

    def walk(start, end, route, depth):
        require(depth <= 8, 'BMFF nesting ceiling')
        counts = Counter()
        at = start
        while at < end:
            require(len(boxes) < 128, 'BMFF box ceiling')
            bounded(at, 8, end)
            size, kind = struct.unpack_from('>I4s', data, at)
            header = 8
            if size == 1:
                bounded(at, 16, end)
                size = struct.unpack_from('>Q', data, at + 8)[0]
                header = 16
            elif size == 0:
                size = end - at
            require(size >= header, 'Invalid BMFF length')
            finish = bounded(at, size, end)
            name = kind.decode('latin1')
            path = route + ((name, counts[name]),)
            counts[name] += 1
            body = at + header
            boxes.append({'path': path, 'kind': name, 'start': at,
                          'body': body, 'end': finish})
            if kind == b'moov':
                walk(body, finish, path, depth + 1)
            elif kind == b'uuid':
                bounded(body, 16, finish)
                require(data[body:body + 16] == CANON, 'Unknown authored UUID')
                walk(body + 16, finish, path, depth + 1)
            elif kind in (b'CMT1', b'CMT2', b'CMT3', b'CMT4'):
                require(route and route[-1][0] == 'uuid' and name not in cmts,
                        'Unbound or duplicate CMT directory')
                cmts[name] = parse_tiff(data, body, finish)
            at = finish
        require(at == end, 'Unconsumed BMFF bytes')

    walk(0, len(data), (), 0)
    require('CMT2' in cmts and 'CMT4' in cmts, 'Missing authored CMT directories')
    dates = [entry for entry in cmts['CMT2']['entries'] if entry['tag'] == 0x9003]
    require(len(dates) == 1 and dates[0]['type'] == 2 and dates[0]['count'] == 20,
            'Selected date is not one ASCII20 allocation')
    return {'boxes': boxes, 'cmts': cmts, 'selectedDateHex': dates[0]['valueHex']}


parse_fixture = inspect


def file_bytes(root, item):
    name = item['path']
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name
            and all(part not in ('', '.', '..') for part in name.split('/')),
            'Unsafe evidence member')
    target = (root / name).resolve()
    require(target.is_relative_to(root) and not (root / name).is_symlink(), 'Evidence path escapes root')
    require(target.is_file() and not target.is_symlink(), 'Evidence file missing/linked')
    require(target.stat().st_size <= MAX_BYTES, 'Evidence file exceeds bound')
    data = target.read_bytes()
    require(len(data) == item['size'] and digest(data) == item['sha256'],
            'Evidence bytes disagree with declared binding')
    return data


def identities(block):
    return {(tuple(entry['route']), entry['tag'], entry['duplicate'],
             entry['type'], entry['count']): entry['valueHex']
            for entry in block['entries']}


def verify_input(data, cell):
    observed = inspect(data)
    order = '<' if cell['order'] == 'II' else '>'
    require(set(observed['cmts']) == {'CMT2', 'CMT4'}
            and all(block['order'] == order for block in observed['cmts'].values()),
            'Authored directory/endian identity changed')
    expected = {(('root',), 0x9003, 0, 2, 20): ORIGINAL.hex()}
    shape = cell['storage']
    additions = {'baseline': {}, 'inline': {(('root',), UNKNOWN, 0, 7, 4): INLINE.hex()},
                 'outline': {(('root',), UNKNOWN, 0, 7, 14): OUTLINE.hex()},
                 'alias': {(('root',), UNKNOWN, 0, 2, 20): ORIGINAL.hex()},
                 'checksum': {(('root',), UNKNOWN, 0, 4, 1):
                              struct.pack(order + 'I', sum(ORIGINAL)).hex()}}
    require(shape in additions, 'Unknown declared authored shape')
    expected.update(additions[shape])
    require(identities(observed['cmts']['CMT2']) == expected,
            'Wrong invented CMT2 values/types/counts/identities')
    require(identities(observed['cmts']['CMT4']) ==
            {(('root',), 0, 0, 1, 4): '02030000'}, 'Wrong known companion values')
    for name, block in observed['cmts'].items():
        require(not block['gaps'], 'Unexpected authored unallocated storage')
        require(all(entry['route'] == ['root'] for entry in block['entries']),
                'Unexpected authored directory route')
    date = next(entry for entry in observed['cmts']['CMT2']['entries'] if entry['tag'] == 0x9003)
    unknown = [entry for entry in observed['cmts']['CMT2']['entries'] if entry['tag'] == UNKNOWN]
    if shape == 'alias':
        require(unknown[0]['offset'] == date['offset'], 'Declared alias is not shared storage')
    leaf = {box['kind']: data[box['body']:box['end']] for box in observed['boxes']
            if box['kind'] not in ('moov', 'uuid', 'CMT2', 'CMT4')}
    require(leaf == {'ftyp': b'crx \0\0\0\0crx ', 'CNCV': b'CanonCR3_0113\0'},
            'Unexpected authored leaf payload')
    require([box['kind'] for box in observed['boxes']] ==
            ['ftyp', 'moov', 'uuid', 'CNCV', 'CMT2', 'CMT4'], 'Unexpected authored topology')
    return observed


def alias_relationship(date, unknown):
    if unknown is None:
        return 'absent'
    left, right = date['offset'], unknown['offset']
    if (left, date['length']) == (right, unknown['length']):
        return 'exact-shared-storage'
    if left < right + unknown['length'] and right < left + date['length']:
        return 'partial-overlap'
    return 'separate-storage'


def compare_output(before, after, old, cell):
    new = inspect(after)
    require([box['path'] for box in old['boxes']] == [box['path'] for box in new['boxes']],
            'Output added/removed/reordered boxes')
    for left, right in zip(old['boxes'], new['boxes']):
        if left['kind'] not in ('moov', 'uuid', 'CMT2', 'CMT4'):
            require(before[left['body']:left['end']] == after[right['body']:right['end']],
                    'Unselected leaf payload changed')
    require(set(new['cmts']) == set(old['cmts']), 'Output directory identities changed')
    expected_date = ORIGINAL if cell['assignment'] == 'same' else CHANGED
    require(new['selectedDateHex'] == expected_date.hex(), 'Selected output date is wrong')
    require(identities(new['cmts']['CMT4']) == identities(old['cmts']['CMT4']),
            'Known companion value changed')
    require(new['cmts']['CMT4']['order'] == old['cmts']['CMT4']['order'],
            'Known companion byte order changed')
    source = old['cmts']['CMT2']
    target = new['cmts']['CMT2']
    require(target['order'] == source['order'], 'Output byte order changed')
    source_date = next(entry for entry in source['entries'] if entry['tag'] == 0x9003)
    target_date = next(entry for entry in target['entries'] if entry['tag'] == 0x9003)
    source_unknown = [entry for entry in source['entries'] if entry['tag'] == UNKNOWN]
    target_unknown = [entry for entry in target['entries'] if entry['tag'] == UNKNOWN]
    require(len(target_unknown) <= 1, 'Ambiguous output unknown entry')
    original = source_unknown[0] if source_unknown else None
    current = target_unknown[0] if target_unknown else None
    if original is None:
        state = 'not-applicable' if current is None else 'added'
    elif current is None:
        state = 'removed'
    elif any(original[key] != current[key] for key in ('route', 'type', 'count', 'duplicate')):
        state = 'shape-changed'
    else:
        state = 'value-preserved' if original['valueHex'] == current['valueHex'] else 'value-changed'
    checksum = None
    if cell['storage'] == 'checksum' and current is not None:
        if current['type'] == 4 and current['count'] == 1:
            checksum = struct.unpack(target['order'] + 'I', bytes.fromhex(current['valueHex']))[0] == sum(expected_date)
    changed = []
    source_values, target_values = identities(source), identities(target)
    for identity in sorted(source_values.keys() | target_values.keys()):
        left, right = source_values.get(identity), target_values.get(identity)
        if left != right:
            changed.append({'identity': [list(identity[0]), *identity[1:]],
                            'sourceHex': left, 'outputHex': right})
    return {'id': cell['id'], 'selectedDateVerified': True,
            'knownCompanionValuesVerified': True, 'unselectedLeafComplementsVerified': True,
            'unknownEntryState': state,
            'sourceAliasRelationship': alias_relationship(source_date, original),
            'outputAliasRelationship': alias_relationship(target_date, current),
            'fixtureDefinedChecksumConsistent': checksum,
            'checksumIsCanonAlgorithm': False,
            'logicalValueChanges': changed,
            'sourceCmt2Partition': source['partition'], 'outputCmt2Partition': target['partition'],
            'sourceCmt2Entries': source['entries'], 'outputCmt2Entries': target['entries'],
            'sourceCmt4Gaps': old['cmts']['CMT4']['gaps'],
            'outputCmt4Gaps': new['cmts']['CMT4']['gaps']}


def verify_closures(closures):
    require(len(closures) == len(PINS), 'Wrong pinned closure count')
    found = {}
    for closure in closures:
        path = Path(closure['manifestPath'])
        name = path.name
        require(name in PINS and name not in found and digest(path.read_bytes()) == PINS[name]
                == closure['sha256'], 'Pinned closure manifest changed')
        definition = strict_json(path.read_text(encoding='utf-8'))
        require(definition['files'] == closure['files']
                and Path(definition['root']).resolve() == Path(closure['root']).resolve(),
                'Closure contents/root substitution')
        root = Path(definition['root']).resolve()
        for item in definition['files']:
            component = (root / item['path']).resolve()
            require(component.is_relative_to(root) and component.is_file()
                    and component.stat().st_size == int(item['byteLength'])
                    and digest(component.read_bytes()) == item['sha256'], 'Closure component changed')
        found[name] = root
    require(found.keys() == PINS.keys(), 'Missing pinned closure')
    return found


def audit(root):
    root = Path(root).resolve()
    scope = strict_json((root / 'scope.json').read_text(encoding='utf-8'))
    manifest = strict_json((root / 'manifest.json').read_text(encoding='utf-8'))
    require(scope['schemaVersion'] == manifest['schemaVersion'] == 1
            and scope['authoredOnly'] is True and scope['productionMutationAllowed'] is False
            and scope['ticket'] == 113
            and scope['maxInputBytes'] == MAX_BYTES and scope['timeoutSeconds'] == 120
            and manifest['complete'] is True, 'Wrong/incomplete experiment scope')
    planned = []
    for order, storage, assignment in itertools.product(
            ('II', 'MM'), ('baseline', 'inline', 'outline', 'alias', 'checksum'), ('same', 'changed')):
        pad = False
        planned.append({'id': f'{order}-{storage}-{assignment}',
                        'order': order, 'storage': storage, 'assignment': assignment, 'pad': pad})
    require(scope['matrix'] == planned and len(manifest['cells']) == len(planned), 'Declared matrix changed')
    closure_roots = verify_closures(scope['toolClosures'])
    checked = []
    for name in ('lib/Image/ExifTool/Exif.pm', 'lib/Image/ExifTool/Canon.pm'):
        component = closure_roots['exiftool-13.59.json'] / name
        text = component.read_text(encoding='utf-8')
        definitions = re.findall(r'^\s*(0x[0-9a-f]+|[0-9]+)\s*=>', text, re.I | re.M)
        require(all(int(key, 16 if key.lower().startswith('0x') else 10) != UNKNOWN
                    for key in definitions), 'Authored tag is defined in pinned namespace')
        checked.append({'path': name, 'sha256': digest(component.read_bytes())})
    require(scope['namespaceChoice'] == {
        'tag': UNKNOWN, 'meaning': 'project-authored opaque entry',
        'namespace': 'CMT2 Exif::Main', 'checkedSources': checked,
        'definitionAbsent': True,
        'checksum': 'invented sum of all 20 selected date bytes; LONG1 in TIFF byte order'},
        'Unknown-tag choice/source evidence changed')
    require(manifest['toolClosuresAfter'] == scope['toolClosures'], 'Postrun pinned closure changed')
    capture_definition = strict_json((root / 'capture-manifest.json').read_text(encoding='utf-8'))
    captures = {item['path']: item for item in capture_definition['files']}
    require(len(captures) == len(capture_definition['files'])
            and set(captures) == {path.relative_to(root).as_posix() for path in root.rglob('*')
                                  if path.is_file() and path != root / 'capture-manifest.json'},
            'Capture manifest is not exact directory membership')
    for item in captures.values():
        name = item['path']
        require(isinstance(name, str) and name and '\\' not in name and ':' not in name
                and all(part not in ('', '.', '..') for part in name.split('/')),
                'Unsafe capture member')
        path = (root / name).resolve()
        require(path.is_relative_to(root) and path.is_file() and not (root / name).is_symlink()
                and path.stat().st_size == item['size']
                and digest(path.read_bytes()) == item['sha256'], 'Captured evidence changed')
    archive_definition = strict_json((root / 'source-manifest.json').read_text(encoding='utf-8'))
    require(archive_definition['sources'] == scope['sources'], 'Archived source lineage changed')
    archive = {}
    for item in scope['sources']:
        name = item['archive']['path']
        current = Path(item['currentPath'])
        require(current.parent == Path(__file__).resolve().parent and current.suffix == '.py'
                and name == 'sources/' + current.name and name not in archive
                and name in captures and captures[name] == item['archive'], 'Invalid archived source member')
        archived = file_bytes(root, item['archive'])
        require(current.is_file() and digest(current.read_bytes()) == digest(archived),
                'Current source differs from executed evidence')
        archive[name] = item['archive']['sha256']
    require({'sources/runner.py', 'sources/audit.py', 'sources/test_audit.py',
             'sources/test_runner.py'} <= archive.keys()
            and set(archive) == {'sources/' + path.name for path in Path(__file__).parent.glob('*.py')},
            'Required source not archived before effects')
    require(scope['driver']['sha256'] == archive['sources/runner.py'], 'Executed driver lineage differs')
    environment = scope['environment']
    require(set(environment) <= {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH',
                                  'PERL5LIB', 'LC_ALL', 'LANG', 'TZ'}
            and environment['PATH'] == str(closure_roots['installed-perl.json']) + os.pathsep
                + str(Path(environment['SYSTEMROOT']) / 'System32')
            and environment['PERL5LIB'] == str(closure_roots['json-pp.json'] / 'lib')
            and (environment['LC_ALL'], environment['LANG'], environment['TZ']) == ('C', 'C', 'UTC0'),
            'Reference environment differs from restricted recipe')
    checks = []
    for declared, cell in zip(planned, manifest['cells']):
        require(all(cell[key] == value for key, value in declared.items()), 'Cell identity/order changed')
        data = file_bytes(root, cell['input'])
        require(cell['input'] == cell['inputAfter'], 'Authored source changed during operation')
        require((root / cell['input']['path']).stat().st_mtime_ns == cell['input']['mtimeNs'],
                'Authored source modification time changed')
        old = verify_input(data, cell)
        command = cell['command']
        file_bytes(root, command['stdout'])
        file_bytes(root, command['stderr'])
        date = ORIGINAL if cell['assignment'] == 'same' else CHANGED
        expected = [str(closure_roots['installed-perl.json'] / 'perl.exe'),
                    str(closure_roots['exiftool-13.59.json'] / 'exiftool'), '-config', '',
                    '-ExifIFD:DateTimeOriginal=' + date[:-1].decode('ascii')]
        if cell['pad']:
            expected += ['-api', 'QuickTimePad=1']
        expected += ['-o', str(root / (cell['id'] + '.output.cr3')),
                     str(root / (cell['id'] + '.input.cr3'))]
        require(command['argv'] == expected and command['elapsedNs'] >= 0, 'Unexpected reference operation')
        if (command['exitCode'] == 0 and command['timedOut'] is False
                and command['launchError'] is None and cell['output'] is not None):
            output = file_bytes(root, cell['output'])
            checks.append(compare_output(data, output, old, cell))
        else:
            require(cell['storage'] not in ('baseline', 'inline', 'outline'),
                    'Baseline/reachable control did not exercise writer')
            if cell['output'] is not None:
                file_bytes(root, cell['output'])
            checks.append({'id': cell['id'], 'incompleteOperation': True,
                           'exitCode': command['exitCode'], 'timedOut': command['timedOut']})
        result = strict_json((root / (cell['id'] + '.result.json')).read_text(encoding='utf-8'))
        require(result == cell, 'Per-cell result differs from final manifest')
    return {'ticket': 113, 'authoredOnly': True, 'independentByteAuditCompleted': True,
            'captureManifestSha256': digest((root / 'capture-manifest.json').read_bytes()),
            'sourceManifestSha256': digest((root / 'source-manifest.json').read_bytes()),
            'auditorSha256': digest(Path(__file__).read_bytes()),
            'sourceSha256': {Path(name).name: value for name, value in archive.items()},
            'toolManifestSha256': PINS, 'cells': checks,
            'productionMutationAllowed': False, 'formatAdmissionAttempted': False}


def public_results(result):
    """Allowlist fields from this authored-only observer; no private input API."""
    keys = ('ticket', 'authoredOnly', 'independentByteAuditCompleted', 'auditorSha256',
            'sourceSha256', 'toolManifestSha256', 'cells', 'productionMutationAllowed',
            'formatAdmissionAttempted')
    return {'schemaVersion': 1, **{key: result[key] for key in keys}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Fresh audit output required')
    result = audit(args.root)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

"""Independent read-only byte witness for #0102; camera reports stay private.

This reader does not import the attribution implementation or its inventories.
It intentionally supports classic TIFF and the declared chunk-offset subset.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

CANON = bytes.fromhex('85c0b687820f11e08111f4ce462b6a48')
CONTAINERS = {b'moov', b'trak', b'mdia', b'minf', b'stbl', b'dinf'}
WIDTH = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1,
         8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}
MAX_BYTES = 256 * 1024 * 1024


class Refused(ValueError):
    pass


def need(value, message):
    if not value:
        raise Refused(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def span(data, start, size, limit=None):
    limit = len(data) if limit is None else limit
    need(0 <= start <= limit and 0 <= size <= limit - start, 'Range outside bytes')
    return data[start:start + size]


def boxes(data):
    need(len(data) <= MAX_BYTES, 'Input byte ceiling')
    result = []

    def visit(start, end, parent, path, depth):
        need(depth <= 16, 'Container depth ceiling')
        seen = Counter()
        while start < end:
            need(len(result) < 4096, 'Box count ceiling')
            size, kind = struct.unpack('>I4s', span(data, start, 8, end))
            header = 8
            if size == 1:
                size = struct.unpack('>Q', span(data, start + 8, 8, end))[0]
                header = 16
            elif size == 0:
                size = end - start
            need(size >= header, 'Box shorter than header')
            span(data, start, size, end)
            name = kind.decode('latin1')
            location = path + ((name, seen[kind]),)
            seen[kind] += 1
            index = len(result)
            body, finish = start + header, start + size
            result.append({'kind': name, 'start': start, 'body': body,
                           'end': finish, 'parent': parent, 'path': location})
            if kind in CONTAINERS:
                visit(body, finish, index, location, depth + 1)
            elif kind == b'uuid' and span(data, body, 16, finish) == CANON:
                visit(body + 16, finish, index, location, depth + 1)
            start = finish
        need(start == end, 'Container extent mismatch')

    visit(0, len(data), None, (), 0)
    return result


def tiff(data):
    need(len(data) >= 8, 'Short TIFF header')
    endian = {b'II': '<', b'MM': '>'}.get(bytes(data[:2]))
    need(endian is not None, 'Unsupported TIFF order')

    def number(at, code):
        return struct.unpack(endian + code, span(data, at, struct.calcsize(code)))[0]

    need(number(2, 'H') == 42, 'Unsupported TIFF magic')
    pending = [(number(4, 'I'), ('root',), 0)]
    visited, values, structures = set(), [], [(0, 8)]
    while pending:
        at, path, depth = pending.pop(0)
        if not at:
            continue
        need(depth <= 16 and at not in visited, 'Repeated/deep IFD')
        visited.add(at)
        count = number(at, 'H')
        need(len(values) + count <= 4096, 'Entry ceiling')
        size = 6 + count * 12
        span(data, at, size)
        need(all(at + size <= left or at >= right for left, right in structures),
             'IFD overlaps structure')
        structures.append((at, at + size))
        duplicates = Counter()
        for ordinal in range(count):
            entry = at + 2 + ordinal * 12
            tag, form, amount, pointer = struct.unpack(endian + 'HHII', span(data, entry, 12))
            need(form in WIDTH, 'Unknown TIFF width')
            length = WIDTH[form] * amount
            offset = entry + 8 if length <= 4 else pointer
            raw = span(data, offset, length)
            duplicate = duplicates[tag]
            duplicates[tag] += 1
            values.append({'directory': path, 'tag': tag, 'duplicate': duplicate,
                           'ordinal': ordinal, 'format': form, 'count': amount,
                           'entry': entry, 'offset': offset, 'length': length, 'sha256': digest(raw)})
            if tag in (0x8769, 0x8825, 0xa005):
                need(form == 4 and amount == 1, 'Unsupported IFD pointer')
                pending.append((pointer, path + (f'{tag}:{duplicate}',), depth + 1))
        pending.append((number(at + 2 + count * 12, 'I'), path + ('next',), depth + 1))
    covered = bytearray(len(data))
    for left, right in structures:
        covered[left:right] = b'\x01' * (right - left)
    for value in values:
        left, size = value['offset'], value['length']
        covered[left:left + size] = b'\x01' * size
    gaps, at = [], 0
    while at < len(data):
        if covered[at]:
            at += 1
            continue
        start = at
        while at < len(data) and not covered[at]:
            at += 1
        raw = data[start:at]
        gaps.append({'offset': start, 'length': len(raw), 'allZero': not any(raw),
                     'sha256': digest(raw)})
    return {'byteOrder': endian, 'values': values, 'gaps': gaps,
            'coveredBytes': sum(covered), 'length': len(data), 'structures': structures}


def inspect(data):
    table = boxes(data)
    cmts, ctbo, chunks = [], [], []
    mdats = [box for box in table if box['kind'] == 'mdat']
    for box in table:
        body = span(data, box['body'], box['end'] - box['body'])
        if box['kind'] in ('CMT1', 'CMT2', 'CMT3', 'CMT4'):
            parent = table[box['parent']] if box['parent'] is not None else None
            need(parent and parent['kind'] == 'uuid'
                 and data[parent['body']:parent['body'] + 16] == CANON, 'CMT outside Canon UUID')
            cmts.append({'path': box['path'], 'body': box['body'], **tiff(body)})
        elif box['kind'] == 'CTBO':
            count = struct.unpack('>I', span(body, 0, 4))[0]
            need(count <= 4096 and len(body) == 4 + count * 20, 'CTBO table shape')
            for ordinal in range(count):
                item, offset, size = struct.unpack('>IQQ', span(body, 4 + ordinal * 20, 20))
                span(data, offset, size)
                matches = [b['path'] for b in table if (b['start'], b['end'] - b['start']) == (offset, size)]
                ctbo.append({'path': box['path'], 'ordinal': ordinal, 'id': item,
                             'offset': offset, 'length': size, 'exactBoxMatches': matches,
                             'sha256': digest(span(data, offset, size))})
        elif box['kind'] in ('stco', 'co64'):
            width = 4 if box['kind'] == 'stco' else 8
            need(span(body, 0, 4) == b'\0' * 4, 'Unsupported chunk table version/flags')
            count = struct.unpack('>I', span(body, 4, 4))[0]
            need(count <= 4096 and len(body) == 8 + count * width, 'Chunk table shape')
            sizes = [candidate for candidate in table if candidate['parent'] == box['parent']
                     and candidate['kind'] == 'stsz']
            sample_length = None
            if sizes:
                need(len(sizes) == 1 and count == 1, 'Unsupported sample-size correspondence')
                raw = span(data, sizes[0]['body'], sizes[0]['end'] - sizes[0]['body'])
                flags, fixed, samples = struct.unpack('>III', span(raw, 0, 12))
                need(flags == 0 and samples == 1 and len(raw) == (12 if fixed else 16),
                     'Unsupported independent single-sample size')
                sample_length = fixed or struct.unpack('>I', span(raw, 12, 4))[0]
                need(sample_length > 0, 'Empty independently bound sample')
            for ordinal in range(count):
                offset = int.from_bytes(span(body, 8 + ordinal * width, width), 'big')
                owners = [m for m in mdats if m['body'] <= offset < m['end']]
                need(len(owners) == 1, 'Chunk start not inside one mdat payload')
                owner = owners[0]
                if sample_length is not None:
                    span(data, offset, sample_length, owner['end'])
                chunks.append({'path': box['path'], 'ordinal': ordinal, 'offset': offset,
                               'mdatPath': owner['path'], 'relativeOffset': offset - owner['body'],
                               'singleSampleLength': sample_length,
                               'sampleSha256': digest(span(data, offset, sample_length))
                               if sample_length is not None else None})
    return {'length': len(data), 'sha256': digest(data), 'cmts': cmts, 'ctbo': ctbo,
            'chunks': chunks}


def frozen(value):
    return tuple(frozen(item) for item in value) if isinstance(value, (tuple, list)) else value


def value_map(witness):
    result = {}
    for block in witness['cmts']:
        name = block['path'][-1][0]
        for value in block['values']:
            directory = []
            for part in value['directory']:
                if part in ('root', 'next'):
                    directory.append((part, 0))
                else:
                    tag, occurrence = part.split(':')
                    directory.append(('tag-pointer', int(tag), int(occurrence)))
            key = (name, tuple(directory), value['tag'], value['duplicate'],
                   value['format'], value['count'])
            need(key not in result, 'Duplicate independent value identity')
            result[key] = {**value, 'absolute': block['body'] + value['offset'],
                           'absoluteEntry': block['body'] + value['entry']}
    return result


def verify_attribution(report, before, after, left, right):
    """Reconcile delivered claims with independently parsed source bytes."""
    old, new = value_map(left), value_map(right)
    rows = {frozen(row['key']): row for row in report['allocations']}
    need(len(rows) == len(report['allocations']) and rows.keys() == old.keys() | new.keys(),
         'Allocation identity set differs from independent reader')
    for key, row in rows.items():
        values = []
        for label, expected, data in [('source', old.get(key), before),
                                      ('candidate', new.get(key), after)]:
            observed = row[label]
            need((expected is None) == (observed is None), 'Missing/extra allocation')
            if expected is None:
                values.append(None)
                continue
            need((observed['offset'], observed['length'], observed['ordinal'])
                 == (expected['absolute'], expected['length'], expected['ordinal']),
                 'Allocation offset/length/order disagreement')
            raw = span(data, expected['absolute'], expected['length'])
            need(digest(raw) == row[label + 'Sha256'] == expected['sha256'],
                 'Allocation byte identity disagreement')
            values.append(raw)
        need(row['bytesEqual'] == (values[0] is not None and values[1] is not None
                                  and values[0] == values[1]), 'Incorrect value equality')
    for label, data, witness in [('source', before, left), ('candidate', after, right)]:
        supplied = report[label + 'Inventory']
        position = 0
        for region in supplied['partition']:
            need(region['start'] == position and region['end'] > position and region['roles'],
                 'Delivered partition has gaps/overlap/empty roles')
            position = region['end']
        need(position == len(data), 'Delivered partition misses file bytes')
        expected_gaps = {(block['path'][-1][0], block['body'] + gap['offset'],
                          block['body'] + gap['offset'] + gap['length'])
                         for block in witness['cmts'] for gap in block['gaps']}
        actual_gaps = set()
        for gap in report[label + 'Gaps']:
            raw = span(data, gap['start'], gap['length'])
            need(gap['end'] == gap['start'] + gap['length'] and digest(raw) == gap['sha256'],
                 'Delivered gap byte binding disagreement')
            need((gap['zeroBytes'], gap['nonzeroBytes']) == (raw.count(0), len(raw) - raw.count(0)),
                 'Delivered gap zero/nonzero classification disagreement')
            actual_gaps.add((gap['block'], gap['start'], gap['end']))
        need(actual_gaps == expected_gaps, 'Independent gap intervals disagree')
        expected_ctbo = {(frozen(row['path']), row['id']): row for row in witness['ctbo']}
        expected_chunks = {(frozen(row['path'][:-1]), row['ordinal']): row for row in witness['chunks']}
        actual_ctbo = set()
        for row in report['pointers']['ctbo']:
            bound = row[label]
            if bound is None:
                continue
            key = (frozen(bound['boxPath']), bound['id'])
            need(key in expected_ctbo and key not in actual_ctbo, 'CTBO identity disagreement')
            expected = expected_ctbo[key]
            actual_ctbo.add(key)
            need((bound['offset'], bound['length']) == (expected['offset'], expected['length']),
                 'CTBO extent disagreement')
            matches = expected['exactBoxMatches']
            relation = ('null' if expected['offset'] == expected['length'] == 0 else
                        'exact-box-extent' if len(matches) == 1 else 'unknown-target')
            need(bound['relationship'] == relation, 'Incorrect CTBO relationship classification')
            need(frozen(bound['resolvedTargetPath']) == (frozen(matches[0]) if len(matches) == 1 else None),
                 'Incorrect CTBO resolved box')
        need(actual_ctbo == expected_ctbo.keys(), 'Missing independently observed CTBO entry')
        actual_chunks = set()
        for row in report['pointers']['samples']:
            bound = row[label]
            if bound is None:
                continue
            key = (frozen(bound['tablePath']), 0)
            need(key in expected_chunks and key not in actual_chunks, 'Chunk identity disagreement')
            expected = expected_chunks[key]
            actual_chunks.add(key)
            need(bound['offset'] == expected['offset']
                 and bound['relativeToMdatBody'] == expected['relativeOffset']
                 and frozen(bound['mdatPath']) == frozen(expected['mdatPath']), 'Chunk binding disagreement')
            need(expected['singleSampleLength'] is not None
                 and bound['length'] == expected['singleSampleLength']
                 and bound['sha256'] == expected['sampleSha256'], 'Independent sample-size/hash disagreement')
            need(digest(span(data, bound['offset'], bound['length'])) == bound['sha256'],
                 'Bounded sample bytes disagree')
        need(actual_chunks == expected_chunks.keys(), 'Missing independently observed chunk')
    for row in report['pointers']['ctbo']:
        a, b = row['source'], row['candidate']
        expected = (a is not None and b is not None and a['relationship'] != 'unknown-target'
                    and a['relationship'] == b['relationship']
                    and a['resolvedTargetPath'] == b['resolvedTargetPath'])
        need(row['sameResolvedTarget'] == expected, 'Incorrect paired CTBO claim')
    for row in report['pointers']['samples']:
        a, b = row['source'], row['candidate']
        expected = (a is not None and b is not None and all(a[key] == b[key] for key in
                    ('length', 'mdatPath', 'relativeToMdatBody', 'sha256')))
        need(row['sameBoundedSample'] == expected, 'Incorrect paired sample claim')
    ctbo_valid = all(row['sameResolvedTarget'] for row in report['pointers']['ctbo'])
    samples_valid = all(row['sameBoundedSample'] for row in report['pointers']['samples'])
    all_ranges = {'source': [], 'candidate': []}
    for cell in report.get('cellComparisons', []):
        values = []
        for label, data in [('source', before), ('candidate', after)]:
            ranges = cell[label + 'Ranges']
            all_ranges[label].extend(ranges)
            raw = b''.join(span(data, a, b - a) for a, b in ranges)
            present = cell[label + 'Length'] is not None
            need((len(raw) if present else None) == cell[label + 'Length']
                 and (digest(raw) if present else None) == cell[label + 'Sha256'],
                 'Cell byte binding disagreement')
            values.append(raw if present else None)
        equal = values[0] is not None and values[1] is not None and values[0] == values[1]
        need(cell['bytesEqual'] == equal, 'Incorrect cell equality')
        role, meaning = cell['role'], cell['attribution']
        if meaning == 'unchanged-bytes':
            need(equal, 'Changed bytes labeled unchanged')
        elif meaning == 'added-or-missing-relationship':
            need(values[0] is None or values[1] is None, 'Existing relationship labeled missing')
        elif meaning == 'declared-date-value-change':
            key = frozen(json.loads(role.removeprefix('value:')))
            need(role.startswith('value:') and key[0] == 'CMT2' and key[2] == 0x9003
                 and values[1] == b'2001:02:03 04:05:06\0', 'Incorrect declared date cell')
        elif meaning == 'parsed-box-extent-rewrite':
            prefix = 'bmff-extended-size:' if role.startswith('bmff-extended-size:') else 'bmff-size:'
            need(role.startswith(prefix), 'Wrong box-size cell role')
            path = frozen(json.loads(role[len(prefix):]))
            for label, data in [('source', before), ('candidate', after)]:
                box = next((item for item in boxes(data) if frozen(item['path']) == path), None)
                need(box is not None, 'Missing independently parsed box')
                expected = [[box['start'] + 8, box['body']]] if prefix == 'bmff-extended-size:' else [[box['start'], box['start'] + 4]]
                need([list(r) for r in cell[label + 'Ranges']] == expected, 'Incorrect box-size cell range')
        elif meaning == 'parsed-tiff-allocation-address-rewrite':
            need(role.startswith('ifd-value-pointer:'), 'Wrong allocation pointer role')
            key = frozen(json.loads(role[len('ifd-value-pointer:'):]))
            for label, entries in [('source', old), ('candidate', new)]:
                value = entries.get(key)
                need(value is not None and value['length'] > 4
                     and [list(r) for r in cell[label + 'Ranges']]
                     == [[value['absoluteEntry'] + 8, value['absoluteEntry'] + 12]],
                     'Incorrect allocation pointer cell range')
        elif meaning == 'validated-ctbo-target-relocation':
            need(role.startswith(('ctbo-offset:', 'ctbo-size:')) and ctbo_valid,
                 'Unvalidated CTBO cell classified as relocation')
        elif meaning == 'validated-sample-relocation':
            need(role.startswith('chunk-offset:') and samples_valid,
                 'Unvalidated sample cell classified as relocation')
        else:
            need(meaning == 'unexplained-or-unallocated-byte-change', 'Unknown cell classification')
    if report.get('cellComparisons'):
        for label, data in [('source', before), ('candidate', after)]:
            position = 0
            for start, end in sorted(all_ranges[label]):
                need(start <= position, 'Cell ranges miss file bytes')
                position = max(position, end)
            need(position == len(data), 'Cell ranges miss file tail')
    need(report['productionMutationAllowed'] is False and report['formatAdmissionAttempted'] is False,
         'Attribution cannot authorize mutation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--attribution-root', type=Path,
                        help='Optional delivered private report root to verify independently')
    args = parser.parse_args()
    need(not args.output.exists(), 'Fresh private audit destination required')
    root = args.frozen_run.resolve()
    records = json.loads((root / 'results.private.json').read_bytes())
    scope = json.loads((root / 'scoped-review.private.json').read_bytes())
    manifest_bytes = Path(scope['admissionManifest']['path']).read_bytes()
    need(digest(manifest_bytes) == scope['admissionManifest']['sha256'], 'Frozen admission manifest changed')
    manifest = json.loads(manifest_bytes)
    sources = {source['id']: source for source in manifest['sources']}
    grants = {grant['id']: grant for grant in scope['grants']}
    need(sources.keys() == grants.keys() and all(grant['publishReports'] == 'denied'
         for grant in grants.values()), 'Frozen private source/grant cohort changed')
    for name, expected in json.loads((root / 'capture-manifest.private.json').read_bytes()).items():
        need(digest((root / name).read_bytes()) == expected, 'Frozen capture binding changed')
    reports = []
    attributed = {}
    if args.attribution_root:
        directory = args.attribution_root.resolve()
        for name, expected in json.loads((directory / 'capture-manifest.private.json').read_bytes()).items():
            need(digest((directory / name).read_bytes()) == expected, 'Delivered report binding changed')
        index = json.loads((directory / 'index.private.json').read_bytes())
        need(index['publicReportsPermitted'] is False, 'Camera report disclosure is private only')
        attributed = {(row['id'], row['kind']): directory / row['report'] for row in index['reports']}
    for record in records:
        item = {'id': record['id'], 'files': {}}
        actual = {}
        paths = {'source': Path(sources[record['id']]['path']),
                 'native': root / (record['id'] + '.native.candidate.cr3'),
                 'reference': root / (record['id'] + '.reference.cr3')}
        for label, path in paths.items():
            before = (path.stat().st_size, path.stat().st_mtime_ns)
            with path.open('rb') as stream:
                data = stream.read(MAX_BYTES + 1)
            need(before == (path.stat().st_size, path.stat().st_mtime_ns),
                 'Input observations changed while reading')
            item['files'][label] = inspect(data)
            actual[label] = data
        need(item['files']['source']['sha256'] == sources[record['id']]['sha256']
             == grants[record['id']]['sourceSha256'], 'Frozen source content binding changed')
        if args.attribution_root:
            for kind in ('native', 'reference'):
                need((record['id'], kind) in attributed, 'Missing delivered comparison')
                report = json.loads(attributed.pop((record['id'], kind)).read_bytes())
                verify_attribution(report, actual['source'], actual[kind],
                                   item['files']['source'], item['files'][kind])
            item['deliveredComparisonsIndependentlyVerified'] = True
        reports.append(item)
    need(not attributed, 'Unexpected delivered comparison')
    result = {'ticket': 102, 'kind': 'independent-private-byte-witness',
              'privateOnly': True, 'files': reports,
              'auditorSha256': digest(Path(__file__).read_bytes()),
              'attributionManifestSha256': digest((args.attribution_root / 'capture-manifest.private.json').read_bytes())
              if args.attribution_root else None,
              'limits': 'Classic TIFF, CTBO extents, chunk starts and optional single-sample stsz extents; arbitrary pointer semantics are not inferred.'}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('Independent byte witness retained privately; no camera findings printed.')


if __name__ == '__main__':
    main()

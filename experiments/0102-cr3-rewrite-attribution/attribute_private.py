"""Read-only allocation/offset attribution over frozen #0099 private artifacts.

No camera output, tool process, mutation backend or public-report option exists.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

MAX_BYTES = 256 * 1024 * 1024
MAX_BOXES = 4096
MAX_ENTRIES = 4096
MAX_CTBO = 256
CANON = bytes.fromhex('85c0b687820f11e08111f4ce462b6a48')
WIDTH = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1,
         8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
CONTAINERS = {b'moov', b'trak', b'mdia', b'minf', b'dinf', b'stbl'}
IFD_POINTERS = {0x8769, 0x8825, 0xa005}
DATE = b'2001:02:03 04:05:06\0'


class Refused(ValueError):
    pass


def require(value, message):
    if not value:
        raise Refused(message)


def strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def load(path):
    return strict(Path(path).read_text(encoding='utf-8'))


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')


def extent(start, length, end):
    require(0 <= start <= end and 0 <= length <= end - start, 'Range outside its container')
    return start, start + length


def key_text(value):
    return json.dumps(value, separators=(',', ':'))


def inspect(data):
    require(len(data) <= MAX_BYTES, 'Source exceeds inspection bound')
    boxes, cmts, claims = [], {}, []

    def claim(start, end, role):
        if start != end:
            claims.append((start, end, role))

    def walk(start, end, parent, path, depth):
        require(depth <= 16, 'BMFF depth ceiling')
        counts = Counter()
        at = start
        while at < end:
            require(len(boxes) < MAX_BOXES, 'BMFF box ceiling')
            extent(at, 8, end)
            short, kind = struct.unpack_from('>I4s', data, at)
            header = 8
            if short == 1:
                extent(at, 16, end)
                size = struct.unpack_from('>Q', data, at + 8)[0]
                header = 16
            else:
                size = short or end - at
            require(size >= header, 'Invalid box size')
            _, finish = extent(at, size, end)
            name = kind.decode('latin1')
            own_path = path + ((name, counts[name]),)
            counts[name] += 1
            box = {'kind': name, 'path': own_path, 'start': at, 'body': at + header,
                   'end': finish, 'parent': parent, 'header': header}
            index = len(boxes)
            boxes.append(box)
            claim(at, at + 4, 'bmff-size:' + key_text(own_path))
            claim(at + 4, at + 8, 'bmff-kind:' + key_text(own_path))
            if header == 16:
                claim(at + 8, at + 16, 'bmff-extended-size:' + key_text(own_path))
            body = box['body']
            is_canon = kind == b'uuid' and data[body:body + 16] == CANON
            if kind in CONTAINERS:
                walk(body, finish, index, own_path, depth + 1)
            elif is_canon:
                extent(body, 16, finish)
                claim(body, body + 16, 'canon-uuid-identifier')
                walk(body + 16, finish, index, own_path, depth + 1)
            elif kind in (b'CMT1', b'CMT2', b'CMT3', b'CMT4'):
                require(parent is not None and boxes[parent]['kind'] == 'uuid', 'CMT outside parsed Canon wrapper')
                require(name not in cmts, 'Duplicate CMT block')
                cmts[name] = tiff(data, body, finish, name)
                claims.extend(cmts[name]['claims'])
            elif kind == b'CTBO':
                box['ctbo'] = ctbo(data, body, finish)
                claim(body, body + 4, 'ctbo-entry-count:' + key_text(own_path))
                for row in box['ctbo']:
                    identifier = key_text((own_path, row['id']))
                    claim(row['cell'], row['cell'] + 4, 'ctbo-id:' + identifier)
                    claim(row['cell'] + 4, row['cell'] + 12, 'ctbo-offset:' + identifier)
                    claim(row['cell'] + 12, row['cell'] + 20, 'ctbo-size:' + identifier)
            elif kind in (b'stco', b'co64'):
                extent(body, 8, finish)
                claim(body, body + 8, 'chunk-table-prefix:' + key_text(own_path))
                claim(body + 8, finish, 'chunk-offset:' + key_text(own_path))
            else:
                claim(body, finish, 'leaf-payload:' + key_text(own_path))
            at = finish
        require(at == end, 'Box traversal extent mismatch')

    walk(0, len(data), None, (), 0)
    # Unclaimed CMT bytes remain explicitly unallocated, never presumed disposable.
    for name, block in cmts.items():
        claims.extend((a, b, 'unallocated-cmt:' + name) for a, b in block['gaps'])
    partition = disjoint_partition(claims, len(data))
    return {'boxes': boxes, 'cmts': cmts, 'partition': partition, 'claims': claims}


def tiff(data, base, end, block):
    extent(base, 8, end)
    order = {b'II': '<', b'MM': '>'}.get(bytes(data[base:base + 2]))
    require(order is not None and struct.unpack_from(order + 'H', data, base + 2)[0] == 42, 'Unsupported TIFF header')
    allocations, claims, visited = {}, [], set()
    claims.extend([(base, base + 2, 'tiff-byte-order:' + block),
                   (base + 2, base + 4, 'tiff-magic:' + block),
                   (base + 4, base + 8, 'tiff-root-pointer:' + block)])
    pending = [(struct.unpack_from(order + 'I', data, base + 4)[0], (('root', 0),))]
    while pending:
        relative, path = pending.pop()
        if relative == 0:
            continue
        require(len(path) <= 16 and relative not in visited, 'Cyclic/shared/deep IFD pointer')
        visited.add(relative)
        directory = base + relative
        extent(directory, 2, end)
        count = struct.unpack_from(order + 'H', data, directory)[0]
        require(count <= MAX_ENTRIES and len(allocations) + count <= MAX_ENTRIES, 'IFD entry ceiling')
        _, table_end = extent(directory, 6 + 12 * count, end)
        claims.append((directory, directory + 2, 'ifd-count:' + key_text((block, path))))
        duplicates = Counter()
        for ordinal in range(count):
            at = directory + 2 + ordinal * 12
            tag, kind, number, pointer = struct.unpack_from(order + 'HHII', data, at)
            require(kind in WIDTH, 'Unknown TIFF storage width')
            duplicate = duplicates[tag]
            duplicates[tag] += 1
            key = (block, path, tag, duplicate, kind, number)
            require(key not in allocations, 'Duplicate logical allocation key')
            length = WIDTH[kind] * number
            offset = at + 8 if length <= 4 else base + pointer
            extent(offset, length, end)
            row = {'key': key, 'entry': at, 'ordinal': ordinal, 'offset': offset,
                   'length': length, 'inline': length <= 4, 'order': order}
            allocations[key] = row
            claims.append((at, at + 8, 'ifd-tag-type-count:' + key_text(key)))
            if length <= 4:
                if length:
                    claims.append((offset, offset + length, 'value:' + key_text(key)))
                if length < 4:
                    claims.append((offset + length, at + 12, 'inline-padding:' + key_text(key)))
            else:
                claims.append((at + 8, at + 12, 'ifd-value-pointer:' + key_text(key)))
                claims.append((offset, offset + length, 'value:' + key_text(key)))
            if tag in IFD_POINTERS:
                require(kind == 4 and number == 1, 'Unsupported standard IFD pointer shape')
                pending.append((pointer, path + (('tag-pointer', tag, duplicate),)))
        claims.append((table_end - 4, table_end, 'ifd-next-pointer:' + key_text((block, path))))
        pending.append((struct.unpack_from(order + 'I', data, table_end - 4)[0], path + (('next', 0),)))
    boundaries = sorted({base, end} | {p for a, b, _ in claims for p in (a, b)})
    gaps = [(a, b) for a, b in zip(boundaries, boundaries[1:])
            if a < b and not any(start <= a and b <= finish for start, finish, _ in claims)]
    return {'base': base, 'end': end, 'order': order, 'allocations': allocations,
            'claims': claims, 'gaps': gaps}


def ctbo(data, start, end):
    extent(start, 4, end)
    count = struct.unpack_from('>I', data, start)[0]
    require(count <= MAX_CTBO and end - start == 4 + 20 * count, 'Unsupported CTBO entry extent')
    result, ids = [], set()
    for index in range(count):
        at = start + 4 + index * 20
        identifier, offset, length = struct.unpack_from('>IQQ', data, at)
        require(identifier not in ids, 'Duplicate CTBO id')
        ids.add(identifier)
        extent(offset, length, len(data))
        result.append({'id': identifier, 'offset': offset, 'length': length, 'cell': at})
    return result


def disjoint_partition(claims, total):
    events = {}
    for start, end, label in claims:
        extent(start, end - start, total)
        events.setdefault(start, []).append((label, 1))
        events.setdefault(end, []).append((label, -1))
    events.setdefault(0, [])
    events.setdefault(total, [])
    positions, active, result = sorted(events), Counter(), []
    for index, position in enumerate(positions[:-1]):
        for label, change in events[position]:
            active[label] += change
            if active[label] == 0:
                del active[label]
        finish = positions[index + 1]
        require(active and finish > position, 'Unaccounted file bytes')
        result.append({'start': position, 'end': finish, 'roles': sorted(active),
                       'sharedOwnership': sum(active.values()) > 1})
    require(sum(row['end'] - row['start'] for row in result) == total, 'Partition coverage mismatch')
    return result


def allocation_comparison(before, after, old, new):
    result = []
    left = {key: row for block in old['cmts'].values() for key, row in block['allocations'].items()}
    right = {key: row for block in new['cmts'].values() for key, row in block['allocations'].items()}
    for key in sorted(left.keys() | right.keys()):
        a, b = left.get(key), right.get(key)
        old_bytes = before[a['offset']:a['offset'] + a['length']] if a else None
        new_bytes = after[b['offset']:b['offset'] + b['length']] if b else None
        selected = key[0] == 'CMT2' and key[2] == 0x9003
        result.append({'key': key, 'source': a, 'candidate': b,
                       'bytesEqual': old_bytes == new_bytes and a is not None and b is not None,
                       'sourceSha256': sha_bytes(old_bytes) if a else None,
                       'candidateSha256': sha_bytes(new_bytes) if b else None,
                       'selectedDate': selected,
                       'selectedDateMatchesIntent': new_bytes == DATE if selected else None})
    return result


def gap_summary(data, inventory):
    return [{'block': name, 'start': a, 'end': b, 'length': b - a,
             'zeroBytes': data[a:b].count(0), 'nonzeroBytes': b - a - data[a:b].count(0),
             'sha256': sha_bytes(data[a:b]), 'meaning': 'unallocated-to-scanned-IFDs; semantics-not-inferred'}
            for name, block in inventory['cmts'].items() for a, b in block['gaps']]


def ctbo_bindings(inventory):
    bindings = []
    for box in inventory['boxes']:
        for row in box.get('ctbo', []):
            targets = [candidate for candidate in inventory['boxes']
                       if candidate['start'] == row['offset'] and candidate['end'] - candidate['start'] == row['length']]
            null = row['offset'] == row['length'] == 0
            bindings.append({**row, 'boxPath': box['path'], 'nullReference': null,
                             'resolvedTargetPath': targets[0]['path'] if len(targets) == 1 else None,
                             'relationship': 'null' if null else 'exact-box-extent' if len(targets) == 1 else 'unknown-target'})
    return bindings


def sample_bindings(data, inventory):
    boxes = inventory['boxes']
    result = []
    for index, table in enumerate(boxes):
        if table['kind'] != 'stbl':
            continue
        children = [box for box in boxes if box['parent'] == index]

        def one(kinds):
            matches = [box for box in children if box['kind'] in kinds]
            require(len(matches) == 1, 'Missing/duplicate sample table')
            return matches[0]

        description = one({'stsd'})
        raw = data[description['body']:description['end']]
        require(len(raw) >= 24 and struct.unpack_from('>II', raw) == (0, 1), 'Unsupported sample description header')
        require(struct.unpack_from('>I', raw, 8)[0] == len(raw) - 8, 'Sample description extent mismatch')
        require(raw[12:16] in (b'CRAW', b'CTMD') and raw[22:24] == b'\0\1', 'Unsupported sample type/data reference index')

        sizes = one({'stsz'})
        raw = data[sizes['body']:sizes['end']]
        require(len(raw) in (12, 16), 'Unsupported sample-size table')
        flags, fixed, count = struct.unpack_from('>III', raw)
        require(flags == 0 and count == 1, 'Only one plain sample is supported')
        require(len(raw) == (12 if fixed else 16), 'Sample-size extent mismatch')
        length = fixed or struct.unpack_from('>I', raw, 12)[0]
        require(length > 0, 'Empty sample')
        mapping = one({'stsc'})
        raw = data[mapping['body']:mapping['end']]
        require(raw == struct.pack('>IIIII', 0, 1, 1, 1, 1), 'Unsupported sample-to-chunk relationship')
        offsets = one({'stco', 'co64'})
        raw = data[offsets['body']:offsets['end']]
        width = 8 if offsets['kind'] == 'co64' else 4
        require(len(raw) == 8 + width and struct.unpack_from('>II', raw) == (0, 1), 'Unsupported chunk-offset table')
        offset = struct.unpack_from('>Q' if width == 8 else '>I', raw, 8)[0]
        extent(offset, length, len(data))
        media = [box for box in boxes if box['kind'] == 'mdat'
                 and box['body'] <= offset and offset + length <= box['end']]
        require(len(media) == 1, 'Sample is not inside one parsed mdat')
        # The only supported data reference is the local self-contained url box.
        minf = table['parent']
        dinf = [i for i, box in enumerate(boxes) if box['parent'] == minf and box['kind'] == 'dinf']
        require(len(dinf) == 1, 'Missing/duplicate data-reference container')
        drefs = [box for box in boxes if box['parent'] == dinf[0] and box['kind'] == 'dref']
        require(len(drefs) == 1, 'Missing/duplicate data reference')
        dref = data[drefs[0]['body']:drefs[0]['end']]
        require(dref == struct.pack('>III4sI', 0, 1, 12, b'url ', 1), 'External/unknown data reference')
        result.append({'tablePath': table['path'], 'offsetKind': offsets['kind'],
                       'offsetCell': offsets['body'] + 8, 'offsetWidth': width,
                       'offset': offset, 'length': length, 'mdatPath': media[0]['path'],
                       'relativeToMdatBody': offset - media[0]['body'],
                       'sha256': sha_bytes(data[offset:offset + length])})
    return result


def pointer_comparison(before, after, old, new):
    ctbo_old, ctbo_new = ctbo_bindings(old), ctbo_bindings(new)
    a = {(key_text(row['boxPath']), row['id']): row for row in ctbo_old}
    b = {(key_text(row['boxPath']), row['id']): row for row in ctbo_new}
    ctbo_rows = [{'key': key, 'source': a.get(key), 'candidate': b.get(key),
                  'sameResolvedTarget': key in a and key in b and a[key]['relationship'] != 'unknown-target'
                  and a[key]['relationship'] == b[key]['relationship']
                  and a[key]['resolvedTargetPath'] == b[key]['resolvedTargetPath']}
                 for key in sorted(a.keys() | b.keys())]
    a = {key_text(row['tablePath']): row for row in sample_bindings(before, old)}
    b = {key_text(row['tablePath']): row for row in sample_bindings(after, new)}
    samples = [{'tablePath': key, 'source': a.get(key), 'candidate': b.get(key),
                'sameBoundedSample': key in a and key in b
                and all(a[key][field] == b[key][field] for field in ('length', 'mdatPath', 'relativeToMdatBody', 'sha256'))}
               for key in sorted(a.keys() | b.keys())]
    return {'ctbo': ctbo_rows, 'samples': samples}


def serialized_inventory(inventory):
    # Private report serialization cannot use tuple keys directly.
    return {'boxes': inventory['boxes'], 'cmts': {name: {**block, 'allocations': list(block['allocations'].values())}
             for name, block in inventory['cmts'].items()}, 'partition': inventory['partition']}


def cell_comparison(before, after, old, new, allocations, pointers):
    def cells(data, inventory):
        result = {}
        for start, end, role in inventory['claims']:
            result.setdefault(role, []).append((start, end))
        return {role: {'ranges': ranges, 'bytes': b''.join(data[a:b] for a, b in ranges)}
                for role, ranges in result.items()}

    left, right = cells(before, old), cells(after, new)
    selected = {'value:' + key_text(row['key']) for row in allocations
                if row['selectedDate'] and row['selectedDateMatchesIntent']}
    ctbo_roles = set()
    for row in pointers['ctbo']:
        if row['sameResolvedTarget']:
            identifier = key_text((row['source']['boxPath'], row['source']['id']))
            ctbo_roles.update(('ctbo-offset:' + identifier, 'ctbo-size:' + identifier))
    chunk_roles = set()
    for row in pointers['samples']:
        if row['sameBoundedSample']:
            paths = []
            for side, inventory in [('source', old), ('candidate', new)]:
                sample = row[side]
                paths.append(next(box['path'] for box in inventory['boxes']
                                  if box['kind'] == sample['offsetKind'] and box['body'] + 8 == sample['offsetCell']))
            if paths[0] == paths[1]:
                chunk_roles.add('chunk-offset:' + key_text(paths[0]))
    result = []
    for role in sorted(left.keys() | right.keys()):
        a, b = left.get(role), right.get(role)
        equal = a is not None and b is not None and a['bytes'] == b['bytes']
        if equal:
            meaning = 'unchanged-bytes'
        elif a is None or b is None:
            meaning = 'added-or-missing-relationship'
        elif role in selected:
            meaning = 'declared-date-value-change'
        elif role.startswith(('bmff-size:', 'bmff-extended-size:')):
            meaning = 'parsed-box-extent-rewrite'
        elif role.startswith('ifd-value-pointer:'):
            meaning = 'parsed-tiff-allocation-address-rewrite'
        elif role in ctbo_roles:
            meaning = 'validated-ctbo-target-relocation'
        elif role in chunk_roles:
            meaning = 'validated-sample-relocation'
        else:
            meaning = 'unexplained-or-unallocated-byte-change'
        result.append({'role': role, 'sourceRanges': a['ranges'] if a else [],
                       'candidateRanges': b['ranges'] if b else [], 'bytesEqual': equal,
                       'sourceLength': len(a['bytes']) if a else None,
                       'candidateLength': len(b['bytes']) if b else None,
                       'sourceSha256': sha_bytes(a['bytes']) if a else None,
                       'candidateSha256': sha_bytes(b['bytes']) if b else None,
                       'attribution': meaning})
    return result


def analyze(before, after):
    old, new = inspect(before), inspect(after)
    for inventory in (old, new):
        dates = [row for block in inventory['cmts'].values() for key, row in block['allocations'].items()
                 if key[0] == 'CMT2' and key[2] == 0x9003]
        require(len(dates) == 1 and dates[0]['key'][-2:] == (2, 20), 'Missing/ambiguous/non-ASCII20 date')
        date = dates[0]
        label = 'value:' + key_text(date['key'])
        for start, end, role in inventory['claims']:
            require(role == label or not (start < date['offset'] + 20 and date['offset'] < end), 'Selected date has overlapping ownership')
    allocations = allocation_comparison(before, after, old, new)
    pointers = pointer_comparison(before, after, old, new)
    return {'sourceInventory': serialized_inventory(old), 'candidateInventory': serialized_inventory(new),
            'allocations': allocations,
            'sourceGaps': gap_summary(before, old), 'candidateGaps': gap_summary(after, new),
            'pointers': pointers, 'cellComparisons': cell_comparison(before, after, old, new, allocations, pointers),
            'productionMutationAllowed': False, 'formatAdmissionAttempted': False}


def qualify(repository, prior, root):
    require(root.is_dir() and not root.is_symlink() and not list(root.iterdir()), 'Fresh private empty root required')
    manifest = load(prior / 'capture-manifest.private.json')
    review = load(repository / '.local/qualification-wave-20261015/reference99-independent-review.private.json')
    require(review['allPassed'] and sha(prior / 'results.private.json') == review['resultsSha256'], 'Prior independent review binding changed')
    for name, expected in manifest.items():
        require(Path(name).name == name, 'Retained file name escapes its root')
        require(sha(prior / name) == expected, 'Prior retained artifact changed')
    scoped = load(prior / 'scoped-review.private.json')
    require(sha(prior / 'scoped-review.private.json') == review['scopedReviewSha256'], 'Prior scoped rights review changed')
    admission_path = Path(scoped['admissionManifest']['path'])
    require(sha(admission_path) == scoped['admissionManifest']['sha256'], 'Frozen source manifest changed')
    inputs = load(admission_path)
    grants = {row['id']: row for row in scoped['grants']}
    require({row['id'] for row in inputs['sources']} == set(grants), 'Frozen source cohort changed')
    require(all(row['publishReports'] == 'denied' for row in scoped['grants']), 'Private-only grant required')
    dump(root / 'scoped-review.private.json', {'ticket': 102,
         'scope': 'Read-only attribution of frozen #0099 artifacts; no new camera writes or tools.',
         'priorRoot': str(prior), 'priorManifestSha256': sha(prior / 'capture-manifest.private.json'),
         'priorScopedReviewSha256': sha(prior / 'scoped-review.private.json'),
         'priorIndependentReviewSha256': sha(repository / '.local/qualification-wave-20261015/reference99-independent-review.private.json'),
         'publishReports': 'denied', 'productionMutationAllowed': False})
    (root / 'attribute_private.source.py').write_bytes(Path(__file__).read_bytes())
    results = []
    for source in inputs['sources']:
        require(source['sha256'] == grants[source['id']]['sourceSha256'], 'Source grant identity mismatch')
        source_path = Path(source['path'])
        require(source_path.stat().st_size <= MAX_BYTES, 'Oversized source')
        before_identity = (sha(source_path), source_path.stat().st_mtime_ns)
        require(before_identity[0] == source['sha256'], 'Original source binding changed')
        data = source_path.read_bytes()
        for kind, suffix in [('native', '.native.candidate.cr3'), ('reference', '.reference.cr3')]:
            candidate = prior / (source['id'] + suffix)
            require(candidate.stat().st_size <= MAX_BYTES and sha(candidate) == manifest[candidate.name], 'Candidate binding changed')
            report = analyze(data, candidate.read_bytes())
            dump(root / (source['id'] + '-' + kind + '.private.json'), report)
            results.append({'id': source['id'], 'kind': kind, 'report': source['id'] + '-' + kind + '.private.json'})
        require(before_identity == (sha(source_path), source_path.stat().st_mtime_ns), 'Source changed during read-only attribution')
    dump(root / 'index.private.json', {'ticket': 102, 'reports': results, 'publicReportsPermitted': False,
                                      'productionMutationAllowed': False, 'formatAdmissionAttempted': False})
    dump(root / 'capture-manifest.private.json', {path.name: sha(path) for path in root.iterdir() if path.is_file()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--prior', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    qualify(args.repository.resolve(), args.prior.resolve(), args.root.resolve())
    print('Private read-only attribution finished; review the selected private directory.')

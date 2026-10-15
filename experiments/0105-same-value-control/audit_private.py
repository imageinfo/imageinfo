"""Independent private witness for #0105, using the separate #0102 reader.

The runner and its parsers are never imported. Camera findings must remain in
the explicitly selected private audit destination.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

BASE = Path(__file__).resolve().parents[1] / '0102-cr3-rewrite-attribution'
SPEC = importlib.util.spec_from_file_location('witness102_for105', BASE / 'independent_audit.py')
witness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(witness)
MAX_BYTES = 256 * 1024 * 1024


class Refused(ValueError):
    pass


def need(value, message):
    if not value:
        raise Refused(message)


def strict(text):
    def members(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=members)


def load(path):
    return strict(Path(path).read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def manifest(root):
    """Verify only direct retained files, without accepting escaping names."""
    root = Path(root).resolve()
    records = load(root / 'capture-manifest.private.json')
    need(isinstance(records, dict) and records, 'Empty or malformed retained manifest')
    need(set(records) == {path.name for path in root.iterdir()
                          if path.is_file() and path.name != 'capture-manifest.private.json'},
         'Retained manifest omits or adds a file')
    for name, expected in records.items():
        need(Path(name).name == name and name not in ('.', '..')
             and '/' not in name and '\\' not in name and ':' not in name,
             'Retained name escapes root')
        path = root / name
        need(path.is_file() and not path.is_symlink() and sha(path) == expected,
             'Retained artifact binding changed')
    return records


def fresh_destination(root, output):
    need(not output.exists(), 'Fresh private audit destination required')
    need(not output.resolve().is_relative_to(root.resolve()), 'Keep audit output outside frozen captures')


def bounded_bytes(path):
    path = Path(path)
    before = (path.stat().st_size, path.stat().st_mtime_ns)
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    need(len(data) <= MAX_BYTES, 'Input byte ceiling')
    need(before == (path.stat().st_size, path.stat().st_mtime_ns),
         'Input changed during independent read')
    return data


def selected_date(data):
    inventory = witness.inspect(data)
    values = witness.value_map(inventory)
    dates = [(key, row) for key, row in values.items() if key[0] == 'CMT2' and key[2] == 0x9003]
    need(len(dates) == 1 and dates[0][0][-2:] == (2, 20),
         'Missing/ambiguous/non-ASCII20 selected date')
    key, row = dates[0]
    start, end = row['absolute'], row['absolute'] + 20
    raw = data[start:end]
    need(len(raw) == 20 and raw[-1] == 0, 'Selected date terminator')
    try:
        text = raw[:-1].decode('ascii')
        parsed = datetime.strptime(text, '%Y:%m:%d %H:%M:%S')
        need(f'{parsed.year:04}:{parsed.month:02}:{parsed.day:02} '
             f'{parsed.hour:02}:{parsed.minute:02}:{parsed.second:02}' == text, 'Noncanonical date')
    except (ValueError, UnicodeError) as error:
        raise Refused('Invalid Gregorian ASCII20 date') from error
    for other_key, other in values.items():
        if other_key != key:
            need(other['length'] == 0 or other['absolute'] >= end
                 or other['absolute'] + other['length'] <= start,
                 'Selected date aliases another allocation')
    for block in inventory['cmts']:
        for a, b in block['structures']:
            # The independent TIFF reader includes its header and whole tables.
            need(block['body'] + b <= start or block['body'] + a >= end,
                 'Selected date overlaps TIFF structure')
    return raw, inventory


def run_summary(before, after):
    """Reconstruct complete run digest with a separate byte-wise state machine."""
    common = min(len(before), len(after))
    start, count, changed, samples = None, 0, 0, []
    hasher = hashlib.sha256()

    def consume(offset, length):
        nonlocal count, changed
        count += 1
        changed += length
        hasher.update(struct.pack('>QQ', offset, length))
        if len(samples) < 256:
            samples.append([offset, length])

    for offset in range(common):
        if before[offset] != after[offset]:
            if start is None:
                start = offset
        elif start is not None:
            consume(start, offset - start)
            start = None
    if start is not None:
        consume(start, common - start)
    if len(before) != len(after):
        consume(common, abs(len(before) - len(after)))
    return {'runCount': count, 'changedBytes': changed, 'samples': samples,
            'retainedRunListComplete': count <= 256,
            'completeRunSequenceSha256': hasher.hexdigest(),
            'runSequenceEncoding': 'ordered-u64be-offset-u64be-length-v1'}


def allocation_relations(source, same, changed):
    """Classify complete logical allocation bytes, retaining missing identities."""
    blobs = (source, same, changed)
    maps = [witness.value_map(witness.inspect(data)) for data in blobs]
    result = []
    for key in sorted(set().union(*(mapping.keys() for mapping in maps)), key=repr):
        values = [data[mapping[key]['absolute']:mapping[key]['absolute'] + mapping[key]['length']]
                  if key in mapping else None for data, mapping in zip(blobs, maps)]
        a, b, c = values
        if any(value is None for value in values):
            classification = 'missing-or-added-identity'
        elif a == b == c:
            classification = 'all-equal'
        elif b == c:
            classification = 'shared-reference-value-change'
        elif a == b:
            classification = 'changed-date-output-only-value-change'
        elif a == c:
            classification = 'same-value-output-only-value-change'
        else:
            classification = 'three-distinct-values'
        result.append({'key': key, 'classification': classification,
                       'sha256': [digest(value) if value is not None else None for value in values]})
    return result


def metadata_changes(before, after):
    """Separate exact stored/derived/locator key changes without dropping omissions."""
    result = []
    for key in sorted(before.keys() | after.keys()):
        if (key in before) != (key in after) or before.get(key) != after.get(key):
            category = ('source-locator' if key == 'SourceFile' else
                        'filesystem-observation' if ':System:' in key else
                        'derived-composite' if key.startswith('Composite:') else 'stored-or-other')
            result.append({'key': key, 'beforePresent': key in before, 'afterPresent': key in after,
                           'before': before.get(key), 'after': after.get(key), 'class': category})
    return result


def unique_rows(rows, key='id'):
    need(isinstance(rows, list), 'Expected row list')
    result = {row[key]: row for row in rows}
    need(len(result) == len(rows), 'Duplicate row identity')
    return result


def verify_false_flags(value):
    for key in ('productionMutationAllowed', 'formatAdmissionEnabled', 'publicReportsPermitted'):
        need(value.get(key) is False, 'Research/disclosure boundary changed')


def bind_cohort(sources, grants, results):
    sources, grants, results = map(unique_rows, (sources, grants, results))
    need(1 <= len(sources) <= 8 and sources.keys() == grants.keys() == results.keys(),
         'Incomplete or changed source/grant/result cohort')
    for identifier, source in sources.items():
        need(grants[identifier]['sourceSha256'] == results[identifier]['sourceSha256'] == source['sha256']
             and grants[identifier]['publishReports'] == 'denied', 'Source grant/result binding changed')
    return sources, grants, results


def verify_classification(report):
    same = unique_rows(report['sourceSame']['cellComparisons'], 'role')
    changed = unique_rows(report['sourceChanged']['cellComparisons'], 'role')
    rows = unique_rows(report['cellClassification'], 'role')
    need(rows.keys() == same.keys() | changed.keys(), 'Causal role denominator changed')
    for role, row in rows.items():
        a, b = same.get(role), changed.get(role)
        expected = 'unexplained'
        if (a is not None and b is not None
                and all(row[field] is not None for row in (a, b)
                        for field in ('sourceLength', 'candidateLength'))):
            if a['bytesEqual'] and b['bytesEqual']:
                expected = 'unchanged'
            elif a['bytesEqual']:
                expected = 'changed-date-associated-observation'
            elif not b['bytesEqual'] and a['candidateLength'] == b['candidateLength'] \
                    and a['candidateSha256'] == b['candidateSha256']:
                expected = 'shared-rewrite-observation'
        need(row['classification'] == expected, 'Incorrect causal observation classification')
    need(report.get('causalNecessityEstablished') is False
         and report.get('semanticIndependenceEstablished') is False,
         'Causal control cannot establish necessity or semantic independence')


def verify_comparisons(report, original, same, changed):
    witnesses = [witness.inspect(data) for data in (original, same, changed)]
    for key, before, after, a, b in (
        ('sourceSame', original, same, witnesses[0], witnesses[1]),
        ('sourceChanged', original, changed, witnesses[0], witnesses[2]),
        ('sameChanged', same, changed, witnesses[1], witnesses[2]),
    ):
        witness.verify_attribution(report[key], before, after, a, b)
    verify_classification(report)
    need(report['positionalSourceSame'] == run_summary(original, same)
         and report['positionalSameChanged'] == run_summary(same, changed),
         'Complete byte-run accounting disagrees')
    need(report['outcome'] == ('byte-identical-no-op-artifact' if original == same else 'rewritten-artifact'),
         'Same-value artifact outcome disagrees')
    return allocation_relations(original, same, changed)


def audit_run(root, reclassification=None):
    records = manifest(root)
    scope, summary = load(root / 'scoped-review.private.json'), load(root / 'summary.private.json')
    verify_false_flags(summary)
    need(scope['ticket'] == summary['ticket'] == 105 and scope['publishReports'] == 'denied'
         and scope['productionMutationAllowed'] is False, 'Wrong research scope')
    need(scope['driverSha256'] == sha(root / 'control_private.source.py'), 'Frozen write-runner identity changed')
    revised_reports, revised_manifest = {}, None
    if reclassification is None:
        need(scope['driverSha256'] == sha(Path(__file__).with_name('control_private.py')),
             'Current classifier differs; supply its bound read-only reclassification')
    else:
        revised_manifest = manifest(reclassification)
        revised_scope = load(reclassification / 'scoped-review.private.json')
        need(revised_scope['ticket'] == 105 and revised_scope['publishReports'] == 'denied'
             and revised_scope['productionMutationAllowed'] is False
             and Path(revised_scope['mediaRoot']).resolve() == root
             and revised_scope['mediaManifestSha256'] == sha(root / 'capture-manifest.private.json')
             and revised_scope['writeDriverSha256'] == scope['driverSha256']
             and revised_scope['classifierSha256'] == sha(Path(__file__).with_name('control_private.py'))
             == sha(reclassification / 'control_private.analysis.source.py')
             and revised_scope['reclassifierSha256'] == sha(Path(__file__).with_name('reclassify_private.py'))
             == sha(reclassification / 'reclassify_private.source.py'),
             'Read-only reclassification lineage changed')
        revised_index = load(reclassification / 'index.private.json')
        need(revised_index['ticket'] == 105 and revised_index['publicReportsPermitted'] is False
             and revised_index['productionMutationAllowed'] is False, 'Reclassification scope changed')
        revised_reports = unique_rows(revised_index['reports'])
    prior, attribution = Path(scope['priorRoot']).resolve(), Path(scope['attributionRoot']).resolve()
    frozen99, frozen102 = manifest(prior), manifest(attribution)
    need(frozen99['qualify_private.source.py'] == sha(Path(__file__).resolve().parents[1] /
             '0099-cr3-reference-effects/qualify_private.py')
         and frozen102['attribute_private.source.py'] == sha(BASE / 'attribute_private.py'),
         'Reused methods differ from their frozen source')
    need(scope['priorManifestSha256'] == sha(prior / 'capture-manifest.private.json')
         and scope['attributionManifestSha256'] == sha(attribution / 'capture-manifest.private.json'),
         'Frozen prior manifest lineage changed')
    scope99, scope102 = load(prior / 'scoped-review.private.json'), load(attribution / 'scoped-review.private.json')
    review99 = load(Path(__file__).resolve().parents[2] /
                    '.local/qualification-wave-20261015/reference99-independent-review.private.json')
    need(review99['allPassed'] is True and review99['resultsSha256'] == sha(prior / 'results.private.json')
         and review99['scopedReviewSha256'] == sha(prior / 'scoped-review.private.json'),
         'Prior independent review no longer binds frozen artifacts')
    need(Path(scope102['priorRoot']).resolve() == prior
         and scope102['priorManifestSha256'] == sha(prior / 'capture-manifest.private.json'),
         'Attribution prior lineage changed')
    need(scope['admissionManifest'] == scope99['admissionManifest']
         and scope['grants'] == scope99['grants'] and scope['tools'] == scope99['tools']
         and scope['sourceGuard'] == scope99['sourceGuard']
         and scope['toolClosures'] == scope99['toolClosures'], 'Frozen grant/tool scope changed')
    admission = Path(scope['admissionManifest']['path'])
    need(sha(admission) == scope['admissionManifest']['sha256'], 'Admission manifest changed')
    inputs = load(admission)
    sources, grants, results = bind_cohort(inputs['sources'], scope['grants'], load(root / 'results.private.json'))
    for tool in [*scope['tools'].values(), scope['sourceGuard']]:
        need(sha(tool['path']) == tool['sha256'], 'Pinned executable changed')
    for closure in scope['toolClosures']:
        if 'sourcePath' in closure:
            need(sha(closure['sourcePath']) == closure['sourceSha256']
                 and sha(closure['path']) == closure['sha256'], 'Guard source/binary changed')
        else:
            definition = closure
            if 'files' not in closure:
                need(sha(closure['path']) == closure['sha256'], 'Tool distribution manifest changed')
                definition = load(closure['path'])
                need(Path(definition['root']).resolve() == Path(closure['root']).resolve(),
                     'Tool distribution root changed')
            for entry in definition['files']:
                file = (Path(closure['root']) / entry['path']).resolve()
                need(file.is_relative_to(Path(closure['root']).resolve())
                     and sha(file) == entry['sha256'], 'Pinned tool closure changed')
    for grant in grants.values():
        need(sha(grant['fixturePath']) == grant['fixtureSha256']
             and sha(grant['reviewPath']) == grant['reviewSha256'], 'Source rights record changed')
        fixture, review = load(grant['fixturePath']), load(grant['reviewPath'])
        need(fixture['admission'] == 'admitted' and fixture['rights']['analyze'] and fixture['rights']['modify']
             and {'reference-characterization', 'differential'} <= set(fixture['allowedPhases'])
             and review['review']['state'] == 'approved'
             and review['rights']['permissions']['analyze'] == review['rights']['permissions']['modify'] == 'allowed'
             and review['rights']['permissions']['publishReports'] == 'denied', 'Source rights scope changed')
    attr_index = unique_rows(load(attribution / 'index.private.json')['reports'], 'report')
    need({(row['id'], row['kind']) for row in attr_index.values()} ==
         {(identifier, kind) for identifier in sources for kind in ('native', 'reference')}
         and len(attr_index) == len(sources) * 2, 'Frozen attribution cohort changed')
    runs = unique_rows(load(root / 'runs.private.json'))
    need(set(runs) <= {identifier + '-' + suffix for identifier in sources
                      for suffix in ('source-read', 'same-write', 'same-read', 'changed-read', 'same-unpack')},
         'Unexpected external command: changed-date writes are outside scope')
    for record in runs.values():
        need(record['inputsBefore'] == record['inputsAfter'], 'External command changed an input')
        need(record['stdoutSha256'] == sha(root / (record['id'] + '.stdout'))
             and record['stderrSha256'] == sha(root / (record['id'] + '.stderr')), 'Run capture binding changed')
        for path, state in record['inputsAfter'].items():
            need([sha(path), Path(path).stat().st_mtime_ns] == state, 'Current input differs from capture')
    checks = []
    for identifier, source in sources.items():
        item = results[identifier]
        path, changed = Path(source['path']), prior / (identifier + '.reference.cr3')
        original, changed_data = bounded_bytes(path), bounded_bytes(changed)
        original_date, source_witness = selected_date(original)
        need(digest(original) == source['sha256'] and item['sourcePath'] == str(path)
             and Path(item['changedPath']).resolve() == changed.resolve()
             and digest(changed_data) == item['changedSha256'] == frozen99[changed.name],
             'Actual source/changed artifact binding changed')
        need(item['sourceBefore'] == item['sourceAfter'] == [digest(original), path.stat().st_mtime_ns]
             and item['changedBefore'] == item['changedAfter'] == [digest(changed_data), changed.stat().st_mtime_ns]
             and item['sourceUnchanged'] is True and item['retainedChangedUnchanged'] is True
             and item['guardExit'] == 0 and item['productionMutationAllowed'] is False,
             'Input preservation or guard outcome disagrees')
        need(bytes.fromhex(item['originalDateAscii20Hex']) == original_date,
             'Retained original-value intent disagrees')
        output = root / (identifier + '.same-value.cr3')
        need(Path(item['outputPath']).resolve() == output.resolve(), 'Derivative destination changed')
        write = runs[identifier + '-same-write']
        expected = [scope['tools']['perl']['path'], scope['tools']['reference']['path'], '-config', '',
                    '-ExifIFD:DateTimeOriginal=' + original_date[:-1].decode('ascii'), '-o', str(output), str(path)]
        need(write['argv'] == expected and item['writeExit'] == write['exitCode'],
             'Reference command exceeded original-value assignment')
        check = {'id': identifier, 'outcome': item['outcome'], 'sourceAndExistingArtifactsPreserved': True}
        for row in attr_index.values():
            if row['id'] == identifier:
                other = changed_data if row['kind'] == 'reference' else bounded_bytes(prior / (identifier + '.native.candidate.cr3'))
                witness.verify_attribution(load(attribution / row['report']), original, other,
                                           source_witness, witness.inspect(other))
        if 'report' in item:
            need(write['exitCode'] == 0 and write['timedOut'] is False and output.is_file()
                 and output.name in records, 'Complete outcome lacks completed write/artifact')
            same = bounded_bytes(output)
            need(digest(same) == item['outputSha256'] and selected_date(same)[0] == original_date,
                 'Same-value artifact changed or selected date differs')
            need(Path(item['report']).name == item['report'] and item['report'] in records,
                 'Comparison report is not retained')
            report = load(root / item['report'])
            if reclassification is not None:
                need(identifier in revised_reports, 'Missing revised comparison')
                revised = revised_reports.pop(identifier)
                need(Path(revised['report']).name == revised['report']
                     and revised['report'] in revised_manifest, 'Revised report is not retained')
                updated = load(reclassification / revised['report'])
                need({key: value for key, value in updated.items() if key != 'cellClassification'} ==
                     {key: value for key, value in report.items() if key != 'cellClassification'},
                     'Read-only reclassification changed another observation')
                report = updated
            relations = verify_comparisons(report, original, same, changed_data)
            values = {}
            for label in ('source', 'same', 'changed'):
                run = runs[identifier + '-' + label + '-read']
                need(run['exitCode'] == 0 and not run['timedOut']
                     and (root / (run['id'] + '.stderr')).stat().st_size == 0, 'Incomplete metadata capture')
                rows = load(root / (run['id'] + '.stdout'))
                input_path = {'source': path, 'same': output, 'changed': changed}[label]
                expected_argv = [scope['tools']['perl']['path'], scope['tools']['reference']['path'],
                                 '-config', '', '-j', '-a', '-u', '-G0:1:4:5', '-s', '-n',
                                 '-api', 'RequestAll=3', str(input_path)]
                need(run['argv'] == expected_argv, 'Metadata capture command changed')
                need(isinstance(rows, list) and len(rows) == 1, 'Unexpected metadata row count')
                values[label] = rows[0]
            keys = [key for key in values['source'] if key.endswith(':DateTimeOriginal')]
            need(keys == [item['referenceTargetKey']] and keys[0].startswith('EXIF:ExifIFD:')
                 and values['source'][keys[0]].encode('ascii') + b'\0' == original_date
                 and values['same'].get(keys[0]) == values['source'][keys[0]],
                 'Independent physical/reference date mismatch')
            need(report['sourceSameMetadataChanges'] == metadata_changes(values['source'], values['same'])
                 and report['sameChangedMetadataChanges'] == metadata_changes(values['same'], values['changed']),
                 'Complete metadata delta disagrees')
            unpack = runs[identifier + '-same-unpack']
            need(unpack['argv'] == [scope['tools']['decoder']['path'], str(output)],
                 'Unpack command changed')
            decoded = Path(str(output) + '.pgm')
            complete = (unpack['exitCode'] == 0 and not unpack['timedOut']
                        and (root / (unpack['id'] + '.stderr')).stat().st_size == 0
                        and b'Unpacked' in (root / (unpack['id'] + '.stdout')).read_bytes() and decoded.is_file())
            need(report['unpackComplete'] == complete, 'Independent unpack completeness disagreement')
            baseline_sha = sha(source['baselineDecoded'])
            need(baseline_sha == grants[identifier]['baselineDecodedSha256'], 'Decoded baseline binding changed')
            need(report['decodedBaselineEqual'] == (sha(decoded) == baseline_sha if complete else None)
                 and report['retainedChangedUnpackPath'] == str(Path(str(changed) + '.pgm'))
                 and report['retainedChangedDecodedBaselineEqual'] ==
                     (sha(Path(str(changed) + '.pgm')) == baseline_sha), 'RAW-unpack reconciliation disagrees')
            check.update(independentComparisonsVerified=True, allocationRelations=relations,
                         metadataDeltaVerified=True, rawUnpackReconciled=True)
        else:
            if reclassification is not None:
                need(identifier in revised_reports, 'Missing revised incomplete outcome')
                revised = revised_reports.pop(identifier)
                need(revised['report'] is None and revised['outcome'] == item['outcome'],
                     'Reclassification changed incomplete outcome')
            need(item['outcome'] in ('no-artifact-short-circuit-or-refusal', 'incomplete-artifact',
                                    'unexplained-or-refused-retained'), 'Unrecognized incomplete outcome')
            if item['outcome'] == 'no-artifact-short-circuit-or-refusal':
                need(not output.exists(), 'No-artifact outcome retained an artifact')
            elif item['outcome'] == 'incomplete-artifact':
                need(output.is_file() and write['exitCode'] != 0 and sha(output) == item['outputSha256'],
                     'Incomplete artifact binding disagrees')
        checks.append(check)
    # Read-only audit itself must leave every frozen private capture intact.
    need(manifest(root) == records and manifest(prior) == frozen99 and manifest(attribution) == frozen102,
         'Evidence changed during independent audit')
    need(not revised_reports, 'Unexpected revised comparison')
    if reclassification is not None:
        need(manifest(reclassification) == revised_manifest, 'Reclassification changed during audit')
    return {'ticket': 105, 'privateOnly': True, 'allChecked': True, 'checks': checks,
            'auditorSha256': sha(__file__), 'runnerManifestSha256': sha(root / 'capture-manifest.private.json'),
            'independentReaderSha256': sha(BASE / 'independent_audit.py'),
            'reclassificationManifestSha256': sha(reclassification / 'capture-manifest.private.json')
            if reclassification is not None else None,
            'productionMutationAllowed': False, 'formatAdmissionEnabled': False,
            'publicReportsPermitted': False, 'causalNecessityEstablished': False,
            'semanticIndependenceEstablished': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reclassification', type=Path,
                        help='Optional frozen read-only correction of classification labels')
    args = parser.parse_args()
    fresh_destination(args.root, args.output)
    if args.reclassification:
        fresh_destination(args.reclassification, args.output)
    report = audit_run(args.root.resolve(), args.reclassification.resolve() if args.reclassification else None)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print('Independent control audit retained privately; no camera findings printed.')


if __name__ == '__main__':
    main()

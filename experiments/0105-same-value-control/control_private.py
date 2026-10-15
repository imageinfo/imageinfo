"""Private same-value reference control; no production mutation authority."""
import argparse
import datetime
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess


def component(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REPOSITORY = Path(__file__).resolve().parents[2]
r = component('reference99', REPOSITORY / 'experiments/0099-cr3-reference-effects/qualify_private.py')
a = component('attribution102', REPOSITORY / 'experiments/0102-cr3-rewrite-attribution/attribute_private.py')
require = r.require


def frozen(root):
    manifest = r.read_json(root / 'capture-manifest.private.json')
    for name, expected in manifest.items():
        require(Path(name).name == name and name not in ('', '.', '..'), 'Unsafe frozen filename')
        require(r.sha(root / name) == expected, 'Frozen capture changed')
    return manifest


def cohort(manifest):
    ids = [row['id'] for row in manifest['sources']]
    require(len(set(ids)) == len(ids) and all(re.fullmatch(r'[A-Za-z0-9_-]+', item) for item in ids),
            'Duplicate or unsafe source ID')
    return set(ids)


def date_bytes(data):
    field = r.layout(data)['target']
    inventory = a.inspect(data)
    dates = [row for block in inventory['cmts'].values() for key, row in block['allocations'].items()
             if key[0] == 'CMT2' and key[2] == 0x9003]
    require(len(dates) == 1 and dates[0]['key'][-2:] == (2, 20), 'Independent date identity mismatch')
    require(dates[0]['offset'] == field['offset'], 'Independent date location mismatch')
    # analyze performs the independent selected-allocation alias/structure checks.
    a.analyze(data, data)
    value = data[field['offset']:field['offset'] + 20]
    require(re.fullmatch(rb'\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}\x00', value), 'Not an ASCII20 date')
    datetime.datetime.strptime(value[:-1].decode('ascii'), '%Y:%m:%d %H:%M:%S')
    return value


def classify(original, same, changed):
    """Logical cells describe observed relationships, never rewrite necessity."""
    os_report, oc_report = a.analyze(original, same), a.analyze(original, changed)
    same_cells = {row['role']: row for row in os_report['cellComparisons']}
    changed_cells = {row['role']: row for row in oc_report['cellComparisons']}
    rows = []
    for role in sorted(same_cells.keys() | changed_cells.keys()):
        left, right = same_cells.get(role), changed_cells.get(role)
        if (left is None or right is None or any(row[field] is None
                for row in (left, right) for field in ('sourceLength', 'candidateLength'))):
            label = 'unexplained'
        elif left['bytesEqual'] and right['bytesEqual']:
            label = 'unchanged'
        elif (not left['bytesEqual'] and not right['bytesEqual']
              and (left['candidateLength'], left['candidateSha256']) ==
                  (right['candidateLength'], right['candidateSha256'])):
            label = 'shared-rewrite-observation'
        elif left['bytesEqual'] and not right['bytesEqual']:
            label = 'changed-date-associated-observation'
        else:
            label = 'unexplained'
        rows.append({'role': role, 'classification': label})
    return {'sourceSame': os_report, 'sourceChanged': oc_report,
            'sameChanged': a.analyze(same, changed), 'cellClassification': rows,
            'outcome': 'byte-identical-no-op-artifact' if original == same else 'rewritten-artifact',
            'causalNecessityEstablished': False, 'semanticIndependenceEstablished': False}


def run(root, name, argv, inputs, records, env):
    before = {str(path): r.fingerprint(path) for path in inputs}
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    timeout = False
    try:
        process = subprocess.run([str(item) for item in argv], cwd=root, env=env,
                                 capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        timeout = True
        process = subprocess.CompletedProcess(argv, -1, error.stdout or b'', error.stderr or b'')
    stdout, stderr = root / (name + '.stdout'), root / (name + '.stderr')
    stdout.write_bytes(process.stdout)
    stderr.write_bytes(process.stderr)
    after = {str(path): r.fingerprint(path) for path in inputs}
    records.append({'id': name, 'argv': [str(item) for item in argv], 'startedAt': started,
                    'exitCode': process.returncode, 'timedOut': timeout,
                    'inputsBefore': before, 'inputsAfter': after,
                    'stdoutSha256': r.sha(stdout), 'stderrSha256': r.sha(stderr)})
    r.dump(root / 'runs.private.json', records)
    require(before == after, 'Existing input changed')
    return process


def qualify(prior, attribution, root, guard, repository=REPOSITORY):
    require(os.name == 'nt', 'Windows source guard required')
    require(root.is_dir() and not root.is_symlink() and not list(root.iterdir()), 'Fresh empty private root required')
    require(shutil.disk_usage(root).free >= 8 * 1024 ** 3, 'Require 8 GiB free scratch')
    prior_manifest, attribution_manifest = frozen(prior), frozen(attribution)
    review_path = repository / '.local/qualification-wave-20261015/reference99-independent-review.private.json'
    review = r.read_json(review_path)
    require(review['allPassed'] and review['resultsSha256'] == r.sha(prior / 'results.private.json')
            and review['scopedReviewSha256'] == r.sha(prior / 'scoped-review.private.json'), 'Prior review binding changed')
    scoped = r.read_json(prior / 'scoped-review.private.json')
    manifest_path = Path(scoped['admissionManifest']['path'])
    require(r.sha(manifest_path) == scoped['admissionManifest']['sha256'], 'Frozen admission changed')
    manifest = r.read_json(manifest_path)
    ids = cohort(manifest)
    grants = r.validate_grants(manifest, repository)
    require(grants == scoped['grants'], 'Frozen grants changed')
    closures = r.validate_tool_closures(repository, manifest, guard)
    require(closures == scoped['toolClosures'], 'Frozen tool closure changed')
    require(r.sha(guard) == scoped['sourceGuard']['sha256'], 'Frozen source guard changed')
    for name in ('candidate', 'perl', 'reference', 'decoder'):
        require(manifest[name] == scoped['tools'][name] and r.sha(manifest[name]['path']) == manifest[name]['sha256'], 'Frozen tool changed')
    require(prior_manifest['qualify_private.source.py'] == r.sha(Path(r.__file__)), 'Reference method changed')
    require(attribution_manifest['attribute_private.source.py'] == r.sha(Path(a.__file__)), 'Attribution method changed')
    attr_scope = r.read_json(attribution / 'scoped-review.private.json')
    require(Path(attr_scope['priorRoot']).resolve() == prior and
            attr_scope['priorManifestSha256'] == r.sha(prior / 'capture-manifest.private.json'), 'Attribution lineage changed')
    attr_index = r.read_json(attribution / 'index.private.json')
    require(len(attr_index['reports']) == 2 * len(ids) and
            len({row['report'] for row in attr_index['reports']}) == 2 * len(ids) and
            {(row['id'], row['kind']) for row in attr_index['reports']} ==
            {(item, kind) for item in ids for kind in ('native', 'reference')}, 'Attribution cohort changed')
    for row in attr_index['reports']:
        require(Path(row['report']).name == row['report'], 'Unsafe attribution filename')
        source = next(item for item in manifest['sources'] if item['id'] == row['id'])
        suffix = '.reference.cr3' if row['kind'] == 'reference' else '.native.candidate.cr3'
        require(r.read_json(attribution / row['report']) == a.strict(__import__('json').dumps(
            a.analyze(Path(source['path']).read_bytes(), (prior / (row['id'] + suffix)).read_bytes()))),
            'Frozen attribution no longer reproduces')
    (root / 'control_private.source.py').write_bytes(Path(__file__).read_bytes())
    descriptor = subprocess.run(['icacls', str(root)], capture_output=True, check=True)
    (root / 'root-acl.private.txt').write_bytes(descriptor.stdout)
    r.dump(root / 'scoped-review.private.json', {'ticket': 105, 'priorRoot': str(prior),
        'attributionRoot': str(attribution), 'priorManifestSha256': r.sha(prior / 'capture-manifest.private.json'),
        'attributionManifestSha256': r.sha(attribution / 'capture-manifest.private.json'),
        'admissionManifest': scoped['admissionManifest'], 'grants': grants, 'tools': scoped['tools'],
        'toolClosures': closures, 'sourceGuard': scoped['sourceGuard'],
        'driverSha256': r.sha(Path(__file__)), 'publishReports': 'denied',
        'scope': 'Original-value assignment only into fresh private derivatives; retained changed-date artifacts are read-only.',
        'productionMutationAllowed': False})
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if key in os.environ}
    env.update(PATH=str(Path(manifest['perl']['path']).parent) + os.pathsep + str(Path(os.environ['SYSTEMROOT']) / 'System32'),
               PERL5LIB=manifest['perlLibrary'], LC_ALL='C', LANG='C', TZ='UTC0')
    r.dump(root / 'environment.private.json', env)
    records, results = [], []
    for source in manifest['sources']:
        prefix, path = source['id'], Path(source['path'])
        changed = prior / (prefix + '.reference.cr3')
        original_state = r.fingerprint(path)
        retained_state = r.fingerprint(changed)
        holder = subprocess.Popen([str(guard), str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = {'id': prefix, 'sourcePath': str(path), 'sourceSha256': source['sha256'],
                  'sourceBefore': original_state, 'changedBefore': retained_state,
                  'changedPath': str(changed), 'changedSha256': r.sha(changed), 'productionMutationAllowed': False}
        try:
            require(holder.stdout.readline() == b'guard-open\n', 'Source guard failed')
            require(original_state[0] == source['sha256'] and r.fingerprint(path) == original_state,
                    'Guarded source binding changed')
            data = path.read_bytes()
            original_date = date_bytes(data)
            require(original_date != r.DATE, 'Same and changed intent collide')
            output = root / (prefix + '.same-value.cr3')
            require(not output.exists(), 'Derivative collision')
            result.update(originalDateAscii20Hex=original_date.hex(), outputPath=str(output))

            def metadata(label, item):
                process = run(root, prefix + '-' + label, [manifest['perl']['path'], manifest['reference']['path'],
                    '-config', '', '-j', '-a', '-u', '-G0:1:4:5', '-s', '-n', '-api', 'RequestAll=3', item],
                    [path, changed, item], records, env)
                require(process.returncode == 0 and not process.stderr, 'Metadata read failed')
                values = r.strict_json(process.stdout)
                require(len(values) == 1, 'Unexpected metadata row count')
                return values[0]

            before_values = metadata('source-read', path)
            keys = [key for key in before_values if key.endswith(':DateTimeOriginal')]
            require(len(keys) == 1 and keys[0].startswith('EXIF:ExifIFD:') and
                    before_values[keys[0]].encode('ascii') + b'\0' == original_date, 'Reference original value mismatch')
            write = run(root, prefix + '-same-write', [manifest['perl']['path'], manifest['reference']['path'],
                '-config', '', '-ExifIFD:DateTimeOriginal=' + original_date[:-1].decode('ascii'), '-o', output, path],
                [path, changed], records, env)
            result.update(referenceTargetKey=keys[0], writeExit=write.returncode, outputExists=output.exists())
            if not output.is_file():
                result['outcome'] = 'no-artifact-short-circuit-or-refusal'
            elif write.returncode != 0:
                result.update(outcome='incomplete-artifact', outputSha256=r.sha(output))
            else:
                require(output.stat().st_size <= r.MAX_SOURCE, 'Derivative exceeds bound')
                same = output.read_bytes()
                require(date_bytes(same) == original_date, 'Same-value date changed')
                report = classify(data, same, changed.read_bytes())
                report['positionalSourceSame'] = r.summarize_runs(data, same)
                report['positionalSameChanged'] = r.summarize_runs(same, changed.read_bytes())
                same_values = metadata('same-read', output)
                require(same_values.get(keys[0]) == before_values[keys[0]], 'Same-value metadata target changed')
                changed_values = metadata('changed-read', changed)
                report.update(sourceSameMetadataChanges=r.metadata_changes(before_values, same_values),
                              sameChangedMetadataChanges=r.metadata_changes(same_values, changed_values))
                decoded = Path(str(output) + '.pgm')
                require(not decoded.exists(), 'Decoder collision')
                unpack = run(root, prefix + '-same-unpack', [manifest['decoder']['path'], output],
                             [path, changed, output], records, env)
                report['unpackComplete'] = (unpack.returncode == 0 and not unpack.stderr and b'Unpacked' in unpack.stdout and decoded.is_file())
                report['decodedBaselineEqual'] = r.sha(decoded) == r.sha(source['baselineDecoded']) if report['unpackComplete'] else None
                report['retainedChangedUnpackPath'] = str(Path(str(changed) + '.pgm'))
                report['retainedChangedDecodedBaselineEqual'] = r.sha(Path(str(changed) + '.pgm')) == r.sha(source['baselineDecoded'])
                r.dump(root / (prefix + '-comparison.private.json'), report)
                result.update(outcome=report['outcome'], outputSha256=r.sha(output), report=prefix + '-comparison.private.json')
        except Exception as error:
            result.update(outcome='unexplained-or-refused-retained', errorType=type(error).__name__, error=str(error))
        finally:
            result['sourceAfter'] = r.fingerprint(path)
            result['changedAfter'] = r.fingerprint(changed)
            result['sourceUnchanged'] = original_state == r.fingerprint(path)
            result['retainedChangedUnchanged'] = retained_state == r.fingerprint(changed)
            if holder.poll() is None:
                holder.communicate(b'release\n', timeout=10)
            result['guardExit'] = holder.returncode
            results.append(result)
            r.dump(root / 'results.private.json', results)
            require(result['sourceUnchanged'] and result['retainedChangedUnchanged'] and holder.returncode == 0,
                    'Input preservation or guard failure')
    frozen(prior)
    frozen(attribution)
    r.dump(root / 'summary.private.json', {'ticket': 105, 'publicReportsPermitted': False,
        'productionMutationAllowed': False, 'formatAdmissionEnabled': False,
        'causalNecessityEstablished': False, 'semanticIndependenceEstablished': False})
    r.dump(root / 'capture-manifest.private.json', {path.name: r.sha(path) for path in root.iterdir() if path.is_file()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('prior', 'attribution', 'root', 'guard'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    qualify(args.prior.resolve(), args.attribution.resolve(), args.root.resolve(), args.guard.resolve())
    print('Private control retained; inspect the selected private root.')

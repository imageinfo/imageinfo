"""Read-only superseding classification of immutable #0105 media captures."""
import argparse
import json
from pathlib import Path

import control_private as c


def bound_report(name, manifest):
    c.require(isinstance(name, str) and Path(name).name == name and
              name not in ('', '.', '..') and not any(char in name for char in ':\\/') and
              name in manifest, 'Unsafe or unbound captured report name')
    return name


def reclassify(control, root):
    c.require(root.is_dir() and not root.is_symlink() and not list(root.iterdir()), 'Fresh empty private analysis root required')
    control_manifest = c.frozen(control)
    scoped = c.r.read_json(control / 'scoped-review.private.json')
    c.require(c.r.sha(control / 'control_private.source.py') == scoped['driverSha256'], 'Captured write driver changed')
    prior, attribution = Path(scoped['priorRoot']), Path(scoped['attributionRoot'])
    c.require(c.r.sha(prior / 'capture-manifest.private.json') == scoped['priorManifestSha256'] and
              c.r.sha(attribution / 'capture-manifest.private.json') == scoped['attributionManifestSha256'], 'Frozen lineage changed')
    c.frozen(prior)
    c.frozen(attribution)
    manifest = c.r.read_json(Path(scoped['admissionManifest']['path']))
    c.require(c.r.sha(Path(scoped['admissionManifest']['path'])) == scoped['admissionManifest']['sha256'], 'Source admission changed')
    c.cohort(manifest)
    c.require(c.r.validate_grants(manifest, c.REPOSITORY) == scoped['grants'], 'Frozen grants changed')
    bindings = {'mediaRoot': str(control), 'mediaManifestSha256': c.r.sha(control / 'capture-manifest.private.json'),
                'writeDriverSha256': scoped['driverSha256'], 'classifierSha256': c.r.sha(Path(c.__file__)),
                'reclassifierSha256': c.r.sha(Path(__file__)), 'ticket': 105,
                'scope': 'Read-only classification correction for missing relationships. No reference, metadata or decoder processes.',
                'publishReports': 'denied', 'productionMutationAllowed': False}
    (root / 'control_private.analysis.source.py').write_bytes(Path(c.__file__).read_bytes())
    (root / 'reclassify_private.source.py').write_bytes(Path(__file__).read_bytes())
    c.r.dump(root / 'scoped-review.private.json', bindings)
    results = c.r.read_json(control / 'results.private.json')
    c.require({row['id'] for row in results} == c.cohort(manifest) and len(results) == len(manifest['sources']), 'Control cohort changed')
    reports = []
    for row in results:
        if 'report' not in row:
            reports.append({'id': row['id'], 'outcome': row['outcome'], 'report': None})
            continue
        name = bound_report(row['report'], control_manifest)
        source = next(item for item in manifest['sources'] if item['id'] == row['id'])
        paths = [Path(row[key]) for key in ('sourcePath', 'outputPath', 'changedPath')]
        expected = [Path(source['path']), control / (row['id'] + '.same-value.cr3'),
                    prior / (row['id'] + '.reference.cr3')]
        c.require([path.resolve() for path in paths] == [path.resolve() for path in expected],
                  'Captured paths differ from admitted source and derived lineage')
        before = {str(path): c.r.fingerprint(path) for path in paths}
        c.require(before[str(paths[0])][0] == row['sourceSha256'] and
                  before[str(paths[1])][0] == row['outputSha256'] and
                  before[str(paths[2])][0] == row['changedSha256'], 'Captured artifact binding changed')
        original, same, changed = [path.read_bytes() for path in paths]
        corrected = c.classify(original, same, changed)
        captured = c.r.read_json(control / name)
        # JSON normalization preserves the frozen tuple/list representation.
        normalized = json.loads(json.dumps(corrected))
        c.require(all(captured[key] == value for key, value in normalized.items()
                      if key != 'cellClassification'), 'Correction changed an unrelated relationship')
        captured['cellClassification'] = normalized['cellClassification']
        c.r.dump(root / name, captured)
        c.require(before == {str(path): c.r.fingerprint(path) for path in paths}, 'Input changed during read-only reclassification')
        reports.append({'id': row['id'], 'report': row['report'], 'inputsBefore': before, 'inputsAfter': before})
    c.frozen(control)
    c.r.dump(root / 'index.private.json', {'ticket': 105, 'reports': reports,
        'publicReportsPermitted': False, 'productionMutationAllowed': False})
    c.r.dump(root / 'capture-manifest.private.json', {path.name: c.r.sha(path) for path in root.iterdir() if path.is_file()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    reclassify(args.control.resolve(), args.root.resolve())
    print('Read-only private classification retained; original captures unchanged.')

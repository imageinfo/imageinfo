"""Finite #0087 proposal QA. No media parser, privacy scanner or removal API."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'docs/privacy'
PIN = '2200871d9cef988051d2a99d67df3bda6cbb30a8'
EXIF_XMP = 'http://ns.adobe.com/exif/1.0/'
AUX_XMP = 'http://ns.adobe.com/exif/1.0/aux/'
EXIFEX_XMP = 'http://cipa.jp/exif/1.0/'
UPSTREAM = f'https://github.com/exiftool/exiftool/blob/{PIN}/lib/Image/ExifTool/'
SOURCE_URLS = {'SRC-GPS': UPSTREAM+'GPS.pm', 'SRC-EXIF': UPSTREAM+'Exif.pm',
               'SRC-CANON': UPSTREAM+'Canon.pm', 'SRC-CR3-LOCATIONS': UPSTREAM+'Canon.pm',
               'SRC-XMP-GPS': 'https://developer.adobe.com/xmp/docs/xmp-namespaces/exif/',
               'SRC-XMP-AUX': UPSTREAM+'XMP.pm', 'SRC-XMP-EXIFEX': UPSTREAM+'XMP.pm',
               'SRC-CIPA-2017': 'https://cipa.jp/std/documents/e/DC-X010-2017.pdf'}
# Revision 1 contains prose policy fields. Lock their reviewed canonical bytes
# rather than pretending keyword matching can detect a weakened promise. A policy
# edit requires deliberate review and an explicit update of this QA constant.
REVIEWED_POLICY_SHA256 = 'c73beafe929a1b424f588c8239126161d3a51b472a10b1a01c903a189c429cb8'


class Rejected(ValueError):
    pass


def strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Rejected('duplicate JSON member')
            result[key] = value
        return result

    def invalid(value):
        raise Rejected('nonfinite JSON constant '+value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def read(path):
    return strict(path.read_text(encoding='utf-8'))


def identity(selector):
    if selector['kind'] == 'native':
        return ('native', selector['namespace'], selector['nativeId'])
    return ('xmp', selector['namespaceUri'], selector['localName'])


def expected_identities():
    result = {}
    gps = ('0x0001', '0x0002', '0x0003', '0x0004', '0x0005', '0x0006', '0x0007',
           '0x0013', '0x0014', '0x0015', '0x0016', '0x001d')
    for native in gps:
        result[('native', 'tiff-gps', native)] = ('gps', {'cr3.cmt4.gps', 'preview.exif.gps'})
    for native, category in [('0xa430', 'owner'), ('0xa431', 'serial'), ('0xa435', 'serial')]:
        result[('native', 'tiff-exif', native)] = (category, {'cr3.cmt2.exif', 'preview.exif.exif'})
    for native, category in [('0x0009', 'owner'), ('0x000c', 'serial'), ('0x0096', 'serial')]:
        result[('native', 'canon-main', native)] = (category, {'cr3.cmt3.canon'})
    gps_names = ('GPSLatitude', 'GPSLongitude', 'GPSAltitude', 'GPSAltitudeRef',
                 'GPSTimeStamp', 'GPSDestLatitude', 'GPSDestLongitude')
    for name in gps_names:
        result[('xmp', EXIF_XMP, name)] = ('gps', {'sidecar.xmp', 'preview.xmp'})
    for uri, names in [(AUX_XMP, ('OwnerName', 'SerialNumber', 'LensSerialNumber')),
                       (EXIFEX_XMP, ('CameraOwnerName', 'BodySerialNumber', 'LensSerialNumber'))]:
        for name, category in zip(names, ('owner', 'serial', 'serial')):
            result[('xmp', uri, name)] = (category, {'sidecar.xmp', 'preview.xmp'})
    return result


def policy_digest(catalog):
    policy = {key: catalog[key] for key in ('occurrenceRules', 'protectedData', 'exclusions',
                                           'unknownPolicy', 'authenticityCatalog', 'claims')}
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def semantic(catalog, fixture_plan):
    entries = catalog['entries']
    ids = [entry['id'] for entry in entries]
    if len(ids) != len(set(ids)) or set(ids) != {f'R5P-{number:03}' for number in range(1, 32)}:
        raise Rejected('catalog occurrence selector identifiers must be unique and complete')
    expected = expected_identities()
    found = [identity(entry['selector']) for entry in entries]
    if len(found) != len(set(found)) or set(found) != set(expected):
        raise Rejected('missing, duplicate, invented or widened exact selector')
    fixture_ids = {case['id'] for case in fixture_plan['cases']}
    sources = catalog['sources']
    source_ids = [source['id'] for source in sources]
    if len(source_ids) != len(set(source_ids)) or set(source_ids) != set(SOURCE_URLS):
        raise Rejected('missing, extra or duplicate source reference identifier')
    for source in sources:
        if source['observedOn'] != '2026-10-15' or source['url'] != SOURCE_URLS[source['id']]:
            raise Rejected('source observation date not declared')
        if 'github.com/exiftool/exiftool/' in source['url'] and (
                f'/blob/{PIN}/' not in source['url'] or source['revision'] != PIN):
            raise Rejected('upstream source is not pinned to reviewed revision')
        if (source['id'] == 'SRC-XMP-GPS' and source['revision'] is not None
                or source['id'] == 'SRC-CIPA-2017'
                and source['revision'] != 'CIPA DC-X010-2017, Exif 2.31 metadata for XMP'):
            raise Rejected('live/unversioned or historical standard revision misrepresented')
    for entry in entries:
        category, locations = expected[identity(entry['selector'])]
        selected_locations = entry['selector']['locations']
        if (entry['category'] != category or set(selected_locations) != locations
                or len(selected_locations) != len(locations)):
            raise Rejected('selector category or declared occurrence locations changed')
        if entry['occurrenceRule'] != 'every-exact-property-occurrence':
            raise Rejected('equal/repeated occurrences cannot be collapsed')
        refs = entry['sourceRefs']
        if not refs or len(refs) != len(set(refs)) or not set(refs) <= set(source_ids):
            raise Rejected('missing, duplicate or unresolved primary source reference')
        selector = entry['selector']
        if selector['kind'] == 'native':
            primary = {'tiff-gps': 'SRC-GPS', 'tiff-exif': 'SRC-EXIF', 'canon-main': 'SRC-CANON'}[selector['namespace']]
            required_sources = {primary, 'SRC-CR3-LOCATIONS'}
        else:
            primary = {EXIF_XMP: 'SRC-XMP-GPS', AUX_XMP: 'SRC-XMP-AUX', EXIFEX_XMP: 'SRC-XMP-EXIFEX'}[selector['namespaceUri']]
            required_sources = {primary}
        if (selector.get('namespace') == 'tiff-exif' or selector.get('namespaceUri') == EXIFEX_XMP):
            required_sources.add('SRC-CIPA-2017')
        if not required_sources <= set(refs):
            raise Rejected('selector primary identity/location source not referenced')
        families = entry['fixtureFamilies']
        if not families or len(families) != len(set(families)) or not set(families) <= fixture_ids:
            raise Rejected('missing, duplicate or unknown fixture-family reference')
    if any(type(value) is not bool or value for value in catalog['claims'].values()):
        raise Rejected('catalog proposal cannot claim an implementation or privacy outcome')
    if policy_digest(catalog) != REVIEWED_POLICY_SHA256:
        raise Rejected('reviewed occurrence/protection/exclusion/refusal policy changed')
    known = (PACKAGE/catalog['authenticityCatalog']).resolve()
    if known != (ROOT/'docs/write-safety/known-authenticity.v1.json').resolve():
        raise Rejected('authenticity refusal catalog reference changed')
    authenticity = read(known)
    if (authenticity['productionMutationAllowed'] or authenticity['cryptographicValidationPerformed']
            or authenticity['generalAuthenticityAbsenceEstablished']):
        raise Rejected('known-provenance indicators do not qualify mutation or absence')


def fixture_trace(trace, catalog, fixture_plan):
    if set(trace) != {'schemaVersion', 'kind', 'catalogId', 'catalogRevision', 'basis', 'families'}:
        raise Rejected('fixture trace fields')
    if (type(trace['schemaVersion']) is not int or trace['schemaVersion'] != 1
            or trace['catalogId'] != catalog['catalogId']
            or type(trace['catalogRevision']) is not int or trace['catalogRevision'] != catalog['revision']
            or trace['kind'] != 'privacy-catalog-fixture-trace'
            or trace['basis'] != 'authored-plan-trace-not-execution-evidence'):
        raise Rejected('fixture trace version or evidence domain')
    expected = {case['id'] for case in fixture_plan['cases']}
    families = trace['families']
    ids = [family['id'] for family in families]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise Rejected('all fixture families need one explicit disposition')
    catalog_ids = {entry['id'] for entry in catalog['entries']}
    for family in families:
        if set(family) != {'id', 'disposition', 'entryRefs', 'obligation', 'execution'}:
            raise Rejected('fixture family fields')
        if family['disposition'] not in {'required-future-evidence', 'context-only', 'excluded-operation', 'excluded-variant'}:
            raise Rejected('fixture applicability disposition')
        if (family['execution'] != 'not-executed-by-this-catalog' or not family['obligation']
                or len(family['entryRefs']) != len(set(family['entryRefs']))
                or not set(family['entryRefs']) <= catalog_ids):
            raise Rejected('fixture trace cannot invent execution or selector references')
    # Every entry's nominated family has a reciprocal future obligation.
    by_id = {family['id']: family for family in families}
    if any(by_id[identifier]['disposition'] != 'excluded-variant' for identifier in ('FXP-027', 'FXP-028')):
        raise Rejected('secondary C-RAW/DPRAW variants remain explicitly excluded')
    for entry in catalog['entries']:
        for family in entry['fixtureFamilies']:
            if (entry['id'] not in by_id[family]['entryRefs']
                    or by_id[family]['disposition'] != 'required-future-evidence'):
                raise Rejected('entry/family trace lacks reciprocal coverage')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', type=Path)
    args = parser.parse_args()
    catalog = read(PACKAGE/'r5-catalog.v1.json')
    schema = read(PACKAGE/'r5-catalog.schema.json')
    plan = read(ROOT/'docs/fixture-plan/case-plan.v1.json')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(catalog)
    semantic(catalog, plan)
    trace = read(PACKAGE/'fixture-trace.v1.json')
    fixture_trace(trace, catalog, plan)
    vectors = read(PACKAGE/'catalog-vectors.v1.json')
    results = []
    for case in vectors['cases']:
        if 'wire' in case:
            try:
                strict(case['wire'])
            except (Rejected, json.JSONDecodeError):
                accepted = False
            else:
                accepted = True
            assert accepted == case['accepted'], case['id']
            results.append({'id': case['id'], 'passed': True})
            continue
        value = deepcopy(trace if case['target'] == 'trace' else catalog)
        for edit in case['changes']:
            parent = value
            for part in edit['path'][:-1]:
                parent = parent[part]
            parent[edit['path'][-1]] = deepcopy(edit['value'])
        try:
            if case['target'] == 'trace':
                fixture_trace(value, catalog, plan)
            else:
                validator.validate(value)
                semantic(value, plan)
        except (Rejected, ValidationError, ValueError, KeyError, TypeError):
            accepted = False
        else:
            accepted = True
        assert accepted == case['accepted'], case['id']
        results.append({'id': case['id'], 'passed': True})
    summary = {'ticket': 87, 'kind': 'privacy-catalog-proposal-qa', 'observedOn': '2026-10-15',
               'catalogEntries': len(catalog['entries']), 'fixtureFamiliesTraced': len(trace['families']),
               'vectors': results, 'allPassed': True, 'mediaFixturesExecuted': 0,
               'primaryIdentityReview': 'Selected identifiers reviewed against pinned upstream source, Adobe EXIF namespace and historical CIPA2017 mapping; no R5 presence claim.',
               'privateMediaValuesOrHashesIncluded': False, 'runtimeInspectionImplemented': False,
               'removalImplemented': False, 'anonymityEstablished': False}
    if args.public:
        args.public.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'catalogEntries': len(catalog['entries']), 'fixtureFamiliesTraced': len(trace['families']),
                      'vectors': len(results), 'allPassed': True}))


if __name__ == '__main__':
    main()

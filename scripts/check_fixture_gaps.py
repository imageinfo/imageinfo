"""Public #0071 ledger QA; reads no media, private reports or board state.

Schema/cross-reference checks do not establish the truth of prose coverage claims.
Those claims still require review against the explicitly classified sources.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/fixture-plan'
METHOD_ONLY = {
    'docs/write-safety/cr3-reference-effects.md',
    'docs/write-safety/cr3-rewrite-attribution.md',
    'experiments/0099-cr3-reference-effects/README.md',
    'experiments/0102-cr3-rewrite-attribution/README.md',
}
NEXT_TICKETS = {18, 72, 74, 75, 92}
SPLIT_FIRST = 'Split one bounded executable child before any execution.'


class Rejected(ValueError):
    pass


def require(value, message):
    if not value:
        raise Rejected(message)


def strict(text):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result

    def nonfinite(value):
        raise Rejected('Nonfinite JSON constant: ' + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path):
    with Path(path).open('rb') as stream:
        data = stream.read(512 * 1024 + 1)
    require(len(data) <= 512 * 1024, 'QA JSON input exceeds 512 KiB')
    return strict(data.decode('utf-8'))


def unique(rows, name):
    result = {row['id']: row for row in rows}
    require(len(result) == len(rows), 'Duplicate ' + name + ' identity')
    return result


def refs(values, expected, name, nonempty=True):
    require((bool(values) or not nonempty) and len(values) == len(set(values))
            and set(values) <= set(expected), 'Missing/duplicate/unresolved ' + name)


def public_path(value, root):
    path = PurePosixPath(value)
    require(value and '\\' not in value and ':' not in value and not path.is_absolute()
            and all(part not in ('..', '.local', '.git') for part in path.parts)
            and not any(part.startswith('.') for part in path.parts),
            'Evidence must be an ordinary public repository path')
    candidate = (root / Path(*path.parts)).resolve()
    require(candidate.is_relative_to(root.resolve()) and candidate.is_file(),
            'Missing or escaping public evidence source')
    require(not any(part.startswith('.') for part in candidate.relative_to(root.resolve()).parts),
            'Evidence alias resolves into private or hidden repository state')
    return path.as_posix()


def semantic(ledger, plan, root=ROOT):
    planned = unique(plan['cases'], 'planned fixture family')
    families = unique(ledger['families'], 'fixture family')
    assertions = unique(ledger['assertions'], 'assertion')
    evidence = unique(ledger['evidenceSources'], 'evidence source')
    require(len(planned) == 29 and families.keys() == planned.keys(),
            'Every one of the 29 planned fixture families needs a disposition')
    require(assertions, 'The finite current gap ledger cannot be empty')
    require([row['rank'] for row in ledger['assertions']] == list(range(1, len(assertions) + 1)),
            'Priority ranks must be unique, contiguous and in displayed order')
    require(len({row['path'] for row in evidence.values()}) == len(evidence),
            'Evidence paths must not masquerade as independent sources through duplicate IDs')
    for source in evidence.values():
        path = public_path(source['path'], root)
        if path in METHOD_ONLY:
            require(source['class'] == 'method-only',
                    'Private #0099/#0102 outcomes cannot be imported through their public method')
    for identifier, family in families.items():
        require(family['sourcePriority'] == planned[identifier]['priority'],
                'Original fixture priority cannot be silently promoted or downgraded')
        refs(family['assertionRefs'], assertions, 'family assertion reference', nonempty=False)
        refs(family['evidenceRefs'], evidence, 'family evidence reference')
        if family['disposition'] == 'active-gap':
            require(family['sourcePriority'] == 'P0' and family['assertionRefs'],
                    'Active P0 gaps need exact P0 assertion references')
        if identifier in ('FXP-027', 'FXP-028'):
            require(family['disposition'] == 'deferred-secondary' and not family['assertionRefs'],
                    'Secondary RAW modes cannot become first full-RAW release gates')
        for ref in family['assertionRefs']:
            require(identifier in assertions[ref]['familyRefs'], 'One-way family/assertion reference')
    for identifier, assertion in assertions.items():
        refs(assertion['familyRefs'], families, 'assertion fixture family')
        refs(assertion['evidenceRefs'], evidence, 'assertion evidence')
        require(any(evidence[ref]['class'] != 'method-only' for ref in assertion['evidenceRefs']),
                'A public method alone supplies no current assertion-coverage evidence')
        require(assertion['nextTicket'] in NEXT_TICKETS,
                'Gap must route to a scoped #0071 follow-on, not authorize unrelated work')
        if assertion['nextTicket'] == 18:
            require(SPLIT_FIRST in assertion['prerequisites'],
                    'An umbrella route must require a bounded child before execution')
        for family in assertion['familyRefs']:
            require(families[family]['sourcePriority'] == 'P0'
                    and identifier in families[family]['assertionRefs'],
                    'Current P0 assertion must retain a bidirectional P0 family link')
        access = assertion['access']
        if access['execution'] == 'authored-only':
            require(access['publication'] == 'public-authored-only',
                    'Public authored controls must not be presented as camera evidence')
        elif access['execution'] == 'restricted-existing-after-review':
            require(access['publication'] == 'private-camera-only',
                    'Restricted camera execution cannot grant public result permission')
        if assertion['nextTicket'] == 74:
            require(access['execution'] == 'not-authorized'
                    and access['publication'] == 'private-camera-only',
                    'Targeted acquisition is a scoped future need, never an active media request')


def validate(ledger, schema, plan):
    require(not any(ref and not ref.startswith('#') for ref in schema_refs(schema)),
            'QA schema must resolve locally without fetching references')
    Draft202012Validator(schema).validate(ledger)
    semantic(ledger, plan)


def schema_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '$ref':
                yield item
            else:
                yield from schema_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from schema_refs(item)


def altered(ledger, operation):
    """Domain mutations challenge joins, disclosure boundaries and prioritization."""
    result = deepcopy(ledger)
    if operation == 'omit-family':
        result['families'].pop()
    elif operation == 'duplicate-family':
        result['families'][-1] = deepcopy(result['families'][0])
    elif operation == 'change-source-priority':
        result['families'][0]['sourcePriority'] = 'P2'
    elif operation == 'duplicate-rank':
        require(len(result['assertions']) >= 2, 'Rank negative vector requires two assertions')
        result['assertions'][1]['rank'] = result['assertions'][0]['rank']
    elif operation == 'break-family-backlink':
        row = next(row for row in result['families'] if row['assertionRefs'])
        row['assertionRefs'].pop()
    elif operation == 'unknown-evidence':
        result['assertions'][0]['evidenceRefs'] = ['invented-source']
    elif operation == 'private-evidence-path':
        result['evidenceSources'][0]['path'] = '.local/camera-results.private.json'
    elif operation == 'promote-private-method':
        row = next(row for row in result['evidenceSources'] if row['path'] in METHOD_ONLY)
        row['class'] = 'published-private-summary'
    elif operation == 'method-only-assertion-evidence':
        result['assertions'][0]['evidenceRefs'] = [next(row['id'] for row in result['evidenceSources']
                                                       if row['class'] == 'method-only')]
    elif operation == 'camera-publication-permission':
        row = next(row for row in result['assertions']
                   if row['access']['execution'] == 'restricted-existing-after-review')
        row['access']['publication'] = 'public-authored-only'
    elif operation == 'secondary-release-gate':
        row = next(row for row in result['families'] if row['id'] == 'FXP-027')
        row['disposition'] = 'active-gap'
    elif operation == 'unrelated-ticket':
        result['assertions'][0]['nextTicket'] = 71
    elif operation == 'umbrella-direct-execution':
        row = next(row for row in result['assertions'] if row['nextTicket'] == 18)
        row['prerequisites'].remove(SPLIT_FIRST)
    else:
        raise Rejected('Unknown authored mutation')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, default=PACKAGE / 'p0-assertion-gaps.v1.json')
    args = parser.parse_args()
    schema = read(PACKAGE / 'p0-assertion-gaps.schema.json')
    Draft202012Validator.check_schema(schema)
    ledger = read(args.ledger)
    plan = read(PACKAGE / 'case-plan.v1.json')
    validate(ledger, schema, plan)
    operations = ('omit-family', 'duplicate-family', 'change-source-priority', 'duplicate-rank',
                  'break-family-backlink', 'unknown-evidence', 'private-evidence-path',
                  'promote-private-method', 'method-only-assertion-evidence',
                  'camera-publication-permission', 'secondary-release-gate', 'unrelated-ticket',
                  'umbrella-direct-execution')
    for operation in operations:
        variant = altered(ledger, operation)
        rejected = False
        try:
            validate(variant, schema, plan)
        except (Rejected, ValidationError):
            rejected = True
        require(rejected, 'Authored invalid ledger passed: ' + operation)
    for malformed in ('{"same":1,"same":2}', '{"number":NaN}'):
        try:
            strict(malformed)
        except Rejected:
            continue
        raise Rejected('Invalid lexical JSON passed')
    print(f'Fixture-gap ledger: 29 families reconciled; {len(operations) + 2} authored invalid vectors refused; no media read')


if __name__ == '__main__':
    main()

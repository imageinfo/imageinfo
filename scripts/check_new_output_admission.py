"""Check #0176's unsupported trace; never creates a storage capability."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/write-safety'
WS_IDS = [f'WS-{n:03d}' for n in (*range(9, 17), 19, 22, 23, 24)]
SAF_IDS = [f'SAF-{n:03d}' for n in range(1, 17)]
PREDICATES = {
    'PreparedSourceNamespacePreservedOnNativeError',
    'NativeCandidateFileFlushError', 'NativeInstalledNamespaceFlushError',
    'NativeReceiptFileFlushError', 'ExactLiveConfigurationAndImplementationBinding',
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate(ws, saf):
    require(ws['ticket'] == saf['ticket'] == 176, 'ticket')
    require(ws['authority'] is False and saf['authority'] is False, 'authority')
    require(ws['disposition'] == 'unsupported', 'unsupported disposition')
    source = (ROOT / ws['normative_source']['path']).read_bytes()
    require(hashlib.sha256(source).hexdigest() == ws['normative_source']['sha256'], 'normative identity')
    text = source.decode('utf-8')
    clauses = dict((match.group(1), match.group(0).strip()) for match in re.finditer(
        r'^\*\*(WS-\d{3})\b.*?(?=^\*\*WS-\d{3}\b|^## |\Z)', text, re.M | re.S))
    require([r['id'] for r in ws['requirements']] == WS_IDS, 'WS denominator/order')
    for row in ws['requirements']:
        require(row['normative_text'] == clauses[row['id']], 'exact WS clause')
        require(row['disposition'] == 'unsupported-profile-with-bounded-evidence', 'WS disposition')
        require(set(row['missing_or_contradicted_predicates']) <= PREDICATES, 'WS predicates')
    require({r['predicate'] for r in ws['unmet_predicates']} == PREDICATES and
            len(ws['unmet_predicates']) == 5, 'five WS predicates')
    require(all(r['corrective_owner'] and r['required_work'] for r in ws['unmet_predicates']), 'WS corrective owner')
    require([r['id'] for r in saf['scenarios']] == SAF_IDS, 'SAF denominator/order')
    table = {}
    for line in (ROOT / saf['contract']).read_text(encoding='utf-8').splitlines():
        if line.startswith('| SAF-'):
            parts = [part.strip() for part in line.split('|')[1:-1]]
            table[parts[0]] = {'setup': parts[1], 'requiredOutcome': parts[2], 'rules': parts[3].split(', ')}
    for row in saf['scenarios']:
        require(row['normativeClause'] == table[row['id']], 'exact SAF clause')
        require(row['disposition'] == 'scoped-mechanism-evidence; full-scenario-not-certified', 'SAF disposition')
        require(bool(row['remaining']), 'SAF residual')
        require(all((ROOT / path).is_file() for path in row['codeRefs']), 'SAF code reference')
    require({r['id'] for r in saf['necessaryUnresolvedPredicates']} == PREDICATES and
            len(saf['necessaryUnresolvedPredicates']) == 5, 'five SAF predicates')
    require(all(r['correctiveOwner'] and r['requiredOutcome'] for r in saf['necessaryUnresolvedPredicates']), 'SAF corrective owner')
    selector = (ROOT / 'src/storage/admission.rs').read_text(encoding='utf-8')
    actual = set(re.findall(r'predicate: Predicate::(\w+)', selector))
    require(actual == PREDICATES, 'compiled predicates')
    require('_unavailable: Infallible' in selector, 'sealed capability')
    caller = (ROOT / 'src/storage/new_output.rs').read_text(encoding='utf-8')
    require(caller.index('let admission = select_profile') < caller.index('.construct('), 'caller ordering')
    require('admission: &AdmittedByteSink' in caller and 'owner: &mut RetainedSession' in caller,
            'actual owner/capability seam')
    for path in ('src/storage/admission/tests.rs', 'src/storage/new_output/tests.rs'):
        require((ROOT / path).is_file(), 'actual test reference')


def main():
    ws = json.loads((BASE / 'new-output-admission-ws.json').read_text(encoding='utf-8'))
    saf = json.loads((BASE / 'new-output-admission-saf.json').read_text(encoding='utf-8'))
    validate(ws, saf)
    mutations = (
        ('authority', lambda w, s: w.update(authority=True)),
        ('positive', lambda w, s: w.update(disposition='admitted')),
        ('omit-WS', lambda w, s: w['requirements'].pop()),
        ('rewrite-WS', lambda w, s: w['requirements'][0].update(normative_text='shortened')),
        ('omit-predicate', lambda w, s: w['unmet_predicates'].pop()),
        ('omit-SAF', lambda w, s: s['scenarios'].pop()),
        ('rewrite-SAF', lambda w, s: s['scenarios'][0]['normativeClause'].update(setup='changed')),
        ('erase-residual', lambda w, s: s['scenarios'][0].update(remaining='')),
        ('certify-scenario', lambda w, s: s['scenarios'][0].update(disposition='certified')),
    )
    for name, mutation in mutations:
        left, right = deepcopy(ws), deepcopy(saf)
        mutation(left, right)
        try:
            validate(left, right)
        except (ValueError, KeyError):
            continue
        raise ValueError('negative control accepted: ' + name)
    print('Unsupported admission trace: 12 WS / 16 SAF / 5 predicates; 9 rejection controls pass. No admission granted.')


if __name__ == '__main__':
    main()

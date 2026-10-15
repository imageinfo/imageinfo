"""Independent authored binding, alias and causal-classification challenges."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import importlib.util

import audit_private as audit

DATE = b'2024:02:29 12:34:56\0'
EDIT = b'2001:02:03 04:05:06\0'


def atom(kind, payload):
    return struct.pack('>I4s', len(payload) + 8, kind) + payload


def authored(date=DATE, other=b'opaque', alias=False, duplicate=False):
    data = bytearray(b'II' + struct.pack('<HIH', 42, 8, 2))
    data += struct.pack('<HHII', 0x9003, 2, 20, 38)
    data += struct.pack('<HHII', 0x9003 if duplicate else 0x1234, 7,
                        20 if alias else len(other), 38 if alias else 58)
    data += b'\0' * 4 + date + other
    return atom(b'moov', atom(b'uuid', audit.witness.CANON + atom(b'CMT2', data))) + atom(b'mdat', b'marker')


class IndependentControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[2] / '.local').mkdir(exist_ok=True)

    def test_exact_date_and_same_value_are_independently_observed(self):
        self.assertEqual(audit.selected_date(authored())[0], DATE)
        for value in (b'2023:02:29 12:34:56\0', b'2024:02:29 12:34:60\0', DATE[:-1] + b'X'):
            with self.assertRaises(audit.Refused):
                audit.selected_date(authored(value))

    def test_alias_and_duplicate_occurrence_refuse(self):
        for data in (authored(alias=True), authored(duplicate=True)):
            with self.assertRaises(audit.Refused):
                audit.selected_date(data)

    def test_shared_reference_change_is_no_necessity_claim(self):
        rows = audit.allocation_relations(authored(), authored(other=b'normal'),
                                         authored(EDIT, other=b'normal'))
        by_tag = {row['key'][2]: row for row in rows}
        self.assertEqual(by_tag[0x1234]['classification'], 'shared-reference-value-change')
        self.assertEqual(by_tag[0x9003]['classification'], 'changed-date-output-only-value-change')
        self.assertFalse(any('safe' in row['classification'] for row in rows))

    def test_distinct_and_same_only_changes_are_retained(self):
        for same, changed, expected in ((b'normal', b'opaque', 'same-value-output-only-value-change'),
                                        (b'normal', b'foobar', 'three-distinct-values')):
            row = next(row for row in audit.allocation_relations(authored(), authored(other=same),
                       authored(EDIT, other=changed)) if row['key'][2] == 0x1234)
            self.assertEqual(row['classification'], expected)

    def test_complete_runs_and_separate_length_suffix(self):
        result = audit.run_summary(b'abcdef', b'aXcdYYZ')
        pairs = ((1, 1), (4, 2), (6, 1))
        expected = hashlib.sha256(b''.join(struct.pack('>QQ', *row) for row in pairs)).hexdigest()
        self.assertEqual(result['completeRunSequenceSha256'], expected)
        self.assertEqual((result['runCount'], result['changedBytes'], result['samples']),
                         (3, 4, [list(pair) for pair in pairs]))
        self.assertEqual(audit.run_summary(b'', b'')['runCount'], 0)

    def test_manifest_rejects_escape_and_changed_binding(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / '.local') as directory:
            root = Path(directory)
            (root / 'capture-manifest.private.json').write_text(json.dumps({'../secret': '0' * 64}))
            with self.assertRaises(audit.Refused):
                audit.manifest(root)
            (root / 'marker').write_bytes(b'marker')
            (root / 'capture-manifest.private.json').write_text(json.dumps({'marker': '0' * 64}))
            with self.assertRaises(audit.Refused):
                audit.manifest(root)

    def test_manifest_complete_file_denominator_is_required(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / '.local') as directory:
            root = Path(directory)
            (root / 'marker').write_bytes(b'marker')
            record = {'marker': audit.digest(b'marker')}
            (root / 'capture-manifest.private.json').write_text(json.dumps(record))
            self.assertEqual(audit.manifest(root), record)
            (root / 'omitted').write_bytes(b'keep')
            with self.assertRaises(audit.Refused):
                audit.manifest(root)

    def test_collision_and_frozen_root_output_refuse(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / '.local') as directory:
            root = Path(directory)
            existing = root / 'existing'
            existing.write_bytes(b'keep')
            with self.assertRaises(audit.Refused):
                audit.fresh_destination(root / 'other', existing)
            self.assertEqual(existing.read_bytes(), b'keep')
            with self.assertRaises(audit.Refused):
                audit.fresh_destination(root, root / 'new-audit')
            self.assertFalse((root / 'new-audit').exists())

    def test_duplicate_lineage_rows_and_json_members_refuse(self):
        with self.assertRaises(audit.Refused):
            audit.unique_rows([{'id': 'one'}, {'id': 'one'}])
        with self.assertRaises(audit.Refused):
            audit.strict('{"source": 1, "source": 2}')

    def test_whole_source_grant_result_cohort_is_required(self):
        sources = [{'id': 'one', 'sha256': 'a'}]
        grants = [{'id': 'one', 'sourceSha256': 'a', 'publishReports': 'denied'}]
        results = [{'id': 'one', 'sourceSha256': 'a'}]
        audit.bind_cohort(sources, grants, results)
        for altered in ([], [{'id': 'one', 'sourceSha256': 'b'}],
                        [{'id': 'two', 'sourceSha256': 'a'}]):
            with self.assertRaises(audit.Refused):
                audit.bind_cohort(sources, grants, altered)
        grants[0]['publishReports'] = 'allowed'
        with self.assertRaises(audit.Refused):
            audit.bind_cohort(sources, grants, results)

    def test_independent_checker_rejects_tampered_causal_classification(self):
        spec = importlib.util.spec_from_file_location('test105_runner', Path(__file__).with_name('control_private.py'))
        subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(subject)
        original, same, changed = authored(), authored(other=b'normal'), authored(EDIT, other=b'normal')
        report = subject.classify(original, same, changed)
        report['positionalSourceSame'] = subject.r.summarize_runs(original, same)
        report['positionalSameChanged'] = subject.r.summarize_runs(same, changed)
        report = json.loads(json.dumps(report))
        audit.verify_comparisons(report, original, same, changed)
        for mutation in ('classification', 'denominator', 'necessity', 'runDigest'):
            altered = deepcopy(report)
            if mutation == 'classification':
                altered['cellClassification'][0]['classification'] = 'safe'
            elif mutation == 'denominator':
                altered['cellClassification'].pop()
            elif mutation == 'necessity':
                altered['causalNecessityEstablished'] = True
            else:
                altered['positionalSourceSame']['completeRunSequenceSha256'] = '0' * 64
            with self.assertRaises(audit.Refused):
                audit.verify_comparisons(altered, original, same, changed)

    def test_missing_relationships_cannot_be_shared_or_date_associated(self):
        def cell(old, new, equal=False):
            return {'role': 'authored', 'sourceLength': old, 'candidateLength': new,
                    'candidateSha256': 'same' if new is not None else None, 'bytesEqual': equal}
        for a, b, wrong in ((cell(4, None), cell(4, None), 'shared-rewrite-observation'),
                            (cell(None, 4), cell(None, 4), 'shared-rewrite-observation'),
                            (cell(4, 4, True), cell(4, None), 'changed-date-associated-observation')):
            report = {'sourceSame': {'cellComparisons': [a]},
                      'sourceChanged': {'cellComparisons': [b]},
                      'cellClassification': [{'role': 'authored', 'classification': 'unexplained'}],
                      'causalNecessityEstablished': False, 'semanticIndependenceEstablished': False}
            audit.verify_classification(report)
            report['cellClassification'][0]['classification'] = wrong
            with self.assertRaises(audit.Refused):
                audit.verify_classification(report)

    def test_boundary_flags_cannot_be_missing_or_true(self):
        value = {key: False for key in ('productionMutationAllowed', 'formatAdmissionEnabled', 'publicReportsPermitted')}
        audit.verify_false_flags(value)
        for key in value:
            altered = deepcopy(value)
            altered[key] = True
            with self.assertRaises(audit.Refused):
                audit.verify_false_flags(altered)

    def test_metadata_added_removed_null_and_categories_are_distinct(self):
        rows = audit.metadata_changes({'EXIF:a': None, 'Composite:a': 1, 'File:System:a': 2},
                                      {'EXIF:b': None, 'Composite:a': 2, 'File:System:a': 3})
        self.assertEqual({row['class'] for row in rows},
                         {'stored-or-other', 'derived-composite', 'filesystem-observation'})
        self.assertEqual(len(rows), 4)


if __name__ == '__main__':
    unittest.main()

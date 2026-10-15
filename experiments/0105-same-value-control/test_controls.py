"""Authored marker controls, never camera observations."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = load('control105', Path(__file__).with_name('control_private.py'))
rc = load('reclassification105', Path(__file__).with_name('reclassify_private.py'))
t = load('authored102', Path(__file__).parents[1] / '0102-cr3-rewrite-attribution/test_controls.py')


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (c.REPOSITORY / '.local').mkdir(exist_ok=True)

    def test_reclassification_report_names_bound_before_effects(self):
        manifest = {'authored.private.json': 'authored-only'}
        self.assertEqual(rc.bound_report('authored.private.json', manifest), 'authored.private.json')
        for name in ('../escape.json', 'a/b.json', 'a\\b.json', 'a:stream', 'missing.json', '', '..'):
            with self.assertRaises(ValueError):
                rc.bound_report(name, manifest)

    def test_original_date_independent_ascii20_both_orders(self):
        for order in ('<', '>'):
            self.assertEqual(c.date_bytes(t.authored(order)), b'2020:02:29 12:34:56\0')

    def test_invalid_date_refuses(self):
        with self.assertRaises(ValueError):
            c.date_bytes(t.authored(date=b'2021:02:29 12:34:56\0'))

    def test_noop_artifact_is_not_rewrite_necessity(self):
        original = t.authored()
        report = c.classify(original, original, t.authored(date=c.r.DATE))
        self.assertEqual(report['outcome'], 'byte-identical-no-op-artifact')
        self.assertIn('changed-date-associated-observation', {row['classification'] for row in report['cellClassification']})
        self.assertFalse(report['causalNecessityEstablished'])
        self.assertFalse(report['semanticIndependenceEstablished'])

    def test_shared_rewrite_and_residual_remain_observations(self):
        report = c.classify(t.authored(), t.authored(gap=12, tail=0),
                            t.authored(gap=12, tail=0, date=c.r.DATE))
        self.assertEqual(report['outcome'], 'rewritten-artifact')
        self.assertIn('shared-rewrite-observation', {row['classification'] for row in report['cellClassification']})

    def test_different_rewrites_remain_unexplained(self):
        report = c.classify(t.authored(), t.authored(gap=12, tail=0),
                            t.authored(gap=20, tail=0, date=c.r.DATE))
        self.assertIn('unexplained', {row['classification'] for row in report['cellClassification']})

    def test_missing_or_added_relationships_never_imply_shared_rewrite(self):
        import struct

        def renamed(data):
            result = bytearray(data)
            block = next(box for box in c.a.inspect(data)['boxes'] if box['kind'] == 'CMT2')
            struct.pack_into('<H', result, block['body'] + 22, 0x101)
            return bytes(result)

        original, changed = t.authored(), t.authored(date=c.r.DATE)
        for same, other in ((renamed(original), renamed(changed)), (original, renamed(changed))):
            report = c.classify(original, same, other)
            pairs = [{row['role']: row for row in report[key]['cellComparisons']}
                     for key in ('sourceSame', 'sourceChanged')]
            missing = {role for pair in pairs for role, row in pair.items()
                       if row['sourceLength'] is None or row['candidateLength'] is None}
            self.assertTrue(missing)
            self.assertTrue(all(row['classification'] == 'unexplained'
                                for row in report['cellClassification'] if row['role'] in missing))

    def test_alias_date_refuses(self):
        data = bytearray(t.authored())
        inventory = c.a.inspect(data)
        block = inventory['cmts']['CMT2']
        values = list(block['allocations'].values())
        selected = next(row for row in values if row['key'][2] == 0x9003)
        other = next(row for row in values if row['key'][2] != 0x9003)
        import struct
        # Redirect the second entry's ASCII20 value to the selected extent.
        table = next(box for box in inventory['boxes'] if box['kind'] == 'CMT2')['body']
        struct.pack_into('<HHII', data, table + 22, 0x100, 2, 20, selected['offset'] - table)
        self.assertIsNotNone(other)
        with self.assertRaises(ValueError):
            c.date_bytes(data)

    def test_duplicate_and_path_source_ids_refuse(self):
        for ids in (['x', 'x'], ['../x']):
            with self.assertRaises(ValueError):
                c.cohort({'sources': [{'id': item} for item in ids]})

    def test_frozen_hash_and_traversal_refuse(self):
        with tempfile.TemporaryDirectory(dir=c.REPOSITORY / '.local') as tmp:
            root = Path(tmp)
            (root / 'artifact').write_bytes(b'authored')
            c.r.dump(root / 'capture-manifest.private.json', {'artifact': c.r.sha(root / 'artifact')})
            c.frozen(root)
            (root / 'artifact').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                c.frozen(root)
            c.r.dump(root / 'capture-manifest.private.json', {'../artifact': 'bad'})
            with self.assertRaises(ValueError):
                c.frozen(root)


if __name__ == '__main__':
    unittest.main()

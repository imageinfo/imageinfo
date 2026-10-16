"""Authored negative controls for the independent checked-custody auditor."""
import copy
import unittest

import audit


def safe(**values):
    return {**dict.fromkeys(audit.FLAGS, False), **values}


def context():
    def info(index, size=100):
        return {'identity': '1:'+format(index, 'x'), 'size': size, 'links': 1,
                'attributes': 32, 'creationTime': 100, 'lastWriteTime': 200}
    root = info(1, 0)
    root['attributes'] = 16
    prior = {'purpose': 'imageinfo-od11-caller-context-v1', 'stage': 'after-publication',
             'stoppedBeforePublication': False, 'persistenceMode': 'write-through',
             'root': root, 'source': info(2, 65536), 'candidate': info(3, 65536),
             'sha256': audit.MARKER, 'records': [
                 {'name': name, 'info': info(index), 'sha256': '0'*64}
                 for index, name in enumerate(('prepared', 'intent', 'observation'), 4)]}
    return {'purpose': 'imageinfo-od11-receipt-context-v1', 'prior': prior,
            'receipt': {'info': info(7), 'sha256': '0'*64}}


def events():
    value = context()
    result = [safe(callerContext=value['prior'])]
    for name in audit.prior.PREFIX:
        if name in ('receipt-file-flushed', 'receipt-parent-flushed'):
            result.extend([safe(checkedReceiptBoundary=name, receiptFileFlushSucceeded=True,
                                originalPropertiesMatch=True),
                           safe(receiptContext=copy.deepcopy(value), observationOnly=True)])
        result.append(safe(barrier=name))
    result.append(safe(outcome=audit.prior.SUCCESS, receiptFileFlushSucceeded=True,
                       receiptParentFlushSucceeded=True, finalCheckPassed=True))
    return result


def status():
    return {**safe(), 'automaticDurableCustody': False, 'actorSha256': audit.ACTOR,
            'inspectorSha256': audit.INSPECTOR, 'receiptMode': audit.MODE,
            'chargedBytes': 655360, 'operationCount': 1, 'custodySnapshots': 4,
            'originalEventCount': 26, 'checkedReceiptExports': 2, 'inspectionCount': 1,
            'checkedReceiptContextEligible': True}


class EventControls(unittest.TestCase):
    def rejected(self, value):
        with self.assertRaises(ValueError):
            audit.checked_contract(value, complete=True)

    def test_exact_complete_and_unreleased_prefix(self):
        self.assertEqual(len(audit.checked_contract(events(), True)), 2)
        prefix = events()[:7]
        self.assertEqual(audit.checked_contract(prefix, False), [])

    def test_fabricated_early_context(self):
        value = events()
        value.insert(1, safe(receiptContext=context(), observationOnly=True))
        self.rejected(value)

    def test_missing_boundary(self):
        value = events()
        index = next(i for i, row in enumerate(value) if 'checkedReceiptBoundary' in row)
        del value[index]
        self.rejected(value)

    def test_changed_receipt_binding(self):
        value = events()
        row = [row for row in value if 'receiptContext' in row][-1]
        row['receiptContext']['receipt']['info']['lastWriteTime'] += 1
        self.rejected(value)

    def test_terminal_only_success(self):
        self.rejected([events()[-1]])

    def test_duplicate_boundary_and_lost_barrier(self):
        for mutation in ('duplicate', 'missing'):
            value = events()
            index = next(i for i, row in enumerate(value) if 'checkedReceiptBoundary' in row)
            if mutation == 'duplicate':
                value.insert(index, copy.deepcopy(value[index]))
            else:
                del value[2]
            with self.subTest(mutation=mutation):
                self.rejected(value)

    def test_capability_and_false_final_check(self):
        for key in ('committed', 'finalCheckPassed'):
            value = events()
            value[-1][key] = key == 'committed'
            with self.subTest(key=key):
                self.rejected(value)

    def test_incomplete_claim_cannot_use_checked_context(self):
        with self.assertRaises(ValueError):
            audit.checked_contract(events(), False)

    def test_duplicate_json_member(self):
        with self.assertRaises(ValueError):
            audit.prior.decode('{"committed":false,"committed":true}')


class CustodyControls(unittest.TestCase):
    def test_status_requires_exact_provenance_and_false_authority(self):
        audit.safe_status(status())
        for key, value in [('actorSha256', 'f'*64), ('inspectorSha256', audit.ACTOR),
                           ('receiptMode', 'ordinary-receipt'), ('automaticDurableCustody', True),
                           ('committed', True), ('custodySnapshots', 5),
                           ('originalEventCount', 129), ('checkedReceiptExports', True)]:
            changed = status()
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.safe_status(changed)

    def test_refusal_requires_no_launch_and_no_artifact_effect(self):
        item = {'label': 'inspect', 'eventStart': 5, 'eventEnd': 5,
                'before': {'source': 'same'}, 'after': {'source': 'same'},
                'result': {'returned': None, 'error': {'type': 'Refused'}}}
        audit.refusal({'operations': [item]}, 'inspect')
        for key, value in [('eventEnd', 6), ('after', {'source': 'changed'})]:
            changed = copy.deepcopy(item)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.refusal({'operations': [changed]}, 'inspect')

    def test_inventory_rejects_unexpected_and_dual_namespace(self):
        for names in ({'foreign.record': {}}, {'candidate.marker': {}, 'output.marker': {}}):
            with self.subTest(names=names), self.assertRaises(ValueError):
                audit.inventory_contract({'transaction': names, 'custody': {}})


if __name__ == '__main__':
    unittest.main()

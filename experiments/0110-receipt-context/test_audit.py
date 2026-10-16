"""Authored negative controls for the independent #0110 auditor."""
import copy
import unittest

import audit


def safe(**values):
    return {**dict.fromkeys(audit.FLAGS, False), **values}


def sample_context():
    def info(index, size=100):
        return {'identity': '1:'+format(index, 'x'), 'size': size, 'links': 1,
                'attributes': 32, 'creationTime': 100, 'lastWriteTime': 200}
    root = info(1, 0)
    root['attributes'] = 16
    prior = {'purpose': 'imageinfo-od11-caller-context-v1', 'stage': 'after-publication',
        'stoppedBeforePublication': False, 'persistenceMode': 'write-through',
        'root': root, 'source': info(2, 65536), 'candidate': info(3, 65536),
        'sha256': audit.old.MARKER, 'records': [
            {'name': name, 'info': info(index), 'sha256': '0'*64}
            for index, name in enumerate(('prepared', 'intent', 'observation'), 4)]}
    return {'purpose': 'imageinfo-od11-receipt-context-v1', 'prior': prior,
            'receipt': {'info': info(7), 'sha256': '0'*64}}


def sample_events():
    context = sample_context()
    events = [safe(callerContext=context['prior']), safe(barrier='receipt-written')]
    for phase in ('receipt-file-flushed', 'receipt-parent-flushed'):
        events.extend([safe(checkedReceiptBoundary=phase,
                            receiptFileFlushSucceeded=True, originalPropertiesMatch=True),
                       safe(receiptContext=copy.deepcopy(context)), safe(barrier=phase)])
    return events


class EventControls(unittest.TestCase):
    def refused(self, events):
        with self.assertRaises(ValueError):
            audit.event_contract(events)

    def test_actual_checked_schedule(self):
        self.assertEqual(len(audit.event_contract(sample_events())), 2)

    def test_no_export_before_flush_is_valid(self):
        self.assertEqual(audit.event_contract(sample_events()[:2]), [])

    def test_fabricated_early_context(self):
        events = sample_events()
        events.insert(1, safe(receiptContext=sample_context()))
        self.refused(events)

    def test_fabricated_check_before_written(self):
        events = sample_events()
        events.pop(1)
        self.refused(events)

    def test_missing_full_check_marker(self):
        events = sample_events()
        events.pop(2)
        self.refused(events)

    def test_false_original_properties_match(self):
        events = sample_events()
        events[2]['originalPropertiesMatch'] = False
        self.refused(events)

    def test_missing_flush_success(self):
        events = sample_events()
        del events[2]['receiptFileFlushSucceeded']
        self.refused(events)

    def test_timestamp_rebase(self):
        events = sample_events()
        events[6]['receiptContext']['receipt']['info']['lastWriteTime'] += 1
        self.refused(events)

    def test_stale_prior_adoption(self):
        events = sample_events()
        events[3]['receiptContext']['prior']['source']['lastWriteTime'] += 1
        self.refused(events)

    def test_duplicate_boundary(self):
        events = sample_events()
        events[5]['checkedReceiptBoundary'] = 'receipt-file-flushed'
        events[7]['barrier'] = 'receipt-file-flushed'
        self.refused(events)

    def test_fabricated_capability(self):
        events = sample_events()
        events[2]['committed'] = True
        self.refused(events)

    def test_missing_capability(self):
        events = sample_events()
        del events[3]['repairAllowed']
        self.refused(events)

    def test_invalid_boolean_timestamp(self):
        events = sample_events()
        events[3]['receiptContext']['receipt']['info']['lastWriteTime'] = True
        self.refused(events)

    def test_duplicate_json_member(self):
        with self.assertRaises(ValueError):
            audit.decode('{"committed":false,"committed":true}')

    def test_retain_native_mtime_conflict(self):
        context = sample_context()
        inventory = {}
        for name, info in audit.old.context_info(context).items():
            if name == '.':
                continue
            inventory[name] = {'identity': int(info['identity'].split(':')[1], 16),
                'size': info['size'], 'links': info['links'], 'attributes': info['attributes'],
                'mtime': (info['lastWriteTime']-116444736000000000)*100}
        inventory['receipt.record']['mtime'] += 100
        with self.assertRaises(ValueError):
            audit.compare_native_context(context, inventory)
        audit.compare_native_context(context, inventory, stale=True)


class ReadyControls(unittest.TestCase):
    def setUp(self):
        self.binding = {'actorSha256':'a'*64,'observerSha256':'b'*64,
                        'inspectorSha256':'c'*64,'guestAgentSha256':'d'*64}
        ready = {key:value for key,value in self.binding.items() if key != 'guestAgentSha256'}
        ready.update(instance='00000000-0000-0000-0000-000000000001', scriptSha256='d'*64)
        hello = {'at':1,'path':'/hello','value':{'groups':['S-1-16-8192'],
            'build':'26300','scriptSha256':'d'*64,'boot':'2026-10-16T00:00:00+00:00'}}
        event = {'at':2,'path':'/event','value':{'id':'ready','event':ready}}
        response = {'at':3,'path':'/result','value':{
            'id':'ready-'+'e'*32,'challenge':'e'*32,'ready':copy.deepcopy(ready)}}
        self.proof = {'readyEvent':event,'challengeResult':response,'hello':hello}

    def test_exact_current_ready_challenge(self):
        self.assertEqual(audit.ready_proof(self.proof,self.binding,list(self.proof.values()))[1],3)

    def test_hello_alone_is_insufficient(self):
        with self.assertRaises(ValueError):
            audit.ready_proof(self.proof,self.binding,[self.proof['hello']])

    def test_wrong_actor_payload(self):
        self.proof['readyEvent']['value']['event']['actorSha256'] = 'f'*64
        with self.assertRaises(ValueError):
            audit.ready_proof(self.proof,self.binding,list(self.proof.values()))

    def test_other_agent_answers_challenge(self):
        self.proof['challengeResult']['value']['ready']['instance'] = '00000000-0000-0000-0000-000000000002'
        with self.assertRaises(ValueError):
            audit.ready_proof(self.proof,self.binding,list(self.proof.values()))

    def test_challenge_precedes_downloads(self):
        self.proof['challengeResult']['at'] = 1.5
        with self.assertRaises(ValueError):
            audit.ready_proof(self.proof,self.binding,list(self.proof.values()))


if __name__ == '__main__':
    unittest.main()

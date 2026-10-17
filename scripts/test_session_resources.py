"""Authored actual-pipe correctness and retained failure controls for #0146."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import audit_session_resources as audit
import measure_session_resources as collect


class SessionResources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(os.environ.get('IMAGEINFO_SESSION_BINARY', collect.ROOT/'target/debug/imageinfo.exe')).resolve()
        cls.scratch = tempfile.TemporaryDirectory(dir=collect.ROOT/'.local', prefix='session146-qa-')
        cls.root = Path(cls.scratch.name)/'run'
        collect.prepare(cls.root, cls.binary)
        (cls.root/'captures').mkdir()
        cls.oracles = audit.load(cls.root/'oracles.private.json')

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_actual_failure_then_valid_isolation(self):
        cases = ['usage', 'selected', 'missing', 'all', 'invalid', 'selected', 'all']
        cell = dict(name='isolation-control', cases=cases, control=None)
        row = collect.run_cell(self.binary, self.root/'fixtures', cell, self.root/'captures')
        report = audit.audit_cell(self.root, row, ('isolation-control',cases,'close',0,None), self.oracles)
        self.assertTrue(report['eligible'])
        for change in ('id', 'latency', 'lf'):
            broken = copy.deepcopy(row)
            if change=='id':
                broken['name']='wrong'
            elif change=='latency':
                broken['requests'][0]['latencyNs'] += 1
            else:
                broken['received'][0]['completeLf']=False
            with self.assertRaises(ValueError):
                audit.audit_cell(self.root,broken,('isolation-control',cases,'close',0,None),self.oracles)

    def test_actual_boundary_controls(self):
        for cell, expected in zip(collect.plan()[9:], audit.schedule()[9:]):
            with self.subTest(cell=cell['name']):
                row=collect.run_cell(self.binary,self.root/'fixtures',cell,self.root/'captures')
                self.assertTrue(audit.audit_cell(self.root,row,expected,self.oracles)['eligible'])

    def test_censored_no_final_frame_and_timeout_are_retained(self):
        original=subprocess.Popen
        ready=json.dumps(dict(kind='session-ready',protocolVersion=1,allowApply=False,limits=dict(
            maxInputFrameBytes=524288,maxOutputFrameBytes=16777728,maxFrames=256,maxQueuedRequests=0,
            maxTokens=128,maxTokenBytes=32768,maxTotalTokenBytes=65536,maxInputs=4,
            maxMetadataBytes=8388608,maxResultBytes=16777216)))+'\n'
        for name,tail,watchdog in [('no-final','import time;time.sleep(0.05)',3000),('timeout','import time;time.sleep(10)',1000)]:
            script=f'import sys;sys.stdout.write({ready!r});sys.stdout.flush();'+tail
            with patch.object(collect.subprocess,'Popen',side_effect=lambda *a,**k:original([sys.executable,'-c',script],**k)):
                row=collect.run_cell(self.binary,self.root/'fixtures',dict(name=name,cases=['selected'],control=None),self.root/'captures',watchdog)
            self.assertTrue(row['censored'])
            self.assertEqual(row['requests'][0]['completeOffsetNs'],None)
            self.assertEqual(row['requests'][0]['latencyNs'],None)
            self.assertEqual(row['outcome'],'no-final-frame' if name=='no-final' else 'timeout')
            self.assertGreater(row['stdoutCapturedBytes'],0)
            report=audit.audit_cell(self.root,row,(name,['selected'],'close',0,None),self.oracles)
            self.assertFalse(report['eligible'])

    def test_encoded_boundaries_and_lifetime_denominator(self):
        self.assertEqual(len(collect.plan()),16)
        self.assertEqual(sum(len(x['cases']) for x in collect.plan()),960)
        for cell in collect.plan()[12:15]:
            self.assertEqual(len(collect.requests(cell)[0][0]),524288)
        self.assertEqual(len(collect.requests(collect.plan()[-1])),256)

    def test_censored_prefix_semantics_and_checkpoint_rejections(self):
        cases=['selected','all']
        name='adversarial'
        row=collect.run_cell(self.binary,self.root/'fixtures',dict(name=name,cases=cases,control=None),self.root/'captures')
        expectation=(name,cases,'close',0,None)
        path=self.root/'captures'/f'{name}.stdout'
        original=path.read_bytes()
        for fault in ('id','status','isolation','malformed'):
            with self.subTest(censored=fault):
                broken=copy.deepcopy(row)
                broken.update(censored=True,outcome='timeout')
                pieces=original.splitlines(keepends=True)
                value=json.loads(pieces[1])
                if fault=='id':
                    value['id']='wrong'
                elif fault=='status':
                    value['result']['summary']['exitStatus']=2
                elif fault=='isolation':
                    value['result']['files'][0]['snapshot']['occurrences']=[]
                pieces[1]=b'{bad-json\n' if fault=='malformed' else json.dumps(value,separators=(',',':')).encode()+b'\n'
                data=b''.join(pieces)
                path.write_bytes(data)
                broken.update(stdoutBytes=len(data),stdoutCapturedBytes=len(data),stdoutSha256=hashlib.sha256(data).hexdigest())
                broken['received'][1].update(bytes=len(pieces[1]),sha256=hashlib.sha256(pieces[1]).hexdigest())
                with self.assertRaises(ValueError):
                    audit.audit_cell(self.root,broken,expectation,self.oracles)
        path.write_bytes(original)
        for point in (-1,len(row['telemetry']['samples']),len(row['telemetry']['samples'])-1):
            broken=copy.deepcopy(row)
            broken['readyCheckpoint']=point
            for request in broken['requests']:
                request['checkpoint']=point
            with self.assertRaises(ValueError):
                audit.audit_cell(self.root,broken,expectation,self.oracles)
        unavailable=copy.deepcopy(row)
        unavailable['requests'][1].update(checkpoint=None,checkpointUnavailable='process-exited')
        report=audit.audit_cell(self.root,unavailable,expectation,self.oracles)
        self.assertIsNone(report['retainedState']['workingSetBytes']['delta'])
        self.assertIn('unavailable',report['retainedState']['workingSetBytes']['unavailableReason'])

    def test_exact_binding_inventory(self):
        p=audit.load(self.root/'prepared.private.json')
        r=dict(bindings={str(path):collect.base.digest(path) for path in (self.binary,*(collect.ROOT/name for name in collect.TOOLS))},
               bindingsUnchanged=True,sourceBinding=p['sourceBinding'],sourceBindingUnchanged=True)
        audit.audit_bindings(r,p)
        for key in tuple(r['bindings']):
            broken=copy.deepcopy(r)
            del broken['bindings'][key]
            with self.assertRaises(ValueError):
                audit.audit_bindings(broken,p)
        broken=copy.deepcopy(r)
        broken['bindings']['extra.py']='0'*64
        with self.assertRaises(ValueError):
            audit.audit_bindings(broken,p)
        broken=copy.deepcopy(r)
        broken['sourceBinding']['files']['Cargo.toml']='0'*64
        with self.assertRaises(ValueError):
            audit.audit_bindings(broken,p)


if __name__=='__main__':
    unittest.main()

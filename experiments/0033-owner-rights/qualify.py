"""Owned marker property/topology qualification; no media or host crash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading


class Worker:
    def __init__(self,binary,mode,path,capture):
        self.capture=capture;self.events=[];self.lines=[];self.controls=[];self.queue=queue.Queue()
        argv=[str(binary),mode,str(path)];(capture/'argv.json').write_text(json.dumps(argv),encoding='utf-8')
        self.p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.timer=threading.Timer(90,self.p.kill);self.timer.daemon=True;self.timer.start()
        def reader():
            for line in self.p.stdout:self.queue.put(line)
            self.queue.put(None)
        self.thread=threading.Thread(target=reader,daemon=True);self.thread.start()
    def next(self):
        line=self.queue.get(timeout=30);assert line is not None
        self.lines.append(line);event=json.loads(line);self.events.append(event)
        assert not event.get('committed',False) and not event.get('productionPublicationAllowed',False)
        return event
    def barrier(self,name):
        while True:
            event=self.next()
            if event.get('barrier')==name:return
    def send(self,word='continue'):
        self.controls.append(word);self.p.stdin.write(word+'\n');self.p.stdin.flush()
    def finish(self,kill=False):
        if kill and self.p.poll() is None:self.p.kill()
        code=self.p.wait(timeout=30);self.timer.cancel();self.thread.join(timeout=5)
        while not self.queue.empty():
            line=self.queue.get_nowait()
            if line is not None:
                self.lines.append(line);self.events.append(json.loads(line))
        (self.capture/'stdout.jsonl').write_text(''.join(self.lines),encoding='utf-8')
        (self.capture/'stderr.txt').write_text(self.p.stderr.read(),encoding='utf-8')
        (self.capture/'events.json').write_text(json.dumps(self.events),encoding='utf-8')
        (self.capture/'controls.json').write_text(json.dumps(self.controls),encoding='utf-8')
        return code


def run(binary,parent):
    if not __debug__:raise RuntimeError('Qualification assertions require Python without -O')
    binary=Path(binary).resolve();parent=Path(parent).resolve();parent.mkdir(parents=True,exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='owner-rights-',dir=parent));cases=[]
    actor=Path(__file__).with_name('actor.py').resolve()
    if os.name!='nt':
        result=subprocess.run([str(binary),'admit',str(root/'absent.marker')],capture_output=True,text=True,timeout=30)
        assert result.returncode==5 and 'OWNER_RIGHTS_WINDOWS_UNVERIFIED' in result.stderr and not list(root.iterdir())
        return {'caseCount':1,'cases':[{'id':'unsupported-platform','workerArtifacts':0}],'productionPublicationAllowed':False,'enabledProfiles':0}

    def action(name,path,capture,preopen=False):
        argv=[sys.executable,str(actor),('preopen-' if preopen else '')+name,str(path)]
        if preopen:
            p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            assert json.loads(p.stdout.readline())['preopened'];return p
        p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        assert p.returncode==0,p.stderr
        (capture/(name+'-actor.json')).write_text(json.dumps({'argv':argv,'stdout':p.stdout,'stderr':p.stderr}),encoding='utf-8')
        return json.loads(p.stdout)

    for mode in ['ordinary','fresh-restricted','minimal-restricted','fresh-sealed']:
        for name in ['read','mtime','readonly','dacl','owner-access','ads','write','link','delete','rename']:
            case=root/(mode+'-'+name);case.mkdir();path=case/'stage.marker';capture=case/'worker';capture.mkdir()
            worker=Worker(binary,mode,path,capture)
            try:
                worker.barrier('created');worker.send();worker.barrier('guarded')
                result=action(name,path,case)
                worker.send();code=worker.finish()
                observation=next(event for event in worker.events if event.get('outcome')=='owned-marker-observed')
                assert code==0 and observation['contentUnchanged'] and observation['identityUnchanged']
                if name=='read':assert result['allowed']
                if name in ['write','delete','rename']:assert not result['allowed']
                if mode!='ordinary' and name in ['mtime','readonly','dacl','owner-access']:assert not result['allowed']
                if mode=='fresh-sealed' and name in ['ads','link']:assert not result['allowed']
                if mode=='fresh-sealed':assert observation['privatePropertyPolicyMatches'] and observation['mtimeUnchanged'] and observation['attributesUnchanged'] and observation['defaultStreamOnly'] and observation['linkCount']==1
                record={'id':case.name,'policy':mode,'actor':name,**result,'contentUnchanged':True,'identityUnchanged':True,
                        'policyMatches':observation['privatePropertyPolicyMatches'],'mtimeUnchanged':observation['mtimeUnchanged'],'attributesUnchanged':observation['attributesUnchanged'],'defaultStreamOnly':observation['defaultStreamOnly'],'linkCount':observation['linkCount'],'committed':False}
                cases.append(record);print(json.dumps(record),flush=True)
            finally:
                if worker.p.poll() is None:worker.finish(kill=True)
    for name in ['mtime','dacl']:
        case=root/('preopened-'+name);case.mkdir();path=case/'stage.marker';capture=case/'worker';capture.mkdir()
        worker=Worker(binary,'seal-after-open',path,capture);contender=None
        try:
            worker.barrier('created');contender=action(name,path,case,preopen=True)
            worker.send();worker.barrier('guarded')
            contender.stdin.write('continue\n');contender.stdin.flush()
            stdout,stderr=contender.communicate(timeout=30);assert contender.returncode==0,stderr
            result=json.loads(stdout);(case/'preopened-actor.json').write_text(json.dumps({'stdout':stdout,'stderr':stderr}),encoding='utf-8')
            fresh=action(name,path,case)
            worker.send();assert worker.finish()==0
            record={'id':case.name,'preexistingHandleActor':result,'freshHandleActor':fresh,'committed':False}
            cases.append(record);print(json.dumps(record),flush=True)
        finally:
            if contender is not None and contender.poll() is None:contender.kill();contender.wait()
            if worker.p.poll() is None:worker.finish(kill=True)
    for mode in ['fresh-restricted','retained-security','sealed-exit','fresh-sealed']:
        case=root/('after-exit-'+mode);case.mkdir();path=case/'stage.marker';capture=case/'worker';capture.mkdir()
        worker=Worker(binary,mode,path,capture)
        worker.barrier('created');worker.send()
        if mode!='sealed-exit':worker.barrier('guarded');worker.send()
        assert worker.finish()==0
        results={name:action(name,path,case) for name in ['read','write','ads','mtime','owner-access','link']}
        if mode=='fresh-sealed':assert not results['write']['allowed'] and not results['ads']['allowed']
        record={'id':case.name,'postExitActors':results,'holderRestoration':next((event.get('holderCanRestorePrivateDacl') for event in worker.events if 'holderCanRestorePrivateDacl' in event),None),'committed':False}
        cases.append(record);print(json.dumps(record),flush=True)
    for name,phase,policy in [('read','published','publish-restricted'),('mtime','published','publish-restricted'),('link','published','publish-restricted'),('mtime','guarded','publish-restricted'),('ads','published','publish-sealed'),('link','published','publish-sealed'),('read','published','publish-sealed')]:
        case=root/(policy+'-'+phase+'-'+name);case.mkdir();path=case/'request.marker';capture=case/'worker';capture.mkdir()
        worker=Worker(binary,policy,path,capture)
        try:
            worker.barrier('created');worker.send();worker.barrier('guarded')
            if phase=='published':worker.send();worker.barrier('published')
            target=case/'txn'/('output.marker' if phase=='published' else 'stage.marker')
            result=action(name,target,case)
            worker.send()
            if phase=='guarded':worker.barrier('published');worker.send()
            assert worker.finish()==0
            observation=next(e for e in worker.events if e.get('outcome')=='owned-marker-observed')
            assert observation['contentUnchanged'] and observation['identityUnchanged'] and observation['privatePropertyPolicyMatches']
            record={'id':case.name,**result,'heldPublicationAndFlushObserved':True,'linkCount':observation['linkCount'],'committed':False}
            cases.append(record);print(json.dumps(record),flush=True)
        finally:
            if worker.p.poll() is None:worker.finish(kill=True)
    result=subprocess.run([str(binary),'admit',str(root/'absent.marker')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0 and json.loads(result.stdout)['outcome']=='refused-before-effects' and not (root/'absent.marker').exists()
    cases.append({'id':'strict-admission','artifactsCreated':False,'committed':False})
    for phase in ['created','guarded','published']:
        for event in ['kill','cancel','collision']:
            if event=='collision' and phase!='guarded':continue
            case=root/(event+'-'+phase);case.mkdir();path=case/'request.marker';capture=case/'worker';capture.mkdir()
            worker=Worker(binary,'publish-sealed',path,capture)
            try:
                worker.barrier('created')
                if phase!='created':worker.send();worker.barrier('guarded')
                if phase=='published':worker.send();worker.barrier('published')
                target=case/'txn'/'output.marker'
                if event=='collision':
                    with target.open('xb') as output:output.write(b'winning-marker')
                    worker.send();code=worker.finish()
                    assert code==5 and target.read_bytes()==b'winning-marker'
                elif event=='cancel':worker.send('cancel');code=worker.finish();assert code==5
                else:code=worker.finish(kill=True)
                if phase=='published':assert target.read_bytes()==b'3'*65536
                elif event!='collision':assert not target.exists()
                cases.append({'id':case.name,'interruption':event,'phase':phase,'candidateOutputObserved':phase=='published','foreignWinnerRetained':event=='collision','committed':False})
            finally:
                if worker.p.poll() is None:worker.finish(kill=True)
    for name in ['relative.marker','C:\\temp\\x.marker:stream.marker','\\\\server\\share\\x.marker','C:\\temp\\..\\x.marker','C:\\temp\\NUL.marker']:
        result=subprocess.run([str(binary),'fresh-sealed',name],capture_output=True,text=True,timeout=30)
        assert result.returncode==5 and 'MARKER_PATH_UNVERIFIED' in result.stderr
        cases.append({'id':'path-'+str(len(cases)),'diagnostic':'MARKER_PATH_UNVERIFIED','workerArtifacts':0,'committed':False})
    report={'caseCount':len(cases),'cases':cases,'platform':'Windows ordinary local NTFS','productionPublicationAllowed':False,'enabledProfiles':0}
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(root,flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',required=True);parser.add_argument('--parent',required=True)
    args=parser.parse_args();print(json.dumps(run(args.binary,args.parent),indent=2))

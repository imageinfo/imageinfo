"""Actual named-file actors against research guards; marker bytes only."""
import argparse,hashlib,json,mmap,os,platform,subprocess,sys,tempfile,time
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()

def run(binary,parent):
    binary=str(Path(binary).resolve());root=Path(tempfile.mkdtemp(prefix='imageinfo-guards-',dir=parent));cases=[]
    def directory(name):p=root/name;p.mkdir(mode=0o700);return p
    def record(name,**facts):cases.append({'id':name,**facts})
    def rejected(action):
        try:action();return False
        except OSError:return True
    if os.name=='nt':
        def held(name,stage,action):
            p=directory(name);source=p/'source.bin'
            if not stage:source.write_bytes(b'initial-source'*1024)
            if not stage and name.endswith('-alias'):os.link(source,p/'alias.bin')
            cmd='hold-stage' if stage else 'hold-source';path=p if stage else source
            process=subprocess.Popen([binary,cmd,str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            first=json.loads(process.stdout.readline());assert first['barrier']=='guard-held'
            actual=p/'guard-stage.bin' if stage else source
            try:values=action(p,actual)
            finally:out,err=process.communicate('release\n',timeout=20)
            assert process.returncode==0 and not err
            last=json.loads(out);assert last['contentUnchanged'] and last['objectUnchanged'] and not last['productionPublicationAllowed']
            record(name,**values,objectStable=True,contentStable=True,propertiesUnchanged=last['propertiesUnchanged'])
        for stage in [False,True]:
            prefix='stage' if stage else 'source'
            held(prefix+'-write',stage,lambda p,f:{'unrelatedWriteRefused':rejected(lambda:f.write_bytes(b'bad'))})
            assert cases[-1]['unrelatedWriteRefused']
            held(prefix+'-case-alias',stage,lambda p,f:{'caseAliasWriteRefused':rejected(lambda:f.with_name(f.name.upper()).write_bytes(b'bad'))})
            assert cases[-1]['caseAliasWriteRefused']
            held(prefix+'-truncate',stage,lambda p,f:{'truncateRefused':rejected(lambda:os.truncate(f,1))});assert cases[-1]['truncateRefused']
            held(prefix+'-delete',stage,lambda p,f:{'deleteRefused':rejected(f.unlink)});assert cases[-1]['deleteRefused']
            held(prefix+'-rename',stage,lambda p,f:{'renameRefused':rejected(lambda:f.rename(p/'renamed'))});assert cases[-1]['renameRefused']
            def alias(p,f):
                a=p/'alias.bin'
                if not a.exists() and rejected(lambda:os.link(f,a)):
                    return {'newHardlinkAliasRefused':True}
                return {'aliasWriteRefused':rejected(lambda:a.write_bytes(b'bad'))}
            held(prefix+'-alias',stage,alias);assert cases[-1].get('aliasWriteRefused') or cases[-1].get('newHardlinkAliasRefused')
            held(prefix+'-parent-rename',stage,lambda p,f:{'parentRenameRefused':rejected(lambda:p.rename(root/'moved'))});assert cases[-1]['parentRenameRefused']
            def metadata(p,f):
                allowed=not rejected(lambda:os.utime(f,(1000000000,1000000000)))
                return {'timestampMutationAllowed':allowed}
            held(prefix+'-metadata',stage,metadata)
            assert cases[-1]['timestampMutationAllowed'] and not cases[-1]['propertiesUnchanged']
        for kind in ['writable-handle','writable-map','readonly-map']:
            p=directory('preexisting-'+kind);source=p/'source.bin';source.write_bytes(b'map-source'*1000)
            handle=source.open('r+b' if kind!='readonly-map' else 'rb')
            mapping=mmap.mmap(handle.fileno(),0,access=mmap.ACCESS_WRITE if kind=='writable-map' else mmap.ACCESS_READ) if kind.endswith('map') else None
            if mapping:handle.close()
            process=subprocess.Popen([binary,'hold-source',str(source)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                if kind=='readonly-map':
                    assert json.loads(process.stdout.readline())['barrier']=='guard-held'
                    out,err=process.communicate('release\n',timeout=20);assert process.returncode==0
                    record('preexisting-'+kind,compatibleReadAccepted=True)
                else:
                    out,err=process.communicate(timeout=20);assert process.returncode==1 and not out
                    record('preexisting-'+kind,guardAcquisitionRefused=True)
            finally:
                if mapping:mapping.close()
                if not handle.closed:handle.close()
        p=directory('existing-stage');stage=p/'guard-stage.bin';stage.write_bytes(b'foreign-stage');before=sha(stage)
        refusal=subprocess.run([binary,'hold-stage',str(p)],capture_output=True,timeout=20)
        assert refusal.returncode==1 and sha(stage)==before;record('existing-stage',retained=True)
        for invalid in ['relative-source.bin',r'\\server\share\source.bin',r'\\?\C:\source.bin']:
            refusal=subprocess.run([binary,'hold-source',invalid],capture_output=True,timeout=20)
            assert refusal.returncode==1;record('path-profile-'+str(len(cases)),refused=True)
        target=directory('junction-target');(target/'source.bin').write_bytes(b'junction-source')
        junction=root/'junction-alias'
        made=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(target)],capture_output=True,timeout=20)
        assert made.returncode==0
        for operation,operand in [('hold-source',junction/'source.bin'),('hold-stage',junction)]:
            refused=subprocess.run([binary,operation,str(operand)],capture_output=True,timeout=20)
            assert refused.returncode==1 and not (target/'guard-stage.bin').exists()
            record('junction-'+operation,refusedBeforeStageEffects=True)
    elif platform.system()=='Linux':
        def anonymous(name,actor):
            p=directory(name);process=subprocess.Popen([binary,'anonymous-stage',str(p)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            first=json.loads(process.stdout.readline());assert first['links']==0
            try:actor(p,process)
            finally:
                if process.poll() is None:process.kill()
                out,err=process.communicate(timeout=20)
            return p,process,out,err
        def late_named(p,process):
            (p/'candidate.cr3').write_bytes(b'foreign-named-stage')
            process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=20)
        p,process,out,err=anonymous('late-named-stage',late_named);assert process.returncode==0
        assert (p/'output.bin').read_bytes()==bytes([0x29])*65536
        assert (p/'candidate.cr3').read_bytes()==b'foreign-named-stage'
        result=json.loads(out);assert result['boundObjectPublished'] and result['bytesUnchanged']
        record('late-named-stage',counterexamplePreventedForNamedPathActor=True,anonymousObjectUsed=True)
        def destination(p,process):
            (p/'output.bin').write_bytes(b'foreign-winner');process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=20)
        p,process,out,err=anonymous('racing-destination',destination);assert process.returncode==1
        assert (p/'output.bin').read_bytes()==b'foreign-winner';record('racing-destination',winnerRetained=True)
        def swap(p,process):
            p.rename(root/'bound-original');p.mkdir(mode=0o700)
            process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=20)
        p,process,out,err=anonymous('parent-swap',swap);assert process.returncode==0
        assert not (p/'output.bin').exists() and (root/'bound-original/output.bin').exists()
        record('parent-swap',boundObjectUsed=True,requestedPathBindingUnproved=True)
        def cancel(p,process):process.stdin.write('cancel\n');process.stdin.flush();process.wait(timeout=20)
        p,process,out,err=anonymous('cancel',cancel);assert process.returncode==1 and not list(p.iterdir())
        record('anonymous-cancel',noNamedArtifacts=True)
        def killed(p,process):process.kill();process.wait(timeout=20)
        p,process,out,err=anonymous('kill',killed);assert not list(p.iterdir())
        record('anonymous-kill',noNamedArtifacts=True)
        from lease_qualify import qualify_leases
        cases.extend(qualify_leases(root))
    else:
        p=directory('unsupported');result=subprocess.run([binary,'anonymous-stage',str(p)],capture_output=True,timeout=20)
        assert result.returncode==1 and not list(p.iterdir());record('unsupported-platform',refusedWithoutArtifacts=True)
    result={'schemaVersion':1,'platform':platform.platform(),'binarySha256':sha(Path(binary)),
        'root':str(root),'cases':cases,'productionProfilesEnabled':0,'metadataPropertyGuardVerified':False}
    (root/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--parent',required=True)
    a=p.parse_args();run(a.binary,a.parent)

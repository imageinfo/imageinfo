"""Supervise the actual research binary on owned disposable filesystem states.

No host/distro crash, automatic repair or cleanup. Images are never accepted by
this public synthetic suite. Private admitted-media runs use a separate driver.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):value.update(block)
    return value.hexdigest()


def snapshot(root):
    result={}
    for p in root.iterdir():
        info=p.lstat()
        result[p.name]={'mode':info.st_mode,'uid':info.st_uid,'size':info.st_size,
            'mtime':info.st_mtime_ns,'identity':[info.st_dev,info.st_ino],
            'hash':safe_hash(p) if p.is_file() and not p.is_symlink() else None}
    return result


def run(binary,parent,expect_private_refusal=False):
    binary=str(Path(binary).resolve())
    root=Path(tempfile.mkdtemp(prefix='imageinfo-recovery-proof-',dir=parent))
    cases=[]
    def report(name,**values):cases.append({'id':name,**values})
    def directory(name):
        p=root/name;p.mkdir(mode=0o700);return p
    def inspect(p,expected):
        before=snapshot(p)
        process=subprocess.run([binary,'inspect',str(p)],capture_output=True,timeout=20)
        assert process.returncode==0
        output=json.loads(process.stdout)
        assert output['classification']==expected,(p.name,output)
        assert output['authorizedActions']==[] and output['observationOnly'] and output['recoveryRequired']
        assert not output['profileVerified'] and not output['evidenceAuthenticated']
        assert snapshot(p)==before,'Inspection altered retained content/properties'
        return output
    def worker(p):
        process=subprocess.run([binary,'worker',str(p)],capture_output=True,timeout=20)
        assert process.returncode==0,(p.name,process.stderr)
        assert json.loads(process.stdout)['outcome']=='research-publication-observed'
        return process
    phases=['staged','prepared','intent','before-link','validated-before-link','linked','namespace-flushed','receipt-flushed']
    def at_barrier(p,phase,action):
        process=subprocess.Popen([binary,'worker',str(p),'--barriers'],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for reached in phases:
                assert process.stdout.readline().strip()==reached,'Worker missed explicit barrier'
                if reached==phase:
                    return action(process)
                process.stdin.write('continue\n');process.stdin.flush()
            raise AssertionError('Unknown barrier')
        finally:
            if process.poll() is None:process.kill()
            process.communicate(timeout=10)

    if expect_private_refusal:
        p=directory('unsupported-private-mode')
        process=subprocess.run([binary,'worker',str(p)],capture_output=True,timeout=20)
        assert process.returncode==1 and b'PRIVATE_DIRECTORY_REQUIRED' in process.stderr
        assert not list(p.iterdir())
        inspect(p,'invalid-or-uninspectable-evidence')
        report('private-mode-refusal',noArtifacts=True,observedMode=oct(p.stat().st_mode&0o777))
    elif platform.system()!='Linux':
        p=directory('unsupported')
        for operation in ['worker','inspect']:
            result=subprocess.run([binary,operation,str(p)],capture_output=True,timeout=20)
            assert result.returncode==1 and b'STORAGE_PROFILE_UNVERIFIED' in result.stderr
            assert not list(p.iterdir())
            report(operation+'-unsupported',refused=True,noArtifacts=True)
        if os.name=='nt':
            p=directory('windows-directory')
            process=subprocess.Popen([binary,'hold-directory',str(p)],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            assert process.stdout.readline().strip()=='directory-open'
            try:
                os.rename(p,root/'renamed')
                rename='allowed'
            except OSError as error:rename=f'refused:{getattr(error,"winerror",None)}'
            (p/'independent-child').write_bytes(b'external namespace creation')
            stdout,stderr=process.communicate('continue\n',timeout=10)
            assert process.returncode==0 and not stderr
            observed=json.loads(stdout)
            report('windows-directory-guard',rename=rename,childCreationAllowed=True,**observed)
    else:
        p=directory('success');worker(p)
        assert sha(p/'output.cr3')==sha(p/'candidate.cr3')==sha(p/'frozen-input.cr3')
        assert os.path.samefile(p/'output.cr3',p/'candidate.cr3')
        assert all(x.stat().st_mode&0o777==0o600 for x in p.iterdir())
        inspect(p,'candidate-object-observed')
        report('ordinary-publication',completeBytes=True,sameObject=True,privateModes=True)

        for phase in phases:
            p=directory('kill-'+phase)
            at_barrier(p,phase,lambda process:process.kill())
            expected='invalid-or-uninspectable-evidence' if phase=='staged' else (
                'candidate-object-observed' if phase in phases[5:] else 'expected-absence-observed')
            observed=inspect(p,expected)
            report('kill-'+phase,classification=observed['classification'],outputPresent=(p/'output.cr3').exists(),
                receiptPresent=(p/'receipt.record').exists(),OSCrash=False,powerLoss=False)

        p=directory('cancel-before-link')
        def cancel(process):
            process.stdin.write('cancel\n');process.stdin.flush();process.wait(timeout=10)
            assert process.returncode==1
        at_barrier(p,'before-link',cancel);assert not (p/'output.cr3').exists()
        inspect(p,'expected-absence-observed');report('cooperative-cancel',outputAbsent=True)

        p=directory('cancel-after-link')
        at_barrier(p,'linked',cancel)
        assert (p/'output.cr3').exists() and not (p/'receipt.record').exists()
        inspect(p,'candidate-object-observed');report('cancel-after-link',publicationObserved=True,recoveryRequired=True)

        import resource
        p=directory('write-resource-limit')
        def limit_child():resource.setrlimit(resource.RLIMIT_FSIZE,(32768,32768))
        limited=subprocess.run([binary,'worker',str(p)],capture_output=True,timeout=20,preexec_fn=limit_child)
        assert limited.returncode!=0 and not (p/'output.cr3').exists()
        assert (p/'frozen-input.cr3').stat().st_size==32768
        inspect(p,'invalid-or-uninspectable-evidence')
        report('write-resource-limit',actualChildWriteLimit=True,partialArtifactRetained=True,outputAbsent=True)

        p=directory('preexisting-destination');(p/'output.cr3').write_bytes(b'existing');(p/'output.cr3').chmod(0o600)
        before=snapshot(p);refused=subprocess.run([binary,'worker',str(p)],capture_output=True,timeout=20)
        assert refused.returncode==1 and snapshot(p)==before
        report('preexisting-destination',refusedBeforeStaging=True)

        p=directory('racing-destination')
        def collision(process):
            (p/'output.cr3').write_bytes(b'external-winner');(p/'output.cr3').chmod(0o600)
            process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=10)
            assert process.returncode==1
        at_barrier(p,'validated-before-link',collision)
        assert (p/'output.cr3').read_bytes()==b'external-winner'
        inspect(p,'foreign-or-uninspectable-target');report('racing-destination',winnerRetained=True)

        for kind in ['source','candidate']:
            p=directory('early-edit-'+kind)
            def edit(process):
                (p/('frozen-input.cr3' if kind=='source' else 'candidate.cr3')).write_bytes(b'external-edit')
                process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=10)
                assert process.returncode==1
            at_barrier(p,'before-link',edit);assert not (p/'output.cr3').exists()
            inspect(p,'invalid-or-uninspectable-evidence');report('early-edit-'+kind,refusedBeforePublish=True)

        p=directory('late-stage-edit')
        def late_edit(process):
            (p/'candidate.cr3').write_bytes(b'late-unrelated-change')
            process.stdin.write('continue\n');process.stdin.flush()
            assert process.stdout.readline().strip()=='linked'
            process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=10)
            assert process.returncode==1
        at_barrier(p,'validated-before-link',late_edit)
        assert (p/'output.cr3').read_bytes()==b'late-unrelated-change'
        inspect(p,'invalid-or-uninspectable-evidence')
        report('late-stage-edit',unwantedBytesPublished=True,qualification='unverified: stage exclusion missing')

        p=directory('parent-swapped-before-link');moved=root/'original-parent'
        def swap(process):
            p.rename(moved);p.mkdir(mode=0o700)
            process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=10)
            assert process.returncode==1
        at_barrier(p,'before-link',swap)
        assert not (p/'output.cr3').exists() and not (moved/'output.cr3').exists()
        inspect(moved,'expected-absence-observed');report('parent-swapped-before-link',noForeignPublication=True)

        p=directory('parent-swapped-after-validation');moved=root/'renamed-after-check'
        def swap_late(process):
            p.rename(moved);p.mkdir(mode=0o700)
            process.stdin.write('continue\n');process.stdin.flush()
            assert process.stdout.readline().strip()=='linked'
            process.stdin.write('continue\n');process.stdin.flush();process.wait(timeout=10)
            assert process.returncode==1
        at_barrier(p,'validated-before-link',swap_late)
        assert not (p/'output.cr3').exists() and (moved/'output.cr3').exists()
        inspect(moved,'candidate-object-observed');report('parent-swapped-after-validation',boundObjectUsed=True,pathBindingUncertain=True)

        mutations={
            'missing-source':lambda p:(p/'frozen-input.cr3').unlink(),
            'missing-stage':lambda p:(p/'candidate.cr3').unlink(),
            'changed-source':lambda p:(p/'frozen-input.cr3').write_bytes(b'corrupt'),
            'changed-stage':lambda p:(p/'candidate.cr3').write_bytes(b'corrupt'),
            'corrupt-record':lambda p:(p/'intent.record').write_bytes(b'{}'),
            'oversized-record':lambda p:(p/'intent.record').write_bytes(b' '*65537),
            'corrupt-receipt':lambda p:(p/'receipt.record').write_bytes(b'{}'),
            'stage-permission-change':lambda p:(p/'candidate.cr3').chmod(0o644),
            'root-permission-change':lambda p:p.chmod(0o755),
            'record-symlink':lambda p:replace_with_symlink(p/'intent.record',root/'foreign-record'),
            'stage-symlink':lambda p:replace_with_symlink(p/'candidate.cr3',root/'foreign-data'),
            'stage-fifo':lambda p:replace_with_fifo(p/'candidate.cr3'),
            'record-fifo':lambda p:replace_with_fifo(p/'intent.record'),
        }
        (root/'foreign-record').write_bytes(b'never interpreted');(root/'foreign-data').write_bytes(b'never read')
        for name,mutate in mutations.items():
            p=directory(name);worker(p);mutate(p);inspect(p,'invalid-or-uninspectable-evidence')
            report(name,rejectedWithoutRepair=True)
        for kind in ['different-bytes','same-bytes-new-object','symlink']:
            p=directory('foreign-target-'+kind);worker(p)
            old=p/'output.cr3';old.unlink()
            if kind=='symlink':old.symlink_to(root/'foreign-data')
            else:
                old.write_bytes((p/'candidate.cr3').read_bytes() if kind=='same-bytes-new-object' else b'foreign')
                old.chmod(0o600)
            inspect(p,'foreign-or-uninspectable-target');report('foreign-target-'+kind,notAttributedToCandidate=True)

        p=directory('target-fifo');worker(p);replace_with_fifo(p/'output.cr3')
        inspect(p,'foreign-or-uninspectable-target');report('target-fifo',refusedWithoutBlocking=True)

        p=directory('inaccessible-record');worker(p);before_hash=sha(p/'intent.record');(p/'intent.record').chmod(0o000)
        inspect(p,'invalid-or-uninspectable-evidence');assert (p/'intent.record').stat().st_mode&0o777==0
        (p/'intent.record').chmod(0o600);assert sha(p/'intent.record')==before_hash
        report('inaccessible-record',noPermissionShortcut=True,contentRetained=True)

        for mutation in ['path-traversal','fabricated-commit','extra-member','root-identity','forged-receipt']:
            p=directory('forged-'+mutation);worker(p)
            name='receipt.record' if mutation=='forged-receipt' else 'intent.record'
            envelope=json.loads((p/name).read_text());body=json.loads(envelope['body'])
            if mutation=='path-traversal':body['destination']='../foreign-data'
            elif mutation=='fabricated-commit':body['phase']='committed'
            elif mutation=='extra-member':body['authorized']=True
            elif mutation=='root-identity':body['root_identity']='1:2'
            else:body['observation_only']=False
            envelope['body']=json.dumps(body,separators=(',',':'));envelope['sha256']=hashlib.sha256(envelope['body'].encode()).hexdigest()
            (p/name).write_text(json.dumps(envelope));inspect(p,'invalid-or-uninspectable-evidence')
            report('forged-'+mutation,recomputedHashGrantedNothing=True)

        p=directory('private-root-symlink');worker(p)
        alias=root/'root-alias';alias.symlink_to(p,target_is_directory=True)
        inspect(alias,'invalid-or-uninspectable-evidence');report('private-root-symlink',refused=True)

    result={'schemaVersion':1,'platform':platform.platform(),'python':sys.version,'binary':binary,
        'binarySha256':sha(Path(binary)),'root':str(root),'cases':cases,'profileVerified':False,
        'OSCrashRuns':0,'powerLossRuns':0,'automaticRepair':False}
    (root/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def replace_with_symlink(path,target):
    path.unlink();path.symlink_to(target)


def replace_with_fifo(path):
    path.unlink();os.mkfifo(path,0o600)


def safe_hash(path):
    try:return sha(path)
    except PermissionError:return 'unreadable'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True);parser.add_argument('--parent',required=True)
    parser.add_argument('--expect-private-refusal',action='store_true')
    args=parser.parse_args();run(args.binary,args.parent,args.expect_private_refusal)

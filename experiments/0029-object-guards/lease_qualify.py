"""Linux standard-library lease qualification; not a production Rust guard.

Never changes lease-break-time, waits for forced expiry, or grants publication.
All actors touch only caller-owned marker fixtures. Leases' break/expiry behavior
is a remaining admission constraint, not an advisory-lock substitute.
"""
import errno,fcntl,json,mmap,os,signal,subprocess,sys,time
from pathlib import Path

def qualify_leases(root):
    cases=[];events=[]
    old_handler=signal.signal(signal.SIGIO,lambda sig,frame:events.append(time.monotonic()))
    timeout=int(Path('/proc/sys/fs/lease-break-time').read_text())
    if timeout<5:raise RuntimeError('Lease-break configuration too short for bounded qualification')
    def fixture(name):
        p=root/name;p.write_bytes(b'lease-original'*1024);p.chmod(0o600);return p
    try:
        for kind in ['writable-handle','writable-mapping']:
            p=fixture('lease-preexisting-'+kind);writer=p.open('r+b')
            mapped=mmap.mmap(writer.fileno(),0,access=mmap.ACCESS_WRITE) if kind.endswith('mapping') else None
            if mapped:writer.close()
            reader=p.open('rb');refused=False
            try:
                try:fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_RDLCK)
                except OSError as error:
                    assert error.errno in [errno.EAGAIN,errno.EACCES];refused=True
                assert refused,'Preexisting writer/map did not prevent lease; guard cannot be admitted'
            finally:
                if not refused:fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_UNLCK)
                reader.close()
                if mapped:mapped.close()
                if not writer.closed:writer.close()
            cases.append({'id':'lease-preexisting-'+kind,'guardAcquisitionRefused':True})
        for via_alias in [False,True]:
            p=fixture('lease-new-writer'+('-alias' if via_alias else ''))
            a=root/'lease-hardlink-alias' if via_alias else p
            if via_alias:os.link(p,a)
            reader=p.open('rb');fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_RDLCK);events.clear()
            actor=subprocess.Popen([sys.executable,'-c',"from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'external-after-release')",str(a)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+2
                while not events and time.monotonic()<deadline:time.sleep(0.01)
                assert events and actor.poll() is None
                assert p.read_bytes()==b'lease-original'*1024
                pending=fcntl.fcntl(reader,fcntl.F_GETLEASE);assert pending==fcntl.F_UNLCK
                cases.append({'id':'lease-new-writer'+('-alias' if via_alias else ''),
                    'writerBlockedBeforeRelease':True,'breakSignalObserved':True,'pendingBreakDetected':True,
                    'publicationMustRefuse':True,'forcedExpiryTested':False})
            finally:
                fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_UNLCK);reader.close()
                actor.communicate(timeout=10)
            assert actor.returncode==0 and p.read_bytes()==b'external-after-release'
        p=fixture('lease-namespace');reader=p.open('rb');fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_RDLCK);events.clear()
        renamed=root/'lease-renamed'
        try:
            actor=subprocess.run([sys.executable,'-c','import os,sys;os.rename(sys.argv[1],sys.argv[2])',str(p),str(renamed)],capture_output=True,timeout=2)
            assert actor.returncode==0
            assert reader.read()==b'lease-original'*1024
            cases.append({'id':'lease-namespace','sourceRenameAllowed':True,'sourceObjectCoherent':True,'pathGuardUnverified':True})
        finally:fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_UNLCK);reader.close()
        p=fixture('lease-properties');reader=p.open('rb');fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_RDLCK)
        try:
            os.utime(p,(1000000000,1000000000));assert reader.read()==b'lease-original'*1024
            cases.append({'id':'lease-properties','timestampMutationAllowed':True,'propertyGuardUnverified':True})
        finally:fcntl.fcntl(reader,fcntl.F_SETLEASE,fcntl.F_UNLCK);reader.close()
        cases.append({'id':'lease-configuration','observedBreakSeconds':timeout,'changedConfiguration':False,
            'boundedProbeSeconds':2,'unboundedPublicationGuardQualified':False})
    finally:signal.signal(signal.SIGIO,old_handler)
    return cases

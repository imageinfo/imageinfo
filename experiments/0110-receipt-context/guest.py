"""Exactly two checked-flush VM-off cells in one fresh disposable overlay.

Reuse only the scoped #0106 transport, read-only observer and console helpers.
Fresh hash-bound challenge readiness precedes every queued measurement job.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent/'0022-ordinary-output'
sys.path.insert(0,str(TOOLS))
from guest_qualify import hello, queue, state, verify_guest_token, wait_event, rebooted
import windows_guest as transport
spec = importlib.util.spec_from_file_location('receipt106_transport',HERE.parent/'0106-receipt-properties/qualify.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
MODE = 'ordinary-receipt-checked-flush'
INSPECTOR = old.ACTOR
OBSERVER = '2a15627fd4a04c9efbb5eee93e3e8ee76fb0401cda362824a1a0cb34293a6bb7'
MATRIX = [('pre-context','receipt-written'), ('first-checked-context','receipt-file-flushed')]
write, digest, prepare, vm_off = old.write, old.digest, old.prepare, old.vm_off

def agent_source(observer_hash, inspector_hash):
    source = old.agent_source(observer_hash)
    source = source.replace("'ordinary-receipt-properties'))", "'ordinary-receipt-properties','"+MODE+"'))")
    source = source.replace("if($mode -eq 'ordinary-receipt-properties'){'C:\\ImageInfoGuest\\observer.exe'}else{'C:\\ImageInfoGuest\\probe.exe'}",
        "if($mode -eq 'ordinary-receipt-properties'){'C:\\ImageInfoGuest\\observer.exe'}elseif($mode -eq 'ordinary-receipt-inspect'){'C:\\ImageInfoGuest\\inspector.exe'}else{'C:\\ImageInfoGuest\\probe.exe'}")
    source = source.replace("$work.mode -eq 'ordinary-receipt'", "$work.mode -eq '"+MODE+"'")
    source = source.replace("$base='http://10.0.2.2:18722'", "$instance=[guid]::NewGuid().ToString();$base='http://10.0.2.2:18722'")
    marker = "        while($true) {\n            $work="
    download = r'''
        Invoke-WebRequest ($base+'/inspector.exe') -OutFile C:\ImageInfoGuest\inspector.new.exe -UseBasicParsing
        if((Get-FileHash C:\ImageInfoGuest\inspector.new.exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'INSPECTOR_HASH') {throw 'Inspector payload mismatch'}
        Move-Item C:\ImageInfoGuest\inspector.new.exe C:\ImageInfoGuest\inspector.exe -Force
        $ready=@{instance=$instance;actorSha256=(Get-FileHash C:\ImageInfoGuest\probe.exe -Algorithm SHA256).Hash.ToLowerInvariant();observerSha256=(Get-FileHash C:\ImageInfoGuest\observer.exe -Algorithm SHA256).Hash.ToLowerInvariant();inspectorSha256=(Get-FileHash C:\ImageInfoGuest\inspector.exe -Algorithm SHA256).Hash.ToLowerInvariant();scriptSha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()}
        Send '/event' @{id='ready';event=$ready}
'''.replace('INSPECTOR_HASH',inspector_hash)
    assert source.count(marker) == 1
    source = source.replace(marker,download+'\n'+marker)
    marker = "            if(-not $work.id) {Start-Sleep -Milliseconds 500;continue}"
    source = source.replace(marker,marker+"\n            if($work.action -eq 'ready') {Send '/result' @{id=$work.id;challenge=$work.challenge;ready=$ready};continue}")
    assert source.count("$work.mode -eq '"+MODE+"'") == 2
    return source

def serve(root, actor, observer, inspector):
    import http.server
    original_factory = http.server.ThreadingHTTPServer
    def factory(address, handler):
        original = handler.do_GET
        def get(self):
            if self.path in ('/observer.exe','/inspector.exe'):
                return self.send((observer if self.path=='/observer.exe' else inspector).read_bytes(),'application/octet-stream')
            if self.path == '/bootstrap':
                # One premeasurement transition from the retained legacy agent.
                # Subsequent boots use the now-installed exact script and mutex.
                script = r'''$ErrorActionPreference='Stop'
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object {$_.ProcessId -ne $PID -and $_.CommandLine -match '(?i)-file\s+c:\\imageinfoguest\\agent\.ps1\s*$'} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force}
Start-Sleep -Seconds 1
Invoke-WebRequest 'http://10.0.2.2:18722/agent.ps1' -OutFile 'C:\ImageInfoGuest\agent.ps1' -UseBasicParsing
& powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File 'C:\ImageInfoGuest\agent.ps1'
'''
                return self.send(script.encode(),'text/plain; charset=utf-8')
            return original(self)
        handler.do_GET = get
        return original_factory(address,handler)
    http.server.ThreadingHTTPServer = factory
    transport.AGENT = agent_source(digest(observer),digest(inspector))
    transport.serve(root,actor)

def readiness(binding, after=0):
    event = wait_event(lambda e:e['path']=='/event' and e['at']>after and e['value'].get('id')=='ready'
        and e['value']['event'].get('scriptSha256')==binding['guestAgentSha256'])
    ready = event['value']['event']
    for key in ('actorSha256','observerSha256','inspectorSha256'):
        assert ready[key] == binding[key]
    challenge = os.urandom(16).hex()
    identifier = 'ready-'+challenge
    queue({'id':identifier,'action':'ready','challenge':challenge})
    response = wait_event(lambda e:e['path']=='/result' and e['value'].get('id')==identifier)
    assert response['value']['challenge']==challenge and response['value']['ready']==ready
    current = hello()
    verify_guest_token(current['value'])
    assert current['value']['scriptSha256']==binding['guestAgentSha256']
    return {'readyEvent':event,'challengeResult':response,'hello':current}

def invoke(case,suffix,mode,**extra):
    request = {'id':case+'-'+suffix,'action':'run','case':case,'mode':mode,**extra}
    queue(request)
    return wait_event(lambda e:e['path']=='/result' and e['value'].get('id')==request['id'])['value']

def relaunch(root,folder,binding):
    result = subprocess.run(['/mnt/c/Windows/System32/wsl.exe','-u','root','-e','python3',str(TOOLS/'windows_guest.py'),'launch','--root',str(root)],capture_output=True,timeout=40)
    write(folder/'relaunch.private.json',{'exitCode':result.returncode,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')})
    assert result.returncode==0
    # Allow ordinary sign-in to launch the exact installed script. No bootstrap
    # replacement occurs after a measurement or while work is queued.
    time.sleep(30)
    spec=importlib.util.spec_from_file_location('receipt110_console',HERE/'console.py')
    console=importlib.util.module_from_spec(spec);spec.loader.exec_module(console)
    base=Path(json.loads((root/'overlay-binding.private.json').read_text())['root'])
    console.run(root,base,True)

def binding(actor,observer,inspector,frozen,baseline):
    native=json.loads((baseline/'source-binding.private.json').read_text())
    report=json.loads((baseline/'report.private.json').read_text())
    assert report['caseCount']==11 and digest(actor)==native['workerSha256'] and digest(inspector)==INSPECTOR
    assert digest(observer)==OBSERVER
    for relative,expected in native['sources'].items():
        assert digest(frozen/relative)==expected
    paths=list(HERE.glob('*.py'))+[HERE.parent/'0106-receipt-properties'/p for p in ('qualify.py','console.py','audit_final.py')]+[TOOLS/'windows_guest.py',TOOLS/'guest_qualify.py']
    return {'actorSha256':digest(actor),'observerSha256':digest(observer),'inspectorSha256':digest(inspector),
        'guestAgentSha256':hashlib.sha256(agent_source(digest(observer),digest(inspector)).encode()).hexdigest(),
        'candidateSources':native['sources'],'nativeBaselineSha256':digest(baseline/'report.private.json'),
        'nativeBindingSha256':digest(baseline/'source-binding.private.json'),
        'controllerSources':{p.relative_to(HERE.parent).as_posix():digest(p) for p in paths}}

def run(root,actor,observer,inspector,frozen,baseline,output):
    bound=binding(actor,observer,inspector,frozen,baseline)
    output.mkdir(exist_ok=False)
    write(output/'source-binding.private.json',bound)
    for relative,expected in bound['controllerSources'].items():
        target=output/'controller-sources.private'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((HERE.parent/relative).read_bytes())
        assert digest(target)==expected
    (output/'served-agent.private.ps1').write_bytes(agent_source(digest(observer),digest(inspector)).encode())
    host=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    write(output/'host-before.private.json',{'boot':host})
    write(output/'overlay-binding.private.json',json.loads((root/'overlay-binding.private.json').read_text()))
    write(output/'initial-launch.private.json',json.loads((root/'launch.private.json').read_text()))
    rows=[]
    try:
        ready=readiness(bound)
        for index,(name,phase) in enumerate(MATRIX):
            folder=output/name;folder.mkdir()
            case='c110-'+str(index)+'-'+str(int(time.time()))
            before=hello();verify_guest_token(before['value'])
            prepared=invoke(case,'prepare','ordinary-prepare')
            request={'id':case+'-live','action':'run','case':case,'mode':MODE,'stopAt':phase}
            queue(request)
            checkpoint=wait_event(lambda e:e['path']=='/event' and e['value'].get('id')==request['id']
                and e['value']['event'].get('supervisorControl',{}).get('control')=='held')
            actual=old.events(request['id'])
            context=next((e['value']['event']['receiptContext'] for e in reversed(actual) if 'receiptContext' in e['value'].get('event',{})),None)
            pre=next(e['value']['event']['preProperties'] for e in actual if 'preProperties' in e['value'].get('event',{}))
            assert (context is None)==(index==0)
            write(folder/'before.private.json',{'case':case,'hello':before,'readiness':ready,'prepare':prepared,'request':request,'checkpoint':checkpoint,'receiptContext':context,'preProperties':pre})
            fault=time.time();vm_off(root,folder)
            relaunch(root,folder,bound)
            rebooted(before,fault)
            ready=readiness(bound,fault)
            after=ready['hello']
            post=invoke(case,'native-post','ordinary-receipt-properties')
            inventory_before=invoke(case,'rich-before','ordinary-inventory')
            inspection=None
            if context:
                inspection=invoke(case,'inspect','ordinary-receipt-inspect',receiptContext=context)
            inventory_after=invoke(case,'rich-after','ordinary-inventory')
            final=invoke(case,'native-final','ordinary-receipt-properties')
            write(folder/'after.private.json',{'hello':after,'readiness':ready,'postbootProperties':post,'inventoryBefore':inventory_before,
                'inspectRequest':{'receiptContext':context} if context else None,'inspect':inspection,'inventoryAfter':inventory_after,'finalProperties':final})
            write(folder/'controller-events.private.json',[e for e in state() if e['value'].get('id','').startswith(case)])
            write(folder/'transport-history.private.json',state())
            rows.append({'id':name,'barrier':phase,'faultKind':'vm-off','retained':True})
            write(output/'progress.private.json',{'cases':rows})
            print(json.dumps({'cell':name,'retained':True}),flush=True)
        assert binding(actor,observer,inspector,frozen,baseline)==bound
        write(output/'source-binding-after.private.json',bound)
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==host
        write(output/'host-after.private.json',{'boot':host})
        basebound=json.loads((root/'overlay-binding.private.json').read_text());base=Path(basebound['root'])
        baseafter={'root':str(base),'diskSha256':digest(base/'windows.qcow2'),'varsSha256':digest(base/'vars.fd'),'manifestSha256':digest(base/'guest.private.json')}
        write(output/'base-after.private.json',baseafter);assert baseafter==basebound
        write(output/'summary.private.json',{'caseCount':2,'vmOffs':2,'cases':rows,'hostCachesAlive':True,'enabledProfiles':0,**dict.fromkeys(old.FLAGS,False)})
        write(output/'transport-history.private.json',state())
    except BaseException as error:
        write(output/'incomplete.private.json',{'cases':rows,'diagnostic':str(error)});raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','serve','run'])
    for name in ('root','base','actor','observer','inspector','frozen','baseline','output'):
        parser.add_argument('--'+name,type=Path,required=name=='root')
    args=parser.parse_args()
    if args.mode=='prepare':prepare(args.base,args.root)
    elif args.mode=='serve':serve(args.root,args.actor,args.observer,args.inspector)
    else:run(args.root,args.actor,args.observer,args.inspector,args.frozen,args.baseline,args.output)

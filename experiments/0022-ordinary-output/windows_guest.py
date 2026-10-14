"""Private disposable evaluation guest tooling; no host disks or shared folders.

Run prepare as the ordinary WSL user; launch via WSL root only to open KVM.
QEMU drops to the recorded ordinary uid/gid before running guest instructions.
All generated accounts, passwords, disks and capture files stay in the private root.
"""
import argparse,datetime,hashlib,http.server,json,os,pathlib,queue,secrets,shutil,socket,subprocess,threading,time

AGENT=r'''
$ErrorActionPreference='Stop'
$base='http://10.0.2.2:18722'
function Send($path,$value) {
    $json=$value | ConvertTo-Json -Depth 16 -Compress
    Invoke-RestMethod -Uri ($base+$path) -Method Post -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($json)) | Out-Null
}
New-Item -ItemType Directory C:\ImageInfoGuest\cases -Force | Out-Null
while($true) {
    try {
        $os=Get-CimInstance Win32_OperatingSystem
        Send '/hello' @{build=$os.BuildNumber;version=$os.Version;boot=$os.LastBootUpTime.ToUniversalTime().ToString('o');user=(whoami);groups=(whoami /groups /fo csv);license=(Get-CimInstance SoftwareLicensingProduct | Where-Object {$_.Name -like '*Enterprise*' -and $_.PartialProductKey} | Select-Object Name,LicenseStatus,GracePeriodRemaining)}
        $meta=Invoke-RestMethod ($base+'/meta')
        Invoke-WebRequest ($base+'/probe.exe') -OutFile C:\ImageInfoGuest\probe.new.exe -UseBasicParsing
        if((Get-FileHash C:\ImageInfoGuest\probe.new.exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $meta.sha256) {throw 'Payload mismatch'}
        Move-Item C:\ImageInfoGuest\probe.new.exe C:\ImageInfoGuest\probe.exe -Force
        while($true) {
            $work=Invoke-RestMethod ($base+'/work')
            if(-not $work.id) {Start-Sleep -Milliseconds 500;continue}
            if($work.action -eq 'events') {
                $events=@(Get-WinEvent -FilterHashtable @{LogName='System';Id=41,1001,6008} -MaxEvents 12 -ErrorAction SilentlyContinue | Select-Object Id,ProviderName,TimeCreated,Message)
                Send '/result' @{id=$work.id;events=$events};continue
            }
            if($work.action -ne 'run' -or $work.case -notmatch '^[a-z0-9-]{1,60}$' -or $work.mode -notin @('ordinary-prepare','ordinary','ordinary-inspect','ordinary-admit','ordinary-finalize','ordinary-prune')) {throw 'Invalid guest job'}
            $root='C:\ImageInfoGuest\cases\'+$work.case+'.marker'
            $p=New-Object Diagnostics.Process
            $p.StartInfo=New-Object Diagnostics.ProcessStartInfo
            $p.StartInfo.FileName='C:\ImageInfoGuest\probe.exe'
            $p.StartInfo.Arguments='"'+$root+'" '+$work.mode
            $p.StartInfo.UseShellExecute=$false;$p.StartInfo.CreateNoWindow=$true
            $p.StartInfo.RedirectStandardInput=$true;$p.StartInfo.RedirectStandardOutput=$true;$p.StartInfo.RedirectStandardError=$true
            $null=$p.Start();$lines=@()
            while($null -ne ($line=$p.StandardOutput.ReadLine())) {
                $lines+=,$line;$event=$line | ConvertFrom-Json
                Send '/event' @{id=$work.id;event=$event}
                if($event.barrier) {
                    if($event.barrier -eq $work.stopAt) {
                        if($work.control) {$p.StandardInput.WriteLine($work.control);$p.StandardInput.Flush()}
                    } else {$p.StandardInput.WriteLine('continue');$p.StandardInput.Flush()}
                }
            }
            $p.WaitForExit();$stderr=$p.StandardError.ReadToEnd()
            $files=@()
            if(Test-Path -LiteralPath $root) {
                $files=@(Get-ChildItem -LiteralPath $root -File | ForEach-Object {try {@{name=$_.Name;size=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}}catch {@{name=$_.Name;inaccessible=$true}}})
            }
            Send '/result' @{id=$work.id;exitCode=$p.ExitCode;stdout=$lines;stderr=$stderr;files=$files}
        }
    } catch {try {Send '/agent-error' @{error=$_.Exception.Message}}catch {};Start-Sleep -Seconds 3}
}
'''

def prepare(root,iso,tools):
    root=pathlib.Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    iso=pathlib.Path(iso).resolve();tools=pathlib.Path(tools).resolve()
    if not iso.is_file():raise ValueError('An ordinary evaluation ISO file is required; no physical device paths')
    password=secrets.token_urlsafe(24)
    config=root/'config';config.mkdir()
    (config/'agent.ps1').write_text(AGENT,encoding='utf-8')
    setup=r'''@echo off
setlocal
for %%d in (D E F G H I J) do if exist %%d:\agent.ps1 set CFG=%%d:
mkdir C:\ImageInfoGuest
copy /y %CFG%\agent.ps1 C:\ImageInfoGuest\agent.ps1
icacls C:\ImageInfoGuest /grant "*S-1-5-32-545:(OI)(CI)M"
reg add HKLM\SYSTEM\CurrentControlSet\Control\CrashControl /v NMICrashDump /t REG_DWORD /d 1 /f
reg add HKLM\SYSTEM\CurrentControlSet\Control\CrashControl /v AutoReboot /t REG_DWORD /d 0 /f
reg add HKLM\SYSTEM\CurrentControlSet\Control\CrashControl /v CrashDumpEnabled /t REG_DWORD /d 3 /f
powercfg /hibernate off
powercfg /change standby-timeout-ac 0
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run /v ImageInfoGuestAgent /t REG_SZ /d "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\ImageInfoGuest\agent.ps1" /f
exit /b 0
'''.replace('PASSWORD',password)
    # SetupComplete runs only inside the newly installed guest. It is copied by
    # the documented OEM setup folder from the configuration medium in WinPE.
    (config/'SetupComplete.cmd').write_text(setup,encoding='utf-8')
    xml=rf'''<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
<settings pass="windowsPE">
<component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><SetupUILanguage><UILanguage>en-US</UILanguage></SetupUILanguage><InputLocale>0409:00000409</InputLocale><SystemLocale>en-US</SystemLocale><UILanguage>en-US</UILanguage><UserLocale>en-US</UserLocale></component>
<component name="Microsoft-Windows-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
<DiskConfiguration><Disk wcm:action="add"><DiskID>0</DiskID><WillWipeDisk>true</WillWipeDisk><CreatePartitions><CreatePartition wcm:action="add"><Order>1</Order><Type>EFI</Type><Size>260</Size></CreatePartition><CreatePartition wcm:action="add"><Order>2</Order><Type>MSR</Type><Size>16</Size></CreatePartition><CreatePartition wcm:action="add"><Order>3</Order><Type>Primary</Type><Extend>true</Extend></CreatePartition></CreatePartitions><ModifyPartitions><ModifyPartition wcm:action="add"><Order>1</Order><PartitionID>1</PartitionID><Format>FAT32</Format><Label>System</Label></ModifyPartition><ModifyPartition wcm:action="add"><Order>2</Order><PartitionID>3</PartitionID><Format>NTFS</Format><Label>Windows</Label><Letter>C</Letter></ModifyPartition></ModifyPartitions></Disk></DiskConfiguration>
<ImageInstall><OSImage><InstallFrom><MetaData wcm:action="add"><Key>/IMAGE/INDEX</Key><Value>1</Value></MetaData></InstallFrom><InstallTo><DiskID>0</DiskID><PartitionID>3</PartitionID></InstallTo><WillShowUI>OnError</WillShowUI></OSImage></ImageInstall>
<UserData><AcceptEula>true</AcceptEula><FullName>ImageInfo evaluation</FullName><Organization>ImageInfo test guest</Organization></UserData>

</component></settings>
<settings pass="specialize"><component name="Microsoft-Windows-Deployment" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><RunSynchronous><RunSynchronousCommand wcm:action="add"><Order>1</Order><Path>cmd /c for %d in (D E F G H I J) do @if exist %d:\SetupComplete.cmd (mkdir C:\Windows\Setup\Scripts &amp; copy /y %d:\SetupComplete.cmd C:\Windows\Setup\Scripts\SetupComplete.cmd)</Path></RunSynchronousCommand></RunSynchronous></component><component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><ComputerName>IMAGEINFO-GUEST</ComputerName><TimeZone>UTC</TimeZone></component></settings>
<settings pass="oobeSystem"><component name="Microsoft-Windows-International-Core" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><InputLocale>0409:00000409</InputLocale><SystemLocale>en-US</SystemLocale><UILanguage>en-US</UILanguage><UserLocale>en-US</UserLocale></component>
<component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><OOBE><HideEULAPage>true</HideEULAPage><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE><HideOnlineAccountScreens>true</HideOnlineAccountScreens><ProtectYourPC>3</ProtectYourPC></OOBE><UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Name>ImageInfoTest</Name><DisplayName>ImageInfo test worker</DisplayName><Group>Users</Group><Password><Value>{password}</Value><PlainText>true</PlainText></Password></LocalAccount></LocalAccounts></UserAccounts><AutoLogon><Enabled>true</Enabled><LogonCount>100</LogonCount><Username>ImageInfoTest</Username><Password><Value>{password}</Value><PlainText>true</PlainText></Password></AutoLogon></component></settings></unattend>'''
    (config/'Autounattend.xml').write_text(xml,encoding='utf-8')
    subprocess.run([str(tools/'usr/bin/genisoimage'),'-quiet','-J','-r','-V','IMAGEINFOCFG','-o',str(root/'config.iso'),str(config)],check=True)
    subprocess.run(['qemu-img','create','-f','qcow2',str(root/'windows.qcow2'),'96G'],check=True)
    shutil.copyfile(tools/'usr/share/OVMF/OVMF_VARS_4M.ms.fd',root/'vars.fd')
    (root/'tpm').mkdir()
    manifest={'root':str(root),'iso':str(iso),'tools':str(tools),'uid':os.getuid(),'gid':os.getgid(),'createdAtUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'evaluationOnly':True,'hostDisksExposed':False,'hostFoldersShared':False}
    (root/'guest.private.json').write_text(json.dumps(manifest,indent=2))
    os.chmod(root,0o700)
    print(json.dumps({'guestRoot':str(root),'ramMiB':8192,'cpus':4,'diskVirtualGiB':96,'hostDisksExposed':False}))

def launch(root):
    import pwd
    root=pathlib.Path(root).resolve();v=json.loads((root/'guest.private.json').read_text());tools=pathlib.Path(v['tools'])
    if v['uid']==0 or root.stat().st_uid!=v['uid'] or v['root']!=str(root):raise ValueError('Private guest root must belong to its ordinary operator')
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(tools/'usr/lib/x86_64-linux-gnu')+':'+str(tools/'usr/lib/x86_64-linux-gnu/swtpm')
    tpm=['/usr/sbin/runuser','-u',pwd.getpwuid(v['uid']).pw_name,'--',str(tools/'usr/bin/swtpm'),'socket','--tpm2','--tpmstate','dir='+str(root/'tpm'),'--ctrl','type=unixio,path='+str(root/'tpm.sock'),'--flags','not-need-init,startup-clear','--pid','file='+str(root/'tpm.pid'),'--daemon']
    if not (root/'tpm.pid').exists() or not pathlib.Path('/proc/'+(root/'tpm.pid').read_text().strip()).exists():
        subprocess.run(tpm,env=env,check=True)
    args=['qemu-system-x86_64','-machine','q35,accel=kvm,smm=on','-cpu','host','-smp','4','-m','8192','-global','driver=cfi.pflash01,property=secure,value=on','-drive',f'if=pflash,format=raw,unit=0,readonly=on,file={tools}/usr/share/OVMF/OVMF_CODE_4M.ms.fd','-drive',f'if=pflash,format=raw,unit=1,file={root}/vars.fd','-drive',f'file={root}/windows.qcow2,if=ide,format=qcow2,cache=writeback','-drive',f'file={v["iso"]},media=cdrom,readonly=on','-drive',f'file={root}/config.iso,media=cdrom,readonly=on','-chardev',f'socket,id=chrtpm,path={root}/tpm.sock','-tpmdev','emulator,id=tpm0,chardev=chrtpm','-device','tpm-crb,tpmdev=tpm0','-device','qemu-xhci','-device','usb-tablet','-netdev','user,id=net0','-device','e1000e,netdev=net0','-boot','once=d,order=c,menu=off','-display','none','-vga','std','-qmp',f'unix:{root}/qmp,server=on,wait=off','-daemonize','-pidfile',str(root/'qemu.pid'),'-run-with',f'user={v["uid"]}:{v["gid"]}']
    p=subprocess.run(args,env=env,capture_output=True,text=True,timeout=30)
    (root/'launch.private.json').write_text(json.dumps({'argv':args,'exitCode':p.returncode,'stderr':p.stderr},indent=2))
    if p.returncode:raise RuntimeError(p.stderr)
    os.chown(root/'qmp',v['uid'],v['gid'])
    os.chown(root/'qemu.pid',v['uid'],v['gid'])
    print(json.dumps({'pid':int((root/'qemu.pid').read_text()),'root':str(root)}))

class Qmp:
    def __init__(self,root):
        self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(10);self.sock.connect(str(pathlib.Path(root)/'qmp'));self.file=self.sock.makefile('rwb');json.loads(self.file.readline());self.call('qmp_capabilities')
    def call(self,name,args=None):
        value={'execute':name}
        if args is not None:value['arguments']=args
        self.file.write((json.dumps(value)+'\n').encode());self.file.flush()
        while True:
            response=json.loads(self.file.readline())
            if 'return' in response:return response['return']
            if 'error' in response:raise RuntimeError(response)
    def close(self):self.file.close();self.sock.close()

def serve(root,binary):
    root=pathlib.Path(root).resolve();binary=pathlib.Path(binary).resolve();work=queue.Queue();events=[];lock=threading.Lock()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,content='application/json'):
            data=value if isinstance(value,bytes) else json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.path=='/probe.exe':return self.send(binary.read_bytes(),'application/octet-stream')
            if self.path=='/meta':return self.send({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()})
            if self.path=='/work':
                try:return self.send(work.get_nowait())
                except queue.Empty:return self.send({})
            if self.path=='/state':
                with lock:return self.send(events[-1000:])
            self.send_error(404)
        def do_POST(self):
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>1048576:return self.send_error(413)
            value=json.loads(self.rfile.read(length))
            if self.path=='/queue':work.put(value);return self.send({'queued':True})
            if self.path in ['/hello','/event','/result','/agent-error']:
                record={'at':time.time(),'path':self.path,'value':value}
                with lock:
                    events.append(record)
                    with (root/'events.private.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
                return self.send({'recorded':True})
            self.send_error(404)
    http.server.ThreadingHTTPServer(('127.0.0.1',18722),Handler).serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','launch','serve','screenshot','boot-key']);p.add_argument('--root',required=True);p.add_argument('--iso');p.add_argument('--tools');p.add_argument('--binary');a=p.parse_args()
    if a.mode=='prepare':prepare(a.root,a.iso,a.tools)
    elif a.mode=='launch':launch(a.root)
    elif a.mode=='serve':serve(a.root,a.binary)
    else:
        q=Qmp(a.root)
        if a.mode=='screenshot':print(q.call('screendump',{'filename':str(pathlib.Path(a.root)/'screen.png'),'format':'png'}))
        else:
            for _ in range(4):q.call('send-key',{'keys':[{'type':'qcode','data':'spc'}]});time.sleep(1)
        q.close()

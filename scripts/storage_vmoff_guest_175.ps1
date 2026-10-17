param([string]$Base = 'http://10.0.2.2:18735')
# Disposable guest only. Each Process object below owns exactly one child.
$ErrorActionPreference = 'Stop'
$machine175 = Get-CimInstance Win32_ComputerSystem
if ($machine175.Manufacturer -ne 'QEMU' -or $machine175.Model -notmatch 'Q35') { throw 'Disposable QEMU Q35 guest required; host execution refused' }
$instance = [guid]::NewGuid().ToString('N')
$home175 = 'C:\ImageInfoGuest\qualification175'
$utf8 = New-Object Text.UTF8Encoding($false)
# Fixed read-only partition query. Zero desired access, OPEN_EXISTING, no setters
# or physical-drive handles. SDK STORAGE_WRITE_CACHE_PROPERTY uses 6 ULONG/enum
# fields followed by 3 BOOLEAN bytes (padded to 28 bytes).
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class Storage175Cache {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 static extern SafeFileHandle CreateFileW(string name,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)]
 static extern bool DeviceIoControl(SafeFileHandle handle,uint code,byte[] input,uint inputBytes,byte[] output,uint outputBytes,out uint returned,IntPtr overlapped);
 public static Dictionary<string,object> Query() {
  using(var handle=CreateFileW(@"\\.\C:",0,7,IntPtr.Zero,3,0,IntPtr.Zero)) {
   if(handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
   byte[] input=new byte[12]; input[0]=4; // StorageDeviceWriteCacheProperty, PropertyStandardQuery
   byte[] output=new byte[64]; uint returned;
   if(!DeviceIoControl(handle,0x002D1400,input,12,output,64,out returned,IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
   uint version=BitConverter.ToUInt32(output,0),size=BitConverter.ToUInt32(output,4);
   if(returned<27 || size<27 || size>64 || size>returned || version<27) throw new InvalidOperationException("CACHE_DESCRIPTOR_EXTENT");
   var result=new Dictionary<string,object>();
   result["querySucceeded"]=true; result["query"]="IOCTL_STORAGE_QUERY_PROPERTY/StorageDeviceWriteCacheProperty";
   result["version"]=version; result["size"]=size;
   result["type"]=BitConverter.ToUInt32(output,8); result["enabled"]=BitConverter.ToUInt32(output,12);
   result["changeable"]=BitConverter.ToUInt32(output,16); result["writeThrough"]=BitConverter.ToUInt32(output,20);
   result["flushSupported"]=output[24]!=0; result["userPowerProtection"]=output[25]!=0; result["nonvolatileCacheEnabled"]=output[26]!=0;
   result["rawBase64"]=Convert.ToBase64String(output,0,(int)returned); result["settingChanged"]=false;
   return result;
  }
 }
}
'@
function Send175($route, $value) {
    $bytes = $utf8.GetBytes(($value | ConvertTo-Json -Depth 40 -Compress))
    if ($bytes.Length -gt 8388608) { throw 'Transport capture bound exceeded' }
    Invoke-RestMethod ($Base+$route) -Method Post -TimeoutSec 20 -ContentType 'application/json' -Body $bytes | Out-Null
}
function SendResult175($value) {
    if ($value.id -notmatch '^[a-z0-9-]{1,90}$') { throw 'Invalid result identifier' }
    $bytes=$utf8.GetBytes(($value | ConvertTo-Json -Depth 40 -Compress))
    if ($bytes.Length -gt 8388608) { throw 'Result capture bound exceeded' }
    $path=Join-Path $home175 ($value.id+'-result.json')
    $file=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $file.Write($bytes,0,$bytes.Length);$file.Flush($true) } finally { $file.Dispose() }
    Send175 '/result' $value
}
function Get175($route) { Invoke-RestMethod ($Base+$route) -TimeoutSec 15 }
function Hash175($path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Hello175($challenge) {
    $os = Get-CimInstance Win32_OperatingSystem
    $servicing175 = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -Name UBR).UBR
    $drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $volume = Get-CimInstance Win32_Volume -Filter "DriveLetter='C:'"
    $controllers = @(Get-CimInstance Win32_IDEController | Sort-Object PNPDeviceID | Select-Object Name,Manufacturer,PNPDeviceID,Status)
    $drivers = @(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.DeviceClass -eq 'HDC'} | Sort-Object DeviceID | Select-Object DeviceName,DeviceID,DriverVersion,DriverDate,InfName,Manufacturer)
    $disks = @(Get-CimInstance Win32_DiskDrive | Sort-Object PNPDeviceID | Select-Object Model,InterfaceType,PNPDeviceID,Size,SerialNumber)
    try { $cachePolicy175=[Storage175Cache]::Query() } catch { $cachePolicy175=@{querySucceeded=$false; settingChanged=$false; diagnostic=$_.Exception.Message} }
    $groups = @(whoami.exe /groups /fo csv /nh)
    if (($groups -join "`n") -match 'S-1-5-32-544' -or ($groups -join "`n") -notmatch 'S-1-16-8192') { throw 'Ordinary medium integrity guest required' }
    if ($drive.FileSystem -ne 'NTFS' -or $drive.DriveType -ne 3) { throw 'Local NTFS guest required' }
    return @{ instance=$instance; challenge=$challenge; computer=$env:COMPUTERNAME; user=[Security.Principal.WindowsIdentity]::GetCurrent().Name; groups=$groups;
        boot=$os.LastBootUpTime.ToUniversalTime().ToString('o'); os=$os.Caption; build=$os.BuildNumber; version=$os.Version; servicingRevision=$servicing175; architecture=$os.OSArchitecture;
        filesystem=$drive.FileSystem; volumeSerial=$drive.VolumeSerialNumber; driveType=$drive.DriveType;
        clusterBytes=$volume.BlockSize; volumeSizeBytes=$volume.Capacity; volumeDeviceId=$volume.DeviceID;
        controllers=$controllers; controllerDrivers=$drivers; disks=$disks;
        guestCachePolicy=$cachePolicy175;
        workerSha256=(Hash175 "$home175\actor.exe"); readerSha256=(Hash175 "$home175\reader.ps1"); scriptSha256=(Hash175 $PSCommandPath) }
}
function Read175($path, $limit) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $item = Get-Item -LiteralPath $path -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -gt $limit) { throw 'Capture file bound/type exceeded' }
    $stream = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]7)
    try {
        $bytes = New-Object byte[] ($limit+1); $count=0
        while ($count -lt $bytes.Length) { $n=$stream.Read($bytes,$count,$bytes.Length-$count); if ($n -eq 0) { break }; $count+=$n }
        if ($count -gt $limit) { throw 'Capture grew beyond bound' }
        return [Convert]::ToBase64String($bytes,0,$count)
    } finally { $stream.Dispose() }
}
function Run175($job, $directory) {
    $child=New-Object Diagnostics.Process
    $child.StartInfo=New-Object Diagnostics.ProcessStartInfo
    $child.StartInfo.FileName="$home175\actor.exe"
    $child.StartInfo.Arguments='--exact storage::qualification::guest_actor --ignored --nocapture --test-threads=1'
    $child.StartInfo.UseShellExecute=$false; $child.StartInfo.CreateNoWindow=$true
    $child.StartInfo.RedirectStandardInput=$true; $child.StartInfo.RedirectStandardOutput=$true; $child.StartInfo.RedirectStandardError=$true
    $child.StartInfo.EnvironmentVariables['IMAGEINFO_175_CELL_DIR']=$directory
    $child.StartInfo.EnvironmentVariables['IMAGEINFO_175_MODE']=$job.mode
    $child.StartInfo.EnvironmentVariables['IMAGEINFO_175_CHECKPOINT']=$job.checkpoint
    $stdout=New-Object Text.StringBuilder; $stderr=New-Object Text.StringBuilder
    $pipeEvents175=New-Object Text.StringBuilder
    $control=$null; $gateSent=$false; $started=[DateTime]::UtcNow
    $eventPath=Join-Path $directory $(if($job.mode -eq 'inspect'){'inspect-events.jsonl'}else{'events.jsonl'})
    try {
        if (-not $child.Start()) { throw 'Owned child did not start' }
        $pid175=$child.Id; $outTask=$child.StandardOutput.ReadLineAsync(); $errTask=$child.StandardError.ReadLineAsync()
        while ($true) {
            foreach ($channel in @('out','err')) {
                $task=if($channel -eq 'out'){$outTask}else{$errTask}
                if ($null -ne $task -and $task.IsCompleted) {
                    $line=$task.GetAwaiter().GetResult()
                    if ($null -ne $line) {
                        $buffer=if($channel -eq 'out'){$stdout}else{$stderr}
                        if ($buffer.Length+$line.Length -gt 1048576) { throw 'Child output bound exceeded' }
                        $null=$buffer.AppendLine($line)
                        if ($channel -eq 'out' -and $line.Contains('IMAGEINFO175 ')) {
                            $canonical175=$line.Substring($line.IndexOf('IMAGEINFO175 ')+13)
                            $event175=$canonical175 | ConvertFrom-Json
                            if ($event175.schema -ne 'imageinfo-0175-event-v1' -or $event175.pid -ne $pid175) { throw 'Private pipe event binding mismatch' }
                            if ($pipeEvents175.Length+$canonical175.Length -gt 1048576) { throw 'Private pipe event bound exceeded' }
                            $null=$pipeEvents175.Append($canonical175+"`n")
                            if (-not $gateSent -and $event175.gate -and $event175.event -eq $job.checkpoint) {
                                Send175 '/event' @{id=$job.id; kind='gate'; instance=$instance; pid=$pid175; actorEvent=$event175;
                                    eventFileBase64=[Convert]::ToBase64String($utf8.GetBytes($pipeEvents175.ToString()));
                                    pipeNotice=$line; transport='owned-child-stdout-private-pipe'; guestUtc=[DateTime]::UtcNow.ToString('o')}
                                $gateSent=$true
                            }
                        }
                        if($channel -eq 'out'){$outTask=$child.StandardOutput.ReadLineAsync()}else{$errTask=$child.StandardError.ReadLineAsync()}
                    } else { if($channel -eq 'out'){$outTask=$null}else{$errTask=$null} }
                }
            }
            if ($gateSent -and -not $child.HasExited) {
                $command=Get175 ('/control?id='+$job.id)
                if ($command.action -eq 'kill') {
                    $child.Kill(); if (-not $child.WaitForExit(10000)) { throw 'Owned child exit unconfirmed' }
                    $control=@{action='kill'; pid=$pid175; processExitConfirmed=$true; exitCode=$child.ExitCode; guestUtc=[DateTime]::UtcNow.ToString('o')}
                } elseif ($command.action -eq 'continue') {
                    $child.StandardInput.Write("continue`n");$child.StandardInput.Flush(); $control=@{action='continue'; pid=$pid175}
                }
            }
            if ($child.HasExited -and $null -eq $outTask -and $null -eq $errTask) { break }
            if (([DateTime]::UtcNow-$started).TotalSeconds -gt 180) { throw 'Owned child deadline exceeded' }
            Start-Sleep -Milliseconds 50
        }
        return @{id=$job.id; instance=$instance; pid=$pid175; exitCode=$child.ExitCode; control=$control; gateObserved=$gateSent; stdout=$stdout.ToString(); stderr=$stderr.ToString();
            eventFileBase64=[Convert]::ToBase64String($utf8.GetBytes($pipeEvents175.ToString())); guestDiagnosticBase64=(Read175 $eventPath 1048576); guestUtc=[DateTime]::UtcNow.ToString('o')}
    } catch {
        $diagnostic175=$_.Exception.Message; $cleanupError175=$null; $exited175=$false
        if ($pid175) {
            try {
                if (-not $child.HasExited) { $child.Kill() }
                $exited175=$child.WaitForExit(10000)
            } catch { $cleanupError175=$_.Exception.Message }
        }
        try { $partialEvents175=Read175 $eventPath 1048576 } catch { $partialEvents175=$null; $cleanupError175=($_.Exception.Message) }
        return @{id=$job.id; instance=$instance; pid=$pid175; failed=$true; diagnostic=$diagnostic175;
            exitConfirmed=$exited175; exitCode=$(if($exited175){$child.ExitCode}else{$null}); control=$control; gateObserved=$gateSent;
            stdout=$stdout.ToString(); stderr=$stderr.ToString(); eventFileBase64=[Convert]::ToBase64String($utf8.GetBytes($pipeEvents175.ToString())); guestDiagnosticBase64=$partialEvents175;
            failureCleanup=@{ownedChildExitConfirmed=$exited175; error=$cleanupError175}; guestUtc=[DateTime]::UtcNow.ToString('o')}
    } finally {
        # The success path has confirmed exit; the catch owns one exact cleanup
        # attempt and records any failure. Never replace that retained result.
        try { $child.Dispose() } catch { }
    }
}
$agentLock=New-Object Threading.Mutex($false,'Local\ImageInfoQualification175')
if (-not $agentLock.WaitOne(0)) { exit 0 }
New-Item -ItemType Directory -Path $home175 -Force | Out-Null
$meta=Get175 '/meta'
foreach ($entry in @(@('actor.exe','workerSha256'),@('reader.ps1','readerSha256'))) {
    $destination=Join-Path $home175 $entry[0]
    Invoke-WebRequest ($Base+'/'+$entry[0]) -OutFile ($destination+'.new') -UseBasicParsing
    if ((Hash175 ($destination+'.new')) -ne $meta.($entry[1])) { throw 'Pinned payload mismatch' }
    Move-Item -LiteralPath ($destination+'.new') -Destination $destination -Force
}
if ((Hash175 $PSCommandPath) -ne $meta.guestScriptSha256) { throw 'Pinned agent mismatch' }
Send175 '/hello' (Hello175 'startup')
try {
while ($true) {
    $job=Get175 '/job'
    if (-not $job.id) { Start-Sleep -Milliseconds 500; continue }
    try {
        if ($job.action -eq 'hello') { SendResult175 @{id=$job.id; hello=(Hello175 $job.challenge)}; continue }
        if ($job.action -eq 'stop-agent') { SendResult175 @{id=$job.id; instance=$instance; agentStopped=$true}; break }
        if ($job.cell -notmatch '^[a-z0-9-]{1,60}$') { throw 'Invalid fixed cell name' }
        $directory=Join-Path $home175 $job.cell
        if ($job.action -eq 'run') {
            if ($job.mode -notin @('run','finalize','cleanup','inspect')) { throw 'Invalid actor mode' }
            if ($job.mode -eq 'inspect') { if (-not (Test-Path -LiteralPath $directory -PathType Container)) { throw 'Missing cell' } }
            else { if (Test-Path -LiteralPath $directory) { throw 'Fresh cell required; existing evidence retained' }; $null=New-Item -ItemType Directory -Path $directory }
            $result=Run175 $job $directory; SendResult175 $result
        } elseif ($job.action -eq 'snapshot') {
            if ($job.stage -notin @('before-inspect','after-inspect')) { throw 'Invalid snapshot stage' }
            $destination=Join-Path $home175 ($job.cell+'-'+$job.stage+'.json')
            $readerOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$home175\reader.ps1" -CellDirectory $directory -Destination $destination 2>&1
            if ($LASTEXITCODE -ne 0) { throw ('Independent reader failed: '+($readerOutput -join "`n")) }
            SendResult175 @{id=$job.id; instance=$instance; snapshotBase64=(Read175 $destination 4194304); readerSha256=(Hash175 "$home175\reader.ps1")}
        } else { throw 'Unsupported fixed action' }
    } catch { SendResult175 @{id=$job.id; instance=$instance; failed=$true; diagnostic=$_.Exception.Message; guestUtc=[DateTime]::UtcNow.ToString('o')} }
}
} finally {
    try { $agentLock.ReleaseMutex() } catch { }
    $agentLock.Dispose()
}

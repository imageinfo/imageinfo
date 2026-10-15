param(
    [Parameter(Mandatory=$true)][string]$Drive,
    [Parameter(Mandatory=$true)][string]$FixtureId,
    [Parameter(Mandatory=$true)][string]$Worker,
    [Parameter(Mandatory=$true)][string]$WorkerSha256,
    [Parameter(Mandatory=$true)][string]$Capture
)
# Run inside the disposable evaluation guest as its standard user. No disk setup,
# privilege changes, device faults, transaction cleanup, or host operations occur.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($FixtureId -notmatch '^[a-zA-Z0-9-]{1,64}$') { throw 'Bounded simple fixture id required' }
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Standard user required' }
if ($Drive -notmatch '^[D-Zd-z]:\\$' -or $Drive.Substring(0,2) -eq $env:SystemDrive) { throw 'Secondary drive required' }
$volume = [IO.DriveInfo]::new($Drive)
if ($volume.DriveFormat -ne 'NTFS' -or $volume.VolumeLabel -ne 'IMAGEINFO0048' -or $volume.TotalSize -lt 64MB -or $volume.TotalSize -gt 128MB) { throw 'Fixture NTFS/label/size guard failed' }
$partition = Get-Partition -DriveLetter $Drive.Substring(0,1)
if ($partition.IsBoot -or $partition.IsSystem) { throw 'System/boot partition refused' }
if ((Get-Item -LiteralPath $Drive).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse root refused' }
$markerPath = Join-Path $Drive '.imageinfo-0048-fixture.json'
$marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
if ($marker.schema -ne 'imageinfo-native-errors-fixture-v1' -or $marker.fixture_id -ne $FixtureId -or $marker.drive -ne $Drive -or $marker.max_bytes -ne 134217728) { throw 'Exact fixture marker required' }
$Worker = (Resolve-Path -LiteralPath $Worker).Path
if ($WorkerSha256.ToLowerInvariant() -ne 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa') { throw 'Frozen #0047 static worker required' }
if ((Get-FileHash -LiteralPath $Worker -Algorithm SHA256).Hash.ToLowerInvariant() -ne $WorkerSha256.ToLowerInvariant()) { throw 'Worker binding mismatch' }
$Capture = [IO.Path]::GetFullPath($Capture)
if ($Capture.StartsWith($Drive, [StringComparison]::OrdinalIgnoreCase)) { throw 'Captures must be outside full fixture' }
if (Test-Path -LiteralPath $Capture) { throw 'Fresh capture directory required' }
New-Item -ItemType Directory -Path $Capture | Out-Null
$run = Join-Path $Drive ('native-errors-' + $FixtureId)
if (Test-Path -LiteralPath $run) { throw 'Fresh fixture run required' }
New-Item -ItemType Directory -Path $run | Out-Null
function Save($name, $value) { $value | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath (Join-Path $Capture $name) -Encoding UTF8 }
function Snapshot($root) {
    $items = @()
    foreach ($file in Get-ChildItem -LiteralPath $root -Force -File) {
        $identity = & fsutil file queryfileid $file.FullName 2>&1 | Out-String
        $identityCode = $LASTEXITCODE
        $items += [ordered]@{ name=$file.Name; size=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant(); fileIdQuery=$identity.Trim(); fileIdQueryExitCode=$identityCode; creation=$file.CreationTimeUtc.Ticks; write=$file.LastWriteTimeUtc.Ticks; attributes=[int]$file.Attributes; sddl=(Get-Acl -LiteralPath $file.FullName).Sddl }
    }
    return ,$items
}
function Fill($path, $release) {
    # Real allocated writes, never SetLength growth or a sparse-file simulation.
    $stream = [IO.File]::Open($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $buffer = New-Object byte[] 4096
    for ($i=0; $i -lt $buffer.Length; $i++) { $buffer[$i]=[byte](($i*17+31)%251) }
    $count=0L; $failure=$null
    try {
        while ($count -le 128MB) {
            try { $stream.Write($buffer,0,$buffer.Length); $stream.Flush($true); $count += $buffer.Length }
            catch { $e=$_.Exception; while ($e.InnerException) { $e=$e.InnerException }; $failure=[ordered]@{ type=$e.GetType().FullName; hresult=$e.HResult; message=$e.Message; operation='FileStream.Write/Flush(true)'; successfullyWrittenBytes=$count }; break }
        }
        if (-not $failure) { throw 'Bound reached without native failure' }
        if ($release -gt 0 -and $stream.Length -ge $release) { $stream.SetLength($stream.Length-$release); $stream.Flush($true) }
    } finally { $stream.Dispose() }
    return [ordered]@{ provenance='actual-native-filler-io'; failure=$failure; releasedBytes=$release; fillerLength=(Get-Item -LiteralPath $path).Length; availableBytes=([IO.DriveInfo]::new($Drive)).AvailableFreeSpace }
}
function Invoke-Worker($transaction, $mode, $phase, $filler, $release, $inputLine) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName=$Worker; $info.Arguments='"'+$transaction+'" '+$mode
    $info.UseShellExecute=$false; $info.CreateNoWindow=$true
    $info.RedirectStandardInput=$true; $info.RedirectStandardOutput=$true; $info.RedirectStandardError=$true
    $p=[Diagnostics.Process]::Start($info)
    $stderr=$p.StandardError.ReadToEndAsync(); $events=@(); $controls=@(); $fill=$null
    try {
        if ($inputLine) { $p.StandardInput.WriteLine($inputLine); $p.StandardInput.Flush() }
        while ($true) {
            $read=$p.StandardOutput.ReadLineAsync()
            if (-not $read.Wait(45000)) { throw 'Worker line deadline (not native I/O cancellation qualification)' }
            $line=$read.Result
            if ($null -eq $line) { break }
            $event=$line | ConvertFrom-Json; $events += $event
            foreach ($flag in @('committed','namespaceAcknowledged','repairAllowed','productionPublicationAllowed')) { if ($event.$flag -ne $false) { throw ('False flag required: '+$flag) } }
            if ($event.PSObject.Properties.Name -contains 'barrier') {
                if ($event.barrier -eq $phase) { $fill=Fill $filler $release }
                $p.StandardInput.WriteLine('continue'); $p.StandardInput.Flush(); $controls+='continue'
            }
        }
        if (-not $p.WaitForExit(45000)) { throw 'Worker exit deadline' }
        return [ordered]@{ exitCode=$p.ExitCode; events=$events; controls=$controls; stderr=$stderr.Result; fill=$fill }
    } finally { if (-not $p.HasExited) { $p.Kill(); $p.WaitForExit() }; $p.Dispose() }
}
Save 'binding.private.json' ([ordered]@{ fixture=$marker; markerSha256=(Get-FileHash $markerPath -Algorithm SHA256).Hash.ToLowerInvariant(); workerSha256=$WorkerSha256.ToLowerInvariant(); sourceRevision='b819f54533c495b332c3d4dbb0caccef49923036'; volumeBytes=$volume.TotalSize; driveFormat=$volume.DriveFormat; partition=$partition | Select-Object DiskNumber,PartitionNumber,IsBoot,IsSystem; os=[Environment]::OSVersion.VersionString; user=[Security.Principal.WindowsIdentity]::GetCurrent().Name })
$cases=@()
foreach ($spec in @(@('normal-control','',0), @('candidate-full','source-guarded',0), @('candidate-partial-attempt','source-guarded',32768), @('prepared-record-full','candidate-flushed',0), @('receipt-full','observation-parent-flushed',0))) {
    $id=$spec[0]; $folder=Join-Path $run $id; New-Item -ItemType Directory -Path $folder | Out-Null
    $transaction=Join-Path $folder 'transaction.marker'; $filler=Join-Path $folder 'filler.owned'
    $prepare=Invoke-Worker $transaction 'ordinary-prepare' '' '' 0 ''
    Save ($id+'-prepare.private.json') $prepare
    if ($prepare.exitCode -ne 0) { throw 'Preparation failed' }
    $sourceBefore=Snapshot $transaction
    $result=Invoke-Worker $transaction 'ordinary-receipt' $spec[1] $filler $spec[2] ''
    Save ($id+'-worker.private.json') $result
    $before=Snapshot $transaction
    # Missing caller context is an explicit bounded refusal input, never an
    # invented receipt binding; normal control uses its actual emitted context.
    $context='{}'
    foreach ($event in $result.events) { if ($event.PSObject.Properties.Name -contains 'receiptContext') { $context=$event.receiptContext | ConvertTo-Json -Depth 80 -Compress } }
    $inspection=Invoke-Worker $transaction 'ordinary-receipt-inspect' '' '' 0 $context
    $after=Snapshot $transaction
    Save ($id+'-inspection.private.json') ([ordered]@{input=$context; result=$inspection; before=$before; after=$after})
    $cases += [ordered]@{ id=$id; phase=$spec[1]; sourceBefore=$sourceBefore; worker=$result; beforeInspection=$before; afterInspection=$after; inspection=$inspection; receiptContextAvailable=($context -ne '{}') }
    Save 'cases.private.json' $cases
    # Remove only this controller-created filler after worker exit and inventory.
    # Retain all transaction/source/output/recovery artifacts for independent audit.
    if (Test-Path -LiteralPath $filler) { Remove-Item -LiteralPath $filler }
}
Save 'complete.private.json' ([ordered]@{cases=$cases.Count; readFailure='unrun-unqualified'; flushDeviceFailure='unrun-unqualified'; metadataOnlyFull='not-isolated'; nativeShortWrite='requires-observed-partial-length'; commitmentQualified=$false; cleanupAuthorized=$false})

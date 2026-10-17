param([string]$Base = 'http://10.0.2.2:18724')
$ErrorActionPreference = 'Stop'
$capture = 'C:\ImageInfoGuest174'
New-Item -ItemType Directory -Path $capture -Force | Out-Null
function Post($path, $value) {
    Invoke-RestMethod -Uri ($Base + $path) -Method Post -TimeoutSec 35 -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 20 -Compress)))
}
function Inventory($path, $hash) {
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    $entries = @(Get-ChildItem -LiteralPath $path -Force -File)
    if ($entries.Count -gt 8) { throw 'Inventory bound exceeded' }
    return @($entries | ForEach-Object {
        $v = @{name=$_.Name; bytes=$_.Length; creation=$_.CreationTimeUtc.ToString('o'); write=$_.LastWriteTimeUtc.ToString('o'); attributes=[string]$_.Attributes; sddl=(Get-Acl -LiteralPath $_.FullName).Sddl; identity=((& fsutil.exe file queryfileid $_.FullName) -join "`n"); streams=@(Get-Item -LiteralPath $_.FullName -Stream * | ForEach-Object {@{name=$_.Stream;bytes=$_.Length}})}
        if ($hash) { $v.sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
        $v
    })
}
try {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator refused' }
    $meta = Invoke-RestMethod ($Base + '/meta') -TimeoutSec 15
    & curl.exe --fail --silent --show-error ($Base + '/worker.exe') -o ($capture + '\worker.exe')
    if ($LASTEXITCODE -ne 0 -or (Get-FileHash ($capture + '\worker.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $meta.workerSha256) { throw 'Worker binding mismatch' }
    foreach ($cell in $meta.cells) {
        $volume = @(Get-Volume | Where-Object {$_.FileSystemLabel -eq $cell.volume})
        if ($volume.Count -ne 1 -or $volume[0].FileSystem -ne 'NTFS' -or $volume[0].Size -gt 134217728) { throw 'Exact bounded NTFS fixture required' }
        $drive = ([string]$volume[0].DriveLetter) + ':\'
        $partition = Get-Partition -DriveLetter $volume[0].DriveLetter
        if ($partition.IsSystem -or $partition.IsBoot -or $drive.Substring(0,2) -eq $env:SystemDrive) { throw 'System volume refused' }
        [IO.File]::WriteAllText(($drive + 'fixture174.marker'), "imageinfo-0174-disposable-authored-only-v1`n", [Text.UTF8Encoding]::new($false))
        $root = $drive + 'case'
        New-Item -ItemType Directory -Path $root | Out-Null
        Move-Item -LiteralPath ($drive + 'source.bin') -Destination ($root + '\source.bin')
        $before = @(Inventory $root $false)
        $p = New-Object Diagnostics.Process
        $p.StartInfo = New-Object Diagnostics.ProcessStartInfo
        $p.StartInfo.FileName = $capture + '\worker.exe'
        $p.StartInfo.Arguments = '--exact storage::native_errors::guest_native_error_worker --ignored --nocapture --test-threads=1'
        $p.StartInfo.UseShellExecute=$false; $p.StartInfo.CreateNoWindow=$true
        $p.StartInfo.RedirectStandardInput=$true; $p.StartInfo.RedirectStandardOutput=$true; $p.StartInfo.RedirectStandardError=$true
        $p.StartInfo.EnvironmentVariables['IMAGEINFO_174_ROOT']=$root
        $null = Post '/start' @{cell=$cell.cell;before=$before;volume=($volume[0] | Select-Object FileSystem,FileSystemLabel,Size,SizeRemaining);partition=($partition | Select-Object DiskNumber,PartitionNumber,IsBoot,IsSystem);groups=(& whoami.exe /groups /fo csv);os=[Environment]::OSVersion.Version.ToString()}
        $lines=@(); $events=@(); $timedOut=$false
        try {
            $null=$p.Start(); $stderr=$p.StandardError.ReadToEndAsync()
            while ($true) {
                $read=$p.StandardOutput.ReadLineAsync()
                if (-not $read.Wait(180000)) {$timedOut=$true;throw 'Bounded worker line deadline'}
                $line=$read.Result
                if ($null -eq $line) {break}
                $lines+=,$line
                $index=$line.IndexOf('IMAGEINFO174 ')
                if ($index -ge 0) {
                    $event=$line.Substring($index+13) | ConvertFrom-Json
                    $events+=,$event
                    $null=Post '/event' @{cell=$cell.cell;event=$event}
                    if ($event.barrier) {$p.StandardInput.WriteLine('continue');$p.StandardInput.Flush()}
                }
            }
            if (-not $p.WaitForExit(15000)) {$timedOut=$true;throw 'Bounded worker exit deadline'}
        } finally {
            if ($p.Id -and -not $p.HasExited) {$p.Kill();$p.WaitForExit()}
            $null=Post '/clear' @{cell=$cell.cell}
        }
        $result=@{cell=$cell.cell;before=$before;after=@(Inventory $root $true);unit=@(Inventory ($root+'\unit') $true);events=$events;stdout=$lines;stderr=$stderr.Result;exitCode=$p.ExitCode;timedOut=$timedOut;workerSha256=$meta.workerSha256}
        $result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath ($capture+'\'+$cell.cell+'.private.json') -Encoding UTF8
        $null=Post '/result' $result
        $p.Dispose()
    }
    $null=Post '/finished' @{finished=$true}
} catch {
    $null=Post '/failed' @{failed=$true;error=($_ | Out-String)}
}

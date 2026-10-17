param([string]$Base='http://10.0.2.2:18727')
$ErrorActionPreference='Stop'
function Post($value) {
    Invoke-RestMethod ($Base+'/result') -Method Post -TimeoutSec 30 -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes(($value|ConvertTo-Json -Depth 12 -Compress))) | Out-Null
}
try {
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Standard-user fixture required'}
    $volume=@(Get-Volume|Where-Object {$_.FileSystemLabel -eq 'I197FULL'})
    if($volume.Count -ne 1 -or $volume[0].FileSystem -ne 'NTFS' -or $volume[0].Size -gt 134217728 -or $volume[0].Size -lt 100663296){throw 'Exact bounded secondary volume required'}
    $part=Get-Partition -DriveLetter $volume[0].DriveLetter
    $drive=[string]$volume[0].DriveLetter+':\'
    if($part.IsSystem -or $part.IsBoot -or $drive.Substring(0,2) -eq $env:SystemDrive){throw 'System disk refused'}
    if(@(Get-ChildItem -LiteralPath $drive -Force | Where-Object {$_.Name -ne 'System Volume Information'}).Count -ne 0){throw 'Fresh empty fixture required'}
    [IO.File]::WriteAllText(($drive+'fixture197.marker'),"imageinfo-0197-fresh-authored-128m-v1`n",[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllBytes(($drive+'source.bin'),[Text.Encoding]::ASCII.GetBytes(('S'*4096)))
    [IO.File]::WriteAllBytes(($drive+'original.bin'),[Text.Encoding]::ASCII.GetBytes(('O'*4096)))
    $capture='C:\ImageInfoGuest197'
    New-Item -ItemType Directory -Path $capture | Out-Null
    $meta=Invoke-RestMethod ($Base+'/meta') -TimeoutSec 15
    & curl.exe --fail --silent --show-error ($Base+'/worker.exe') -o ($capture+'\worker.exe')
    if($LASTEXITCODE -ne 0 -or (Get-FileHash ($capture+'\worker.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $meta.workerSha256){throw 'Worker binding mismatch'}
    $p=[Diagnostics.Process]::new();$p.StartInfo=[Diagnostics.ProcessStartInfo]::new()
    $p.StartInfo.FileName=$capture+'\worker.exe'
    $p.StartInfo.Arguments='--exact storage::replacement_resources::tests::native::guest_bounded_storage_full_refusal --ignored --nocapture --test-threads=1'
    $p.StartInfo.UseShellExecute=$false;$p.StartInfo.CreateNoWindow=$true
    $p.StartInfo.RedirectStandardOutput=$true;$p.StartInfo.RedirectStandardError=$true
    $p.StartInfo.EnvironmentVariables['IMAGEINFO_197_DRIVE']=$drive
    $null=$p.Start();$stdout=$p.StandardOutput.ReadToEndAsync();$stderr=$p.StandardError.ReadToEndAsync()
    if(-not $p.WaitForExit(180000)){$p.Kill();$p.WaitForExit();throw 'Bounded worker deadline expired'}
    $value=@{exitCode=$p.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;workerSha256=$meta.workerSha256;volume=($volume[0]|Select-Object FileSystem,FileSystemLabel,Size,SizeRemaining);partition=($part|Select-Object DiskNumber,PartitionNumber,IsBoot,IsSystem);standardUser=$true;os=[Environment]::OSVersion.Version.ToString();files=@(Get-ChildItem -LiteralPath $drive -File -Force|ForEach-Object {@{name=$_.Name;bytes=$_.Length}})}
    $value|ConvertTo-Json -Depth 12|Set-Content -LiteralPath ($capture+'\result.private.json') -Encoding UTF8
    Post $value
} catch {Post @{failed=$true;error=($_|Out-String)}}

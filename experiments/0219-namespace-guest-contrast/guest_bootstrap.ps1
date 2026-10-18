# Definitions only: dot-sourcing never queries the machine or starts a process.
# The current parent supplies private paths and independently reviewed pins.
function Assert-Namespace219LocalPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    if ($Path -notmatch '^[A-Za-z]:\\' -or $Path -match '["\r\n\x00]' -or
        [IO.Path]::GetFullPath($Path) -cne $Path) {
        throw 'A canonical absolute local path is required'
    }
}

function Assert-Namespace219PinnedFile {
    param([string]$Path, [string]$Sha256)
    Assert-Namespace219LocalPath $Path
    if ($Sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid SHA256 pin' }
    $item219 = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($item219.PSIsContainer -or ($item219.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Pinned payload must be an ordinary file'
    }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $Sha256) {
        throw 'Pinned payload hash mismatch'
    }
}

function Get-Namespace219GuestReadiness {
    # No software installation, download, elevation, or machine configuration.
    $machine219 = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    if ($machine219.Manufacturer -ne 'QEMU' -or $machine219.Model -notmatch 'Q35') {
        throw 'Disposable QEMU Q35 guest required; host execution refused'
    }
    $identity219 = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal219 = New-Object Security.Principal.WindowsPrincipal($identity219)
    $groups219 = @($identity219.Groups | ForEach-Object { $_.Value })
    if ($principal219.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
        'S-1-5-32-544' -in $groups219 -or 'S-1-16-8192' -notin $groups219) {
        throw 'Ordinary non-administrator medium-integrity guest required'
    }
    $os219 = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    return [ordered]@{
        manufacturer=$machine219.Manufacturer; model=$machine219.Model
        userSid=$identity219.User.Value; groups=$groups219
        boot=$os219.LastBootUpTime.ToUniversalTime().ToString('o')
        build=$os219.BuildNumber; architecture=$os219.OSArchitecture
        administrator=$false; mediumIntegrity=$true
    }
}

function Write-Namespace219NewJson {
    param([string]$Path, $Value)
    $encoding219 = New-Object Text.UTF8Encoding($false)
    $bytes219 = $encoding219.GetBytes(($Value | ConvertTo-Json -Depth 24 -Compress)+"`n")
    if ($bytes219.Length -gt 1048576) { throw 'Bootstrap JSON bound exceeded' }
    $file219 = [IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $file219.Write($bytes219,0,$bytes219.Length); $file219.Flush($true) }
    finally { $file219.Dispose() }
}

function Read-Namespace219PinnedJson {
    param([string]$Path,[string]$Sha256)
    Assert-Namespace219PinnedFile $Path $Sha256
    if ((Get-Item -LiteralPath $Path).Length -gt 1048576) { throw 'Pinned JSON bound exceeded' }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-Namespace219VolumeBinding {
    param([string]$PlanPath,[string]$PlanSha256,[string]$DiagnosticPlanSha256,[string]$Destination)
    $ErrorActionPreference='Stop'
    $null=Get-Namespace219GuestReadiness
    Assert-Namespace219LocalPath $Destination
    Assert-Namespace219PinnedFile $PlanPath $PlanSha256
    if ($DiagnosticPlanSha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Exact diagnostic plan digest required' }
    # Retain the exact selection bytes that are hashed and parsed, separately
    # from the whole diagnostic plan. A path hash is not a resident-code claim.
    $selectionBytes219=[IO.File]::ReadAllBytes($PlanPath)
    if ($selectionBytes219.Length -eq 0 -or $selectionBytes219.Length -gt 16384) { throw 'Volume selection byte bound' }
    $selectionHasher219=[Security.Cryptography.SHA256]::Create()
    try { $selectionDigest219=([BitConverter]::ToString($selectionHasher219.ComputeHash($selectionBytes219))).Replace('-','').ToLowerInvariant() }
    finally { $selectionHasher219.Dispose() }
    if ($selectionDigest219 -cne $PlanSha256) { throw 'Volume selection changed before capture' }
    $selectionEncoding219=New-Object Text.UTF8Encoding($false,$true)
    $plan219=$selectionEncoding219.GetString($selectionBytes219) | ConvertFrom-Json
    if ($plan219.unit -cnotmatch '^[A-Za-z0-9_-]{1,64}$' -or
        $plan219.fixture_relative -cnotmatch '^[A-Za-z0-9_-]{1,64}$' -or
        $plan219.min_disk_bytes -lt 33554432 -or
        $plan219.max_disk_bytes -gt 1073741824 -or
        $plan219.min_disk_bytes -gt $plan219.max_disk_bytes) { throw 'Invalid bounded volume plan' }
    $volumes219=@(Get-Volume -ErrorAction Stop | Where-Object { $_.FileSystemLabel -ceq $plan219.label })
    if ($volumes219.Count -ne 1) { throw 'Exactly one selected guest volume required' }
    $volume219=$volumes219[0]
    if ($volume219.FileSystem -ne 'NTFS' -or $null -eq $volume219.DriveLetter -or
        "$($volume219.DriveLetter)" -notmatch '^[A-Za-z]$') { throw 'Selected mounted NTFS volume required' }
    $partitions219=@(Get-Partition -DriveLetter $volume219.DriveLetter -ErrorAction Stop)
    if ($partitions219.Count -ne 1) { throw 'Exactly one mapped partition required' }
    $partition219=$partitions219[0]
    $disk219=Get-Disk -Number $partition219.DiskNumber -ErrorAction Stop
    $driveRoot219="$($volume219.DriveLetter):\"
    $logical219=@(Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='"+$volume219.DriveLetter+":'") -ErrorAction Stop)
    if ($logical219.Count -ne 1 -or $logical219[0].DriveType -ne 3) { throw 'Exactly one local logical disk required' }
    $serial219=$disk219.SerialNumber.Trim()
    $volumeSerial219=([Convert]::ToUInt32($logical219[0].VolumeSerialNumber,16)).ToString('X8')
    $root219=Join-Path $driveRoot219 $plan219.fixture_relative
    if ($disk219.IsBoot -or $disk219.IsSystem -or $partition219.IsBoot -or $partition219.IsSystem -or
        $disk219.Size -lt $plan219.min_disk_bytes -or $disk219.Size -gt $plan219.max_disk_bytes -or
        [string]$disk219.BusType -cne $plan219.bus_type -or $plan219.bus_type -cne 'USB' -or
        $serial219 -cne $plan219.device_serial -or $volumeSerial219 -cne $plan219.volume_serial -or
        $volume219.UniqueId -cne $plan219.volume_unique_id -or
        $disk219.Number -ne $plan219.disk_number -or $partition219.PartitionNumber -ne $plan219.partition_number -or
        $root219 -cne $plan219.root) { throw 'Actual guest volume does not match exact reviewed plan' }
    $binding219=[ordered]@{
        schema='imageinfo-0219-volume-binding-v1'; generated_by='Get-Volume/Get-Partition/Get-Disk/Win32_LogicalDisk'
        device_serial=$serial219; volume_serial=$volumeSerial219; drive_root=$driveRoot219
        root=$root219; unit=$plan219.unit; disk_number=$disk219.Number
        partition_number=$partition219.PartitionNumber; volume_unique_id=$volume219.UniqueId
        filesystem=$volume219.FileSystem; is_boot=[bool]$disk219.IsBoot; is_system=[bool]$disk219.IsSystem
        partition_is_boot=[bool]$partition219.IsBoot; partition_is_system=[bool]$partition219.IsSystem
        disk_size_bytes=$disk219.Size; partition_size_bytes=$partition219.Size; volume_size_bytes=$volume219.Size
        disk_bus_type=[string]$disk219.BusType; disk_friendly_name=$disk219.FriendlyName
        partition_offset=$partition219.Offset; plan_sha256=$DiagnosticPlanSha256
        volume_plan_sha256=$selectionDigest219; volume_plan_bytes_base64=[Convert]::ToBase64String($selectionBytes219)
        guestUtc=[DateTime]::UtcNow.ToString('o')
    }
    Write-Namespace219NewJson $Destination $binding219
    return [pscustomobject]$binding219
}

function Stage-Namespace219Payload {
    # Explicit ordinary-user portable staging; never an installer or service.
    param([string]$AssetUri,[string]$ArchiveSha256,[string]$EntryPinsPath,[string]$EntryPinsSha256,[string]$StageDirectory)
    $ErrorActionPreference='Stop'
    $null=Get-Namespace219GuestReadiness
    Assert-Namespace219LocalPath $StageDirectory
    $uri219=[Uri]$AssetUri
    if ($uri219.Scheme -ne 'http' -or $uri219.Host -ne '10.0.2.2' -or
        $uri219.Port -lt 1024 -or $uri219.Port -gt 65535 -or
        $uri219.AbsolutePath -cnotmatch '^/[A-Za-z0-9_.-]{1,100}$' -or $uri219.Query -or $uri219.Fragment -or $uri219.UserInfo -or
        $ArchiveSha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Exact pinned private NAT asset required' }
    $pins219=Read-Namespace219PinnedJson $EntryPinsPath $EntryPinsSha256
    $entries219=@($pins219.PSObject.Properties)
    if ($entries219.Count -lt 2 -or $entries219.Count -gt 10000) { throw 'Payload entry count bound' }
    foreach ($entry219 in $entries219) {
        if ($entry219.Name -cnotmatch '^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$' -or
            @($entry219.Name.Split('/') | Where-Object { $_ -in @('.','..') }).Count -or
            $entry219.Value -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid pinned archive entry' }
    }
    if (Test-Path -LiteralPath $StageDirectory) { throw 'Fresh portable staging required; existing evidence retained' }
    $null=New-Item -ItemType Directory -Path $StageDirectory
    $archive219=Join-Path $StageDirectory 'payload.zip'
    $payload219=Join-Path $StageDirectory 'payload'
    $null=New-Item -ItemType Directory -Path $payload219
    $response219=$null; $input219=$null; $output219=$null
    $total219=0
    try {
        $request219=[Net.HttpWebRequest]::Create($uri219)
        $request219.Timeout=20000; $request219.ReadWriteTimeout=20000
        $request219.AllowAutoRedirect=$false; $request219.Proxy=$null
        $response219=$request219.GetResponse()
        if ([int]$response219.StatusCode -ne 200 -or $response219.ContentLength -gt 67108864) { throw 'Asset response status/length refused' }
        $input219=$response219.GetResponseStream()
        $output219=[IO.File]::Open($archive219,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
        $buffer219=New-Object byte[] 65536
        $watch219=[Diagnostics.Stopwatch]::StartNew()
        while (($count219=$input219.Read($buffer219,0,$buffer219.Length)) -gt 0) {
            $total219+=$count219
            if ($total219 -gt 67108864 -or $watch219.Elapsed.TotalSeconds -gt 120) { throw 'Asset byte/deadline bound exceeded' }
            $output219.Write($buffer219,0,$count219)
        }
        $output219.Flush($true)
    } finally {
        if ($null -ne $output219) { $output219.Dispose() }
        if ($null -ne $input219) { $input219.Dispose() }
        if ($null -ne $response219) { $response219.Dispose() }
    }
    Assert-Namespace219PinnedFile $archive219 $ArchiveSha256
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip219=[IO.Compression.ZipFile]::OpenRead($archive219)
    $seen219=@{}; $expanded219=0
    try {
        if ($zip219.Entries.Count -ne $entries219.Count) { throw 'ZIP file-entry count mismatch; explicit directory entries not allowed' }
        foreach ($entry219 in $zip219.Entries) {
            $name219=$entry219.FullName
            $pin219=$pins219.PSObject.Properties[$name219]
            # Reject all special Unix types and Windows reparse attributes.
            $mode219=($entry219.ExternalAttributes -shr 16) -band 61440
            if ($null -eq $pin219 -or $seen219.ContainsKey($name219) -or
                $name219 -cne $pin219.Name -or $mode219 -notin @(0,32768) -or
                ($entry219.ExternalAttributes -band 1024) -or $entry219.Length -gt 134217728) { throw 'Unlisted/duplicate/special ZIP entry refused' }
            $expanded219+=$entry219.Length
            if ($expanded219 -gt 536870912) { throw 'Expanded ZIP byte bound exceeded' }
            $destination219=Join-Path $payload219 $name219.Replace('/','\')
            $directory219=[IO.Path]::GetDirectoryName($destination219)
            $null=[IO.Directory]::CreateDirectory($directory219)
            $source219=$entry219.Open()
            $target219=[IO.File]::Open($destination219,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
            try {
                $copied219=0
                while (($count219=$source219.Read($buffer219,0,$buffer219.Length)) -gt 0) {
                    $copied219+=$count219
                    if ($copied219 -gt $entry219.Length) { throw 'ZIP decompression length exceeded' }
                    $target219.Write($buffer219,0,$count219)
                }
                if ($copied219 -ne $entry219.Length) { throw 'ZIP decompression length mismatch' }
                $target219.Flush($true)
            } finally { $target219.Dispose(); $source219.Dispose() }
            Assert-Namespace219PinnedFile $destination219 $pin219.Value
            $seen219[$name219]=$true
        }
    } finally { $zip219.Dispose() }
    Write-Namespace219NewJson (Join-Path $StageDirectory 'staging.json') ([ordered]@{
        schema='imageinfo-0219-portable-staging-v1'; asset_uri=$AssetUri; archive_sha256=$ArchiveSha256
        entry_pins_sha256=$EntryPinsSha256; compressed_bytes=$total219; expanded_bytes=$expanded219
        entry_count=$seen219.Count; installer_used=$false; guestUtc=[DateTime]::UtcNow.ToString('o')
    })
    return $payload219
}

function Get-Namespace219PythonRuntime {
    param([string]$PythonPath,[string]$PythonSha256,[string]$ExpectedVersion,[string]$Destination)
    $null=Get-Namespace219GuestReadiness
    Assert-Namespace219LocalPath $Destination
    if ($ExpectedVersion -cnotmatch '^3\.[0-9]{1,2}\.[0-9]{1,3}$') { throw 'Exact Python release required' }
    Assert-Namespace219PinnedFile $PythonPath $PythonSha256
    $process219=New-Object Diagnostics.Process
    $process219.StartInfo=New-Object Diagnostics.ProcessStartInfo
    $process219.StartInfo.FileName=$PythonPath
    $process219.StartInfo.Arguments='-E -s -B -c "import sys; print(sys.version); print(sys.executable); print(sys.flags)"'
    $process219.StartInfo.UseShellExecute=$false
    $process219.StartInfo.CreateNoWindow=$true
    $process219.StartInfo.RedirectStandardOutput=$true
    $process219.StartInfo.RedirectStandardError=$true
    $started219=$false
    $record219=[ordered]@{schema='imageinfo-0219-python-runtime-v1'; pid=$null; exit_confirmed=$false
        exit_code=$null; executable_sha256=$PythonSha256; expected_version=$ExpectedVersion
        stdout=''; stderr=''; failed=$true; diagnostic=$null}
    try {
        if (-not $process219.Start()) { throw 'Pinned Python runtime probe failed to start' }
        $started219=$true
        $record219.pid=$process219.Id
        $out219=New-Object char[] 4097; $err219=New-Object char[] 4097
        $outTask219=$process219.StandardOutput.ReadAsync($out219,0,4097)
        $errTask219=$process219.StandardError.ReadAsync($err219,0,4097)
        if (-not $process219.WaitForExit(10000)) { throw 'Pinned Python runtime probe deadline exceeded' }
        if (-not $outTask219.Wait(1000) -or -not $errTask219.Wait(1000)) { throw 'Runtime probe pipe completion unconfirmed' }
        $outCount219=$outTask219.GetAwaiter().GetResult(); $errCount219=$errTask219.GetAwaiter().GetResult()
        $record219.stdout=New-Object string($out219,0,$outCount219)
        $record219.stderr=New-Object string($err219,0,$errCount219)
        if ($process219.ExitCode -ne 0 -or $outCount219 -gt 4096 -or $errCount219 -ne 0) { throw 'Runtime probe failed or output bound exceeded' }
        $text219=New-Object string($out219,0,$outCount219)
        if (-not $text219.StartsWith($ExpectedVersion+' ') -or $text219 -notmatch 'isolated=1') { throw 'Expected isolated portable Python release required' }
        $record219.failed=$false
    } catch {
        $record219.diagnostic=$_.Exception.Message
    } finally {
        # This exact bounded probe never starts a worker or a descendant.
        try {
            if ($started219 -and -not $process219.HasExited) {
                $process219.Kill()
                if (-not $process219.WaitForExit(5000)) { throw 'Runtime probe owned exit unconfirmed' }
            }
            if ($started219 -and $process219.HasExited) {
                $record219.exit_confirmed=$true; $record219.exit_code=$process219.ExitCode
            }
        } catch { $record219.failed=$true; $record219.cleanup_diagnostic=$_.Exception.Message }
        finally {
            Write-Namespace219NewJson $Destination $record219
            $process219.Dispose()
        }
    }
    return $record219
}

function Invoke-Namespace219GuestCollector {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$PythonPath,
        [Parameter(Mandatory=$true)][string]$PythonSha256,
        [Parameter(Mandatory=$true)][string]$ExpectedPythonVersion,
        [Parameter(Mandatory=$true)][string]$CollectorPath,
        [Parameter(Mandatory=$true)][string]$CollectorSha256,
        [Parameter(Mandatory=$true)][string]$RequestPath,
        [Parameter(Mandatory=$true)][string]$RequestSha256,
        [Parameter(Mandatory=$true)][string]$BootstrapPath,
        [Parameter(Mandatory=$true)][string]$BootstrapSha256,
        [string]$EventPath,
        [string]$CommandPath,
        [string]$Endpoint,
        [Parameter(Mandatory=$true)][string]$VolumePlanPath,
        [Parameter(Mandatory=$true)][string]$VolumePlanSha256,
        [Parameter(Mandatory=$true)][string]$DiagnosticPlanSha256,
        [Parameter(Mandatory=$true)][string]$CaptureDirectory,
        [Parameter(Mandatory=$true)][ValidateRange(30,1800)][int]$DeadlineSeconds,
        [ValidateRange(4096,1048576)][int]$CaptureCharacters=1048576,
        [Parameter(Mandatory=$true)][switch]$CurrentOwningParent
    )
    $ErrorActionPreference='Stop'
    if (-not $CurrentOwningParent) { throw 'Explicit current-parent invocation required' }
    $paths219=@($PythonPath,$CollectorPath,$RequestPath,$BootstrapPath,$CaptureDirectory,$VolumePlanPath)
    if ($Endpoint) {
        if ($EventPath -or $CommandPath -or $Endpoint -cnotmatch '^http://10\.0\.2\.2:([0-9]{4,5})/event/[A-Za-z0-9_-]{1,64}$') { throw 'Exact private HTTP endpoint required without mailboxes' }
        $endpointUri219=[Uri]$Endpoint
        if ($endpointUri219.Port -lt 1024 -or $endpointUri219.Port -gt 65535) { throw 'Invalid endpoint port' }
    } else {
        if (-not $EventPath -or -not $CommandPath) { throw 'Paired event/command mailbox paths required' }
        $paths219+=@($EventPath,$CommandPath)
    }
    foreach ($path219 in $paths219) {
        Assert-Namespace219LocalPath $path219
    }
    if ($BootstrapPath -ine $PSCommandPath) { throw 'Bootstrap pin must name this defining script' }
    if (@($paths219 | Sort-Object -Unique).Count -ne $paths219.Count) {
        throw 'All bootstrap paths must be distinct'
    }
    # Refuse host/elevated invocation before creating evidence or launching code.
    $readiness219 = Get-Namespace219GuestReadiness
    if (Test-Path -LiteralPath $CaptureDirectory) { throw 'Fresh capture directory required; retained evidence preserved' }
    $null = New-Item -ItemType Directory -Path $CaptureDirectory -ErrorAction Stop
    $result219 = [ordered]@{
        schema='imageinfo-0219-bootstrap-v1'; startedUtc=[DateTime]::UtcNow.ToString('o')
        readiness=$readiness219; collectorPid=$null; collectorExitConfirmed=$false
        collectorExitCode=$null; failed=$true; diagnostic=$null
        stdoutTruncated=$false; stderrTruncated=$false
        productionAdmission=$false; rawMutationAdmission=$false
    }
    $child219 = $null
    $stdout219 = New-Object Text.StringBuilder
    $stderr219 = New-Object Text.StringBuilder
    try {
        Assert-Namespace219PinnedFile $PythonPath $PythonSha256
        Assert-Namespace219PinnedFile $CollectorPath $CollectorSha256
        Assert-Namespace219PinnedFile $RequestPath $RequestSha256
        Assert-Namespace219PinnedFile $BootstrapPath $BootstrapSha256
        $requestData219=Read-Namespace219PinnedJson $RequestPath $RequestSha256
        Assert-Namespace219LocalPath $requestData219.volume_binding_path
        if ($DiagnosticPlanSha256 -cnotmatch '^[0-9a-f]{64}$' -or
            $requestData219.bindings.plan_sha256 -cne $DiagnosticPlanSha256 -or
            $requestData219.volume_plan_sha256 -cne $VolumePlanSha256) { throw 'Diagnostic/volume plan request bindings differ' }
        $volumeSelection219=Read-Namespace219PinnedJson $VolumePlanPath $VolumePlanSha256
        if (($volumeSelection219 | ConvertTo-Json -Depth 24 -Compress) -cne
            ($requestData219.volume_plan | ConvertTo-Json -Depth 24 -Compress)) { throw 'Actual volume selection differs from request' }
        $binding219=Get-Namespace219VolumeBinding $VolumePlanPath $VolumePlanSha256 $DiagnosticPlanSha256 $requestData219.volume_binding_path
        if ($binding219.root -cne $requestData219.fixture_root -or $binding219.unit -cne $requestData219.unit) { throw 'Actual volume binding differs from collector request' }
        $runtime219=Get-Namespace219PythonRuntime $PythonPath $PythonSha256 $ExpectedPythonVersion (Join-Path $CaptureDirectory 'runtime.json')
        if ($runtime219.failed) { throw 'Pinned portable runtime probe refused; see runtime.json' }
        # Collector creates event mailbox exclusively. Host creates the empty
        # command mailbox exclusively before invocation and is its sole writer.
        if (-not $Endpoint) {
            if (Test-Path -LiteralPath $EventPath) { throw 'Fresh event mailbox required' }
            $command219 = Get-Item -LiteralPath $CommandPath -Force
            if ($command219.PSIsContainer -or $command219.Length -ne 0 -or
                ($command219.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw 'Fresh empty ordinary command mailbox required'
            }
        }
        Write-Namespace219NewJson (Join-Path $CaptureDirectory 'start.json') ([ordered]@{
            schema='imageinfo-0219-bootstrap-start-v1'; readiness=$readiness219
            pythonSha256=$PythonSha256; collectorSha256=$CollectorSha256
            requestSha256=$RequestSha256; bootstrapSha256=$BootstrapSha256
            diagnosticPlanSha256=$DiagnosticPlanSha256; volumePlanSha256=$VolumePlanSha256
            deadlineSeconds=$DeadlineSeconds; captureCharacters=$CaptureCharacters
            caller='explicit-current-owning-parent'; guestUtc=[DateTime]::UtcNow.ToString('o')
        })
        $child219 = New-Object Diagnostics.Process
        $child219.StartInfo = New-Object Diagnostics.ProcessStartInfo
        $child219.StartInfo.FileName=$PythonPath
        # Paths cannot contain quotes/newlines and end in filenames, so these
        # quoted Windows arguments preserve spaces without shell interpretation.
        $transport219=if($Endpoint){' --endpoint "'+$Endpoint+'"'}else{' --event-file "'+$EventPath+'" --command-file "'+$CommandPath+'"'}
        $child219.StartInfo.Arguments='-E -s -B -u "'+$CollectorPath+'" --request "'+$RequestPath+'" --current-owning-parent'+$transport219
        $child219.StartInfo.WorkingDirectory=[IO.Path]::GetDirectoryName($CollectorPath)
        $child219.StartInfo.UseShellExecute=$false
        $child219.StartInfo.CreateNoWindow=$true
        $child219.StartInfo.RedirectStandardInput=$true
        $child219.StartInfo.RedirectStandardOutput=$true
        $child219.StartInfo.RedirectStandardError=$true
        $child219.StartInfo.EnvironmentVariables['PYTHONNOUSERSITE']='1'
        $child219.StartInfo.EnvironmentVariables['PYTHONDONTWRITEBYTECODE']='1'
        if (-not $child219.Start()) { throw 'Owned collector did not start' }
        $result219.collectorPid=$child219.Id
        $child219.StandardInput.Close()
        Write-Namespace219NewJson (Join-Path $CaptureDirectory 'pid.json') ([ordered]@{
            schema='imageinfo-0219-bootstrap-pid-v1'; collectorPid=$child219.Id
            guestUtc=[DateTime]::UtcNow.ToString('o')
        })
        $watch219 = [Diagnostics.Stopwatch]::StartNew()
        $outBuffer219 = New-Object char[] 4096
        $errBuffer219 = New-Object char[] 4096
        $outTask219=$child219.StandardOutput.ReadAsync($outBuffer219,0,4096)
        $errTask219=$child219.StandardError.ReadAsync($errBuffer219,0,4096)
        while ($true) {
            foreach ($channel219 in @('out','err')) {
                $task219=if($channel219 -eq 'out'){$outTask219}else{$errTask219}
                if ($null -ne $task219 -and $task219.IsCompleted) {
                    $count219=$task219.GetAwaiter().GetResult()
                    if ($count219 -eq 0) {
                        if($channel219 -eq 'out'){$outTask219=$null}else{$errTask219=$null}
                    } else {
                        $builder219=if($channel219 -eq 'out'){$stdout219}else{$stderr219}
                        $buffer219=if($channel219 -eq 'out'){$outBuffer219}else{$errBuffer219}
                        $keep219=[Math]::Min($count219,$CaptureCharacters-$builder219.Length)
                        if ($keep219 -gt 0) { $null=$builder219.Append($buffer219,0,$keep219) }
                        if ($keep219 -lt $count219) {
                            if($channel219 -eq 'out'){$result219.stdoutTruncated=$true}else{$result219.stderrTruncated=$true}
                        }
                        if($channel219 -eq 'out'){$outTask219=$child219.StandardOutput.ReadAsync($outBuffer219,0,4096)}
                        else{$errTask219=$child219.StandardError.ReadAsync($errBuffer219,0,4096)}
                    }
                }
            }
            if ($child219.HasExited -and $null -eq $outTask219 -and $null -eq $errTask219) { break }
            if ($watch219.Elapsed.TotalSeconds -gt $DeadlineSeconds) { throw 'Collector bootstrap deadline exceeded; exit remains unconfirmed' }
            Start-Sleep -Milliseconds 25
        }
        $result219.collectorExitConfirmed=$true
        $result219.collectorExitCode=$child219.ExitCode
        $result219.failed=($child219.ExitCode -ne 0 -or $result219.stdoutTruncated -or $result219.stderrTruncated)
        if ($result219.failed) { $result219.diagnostic='Collector failed or bootstrap capture exceeded bound' }
    } catch {
        $result219.diagnostic=$_.Exception.Message
        if ($null -ne $child219 -and $null -ne $result219.collectorPid) {
            try {
                if ($child219.HasExited) {
                    $result219.collectorExitConfirmed=$true
                    $result219.collectorExitCode=$child219.ExitCode
                }
            } catch { $result219.exitCheckDiagnostic=$_.Exception.Message }
        }
    } finally {
        # Never kill the collector: it owns worker cleanup. An unconfirmed exit
        # is retained as uncertainty, with no postexit probe or replay here.
        $encoding219=New-Object Text.UTF8Encoding($false)
        foreach ($capture219 in @(@('stdout.txt',$stdout219),@('stderr.txt',$stderr219))) {
            $file219=[IO.File]::Open((Join-Path $CaptureDirectory $capture219[0]),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
            try { $bytes219=$encoding219.GetBytes($capture219[1].ToString()); $file219.Write($bytes219,0,$bytes219.Length); $file219.Flush($true) }
            finally { $file219.Dispose() }
        }
        $result219.finishedUtc=[DateTime]::UtcNow.ToString('o')
        Write-Namespace219NewJson (Join-Path $CaptureDirectory 'result.json') $result219
        if ($null -ne $child219) { $child219.Dispose() }
    }
    return [pscustomobject]$result219
}

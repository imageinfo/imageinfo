# Qualification worker for authored marker bytes only; never a media writer.
param(
    [Parameter(Mandatory=$true)][string]$Root,
    [ValidateSet('strict','delete-share')][string]$Sharing = 'strict'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$events = [System.Collections.Generic.List[string]]::new()
$stage = $null
$attempted = $false
$published = $false
$exitCode = 5

function Emit($value) {
    [Console]::Out.WriteLine(($value | ConvertTo-Json -Compress -Depth 8))
    [Console]::Out.Flush()
}
function Barrier([string]$name) {
    $events.Add($name)
    $event = @{barrier=$name; productionPublicationAllowed=$false}
    if ($name -eq 'private-root-created') {
        $event.runtime = @{powershell=$PSVersionTable.PSVersion.ToString(); edition=$PSVersionTable.PSEdition;
            clr=[Environment]::Version.ToString(); os=[Environment]::OSVersion.Version.ToString();
            frameworkFileVersion=[Diagnostics.FileVersionInfo]::GetVersionInfo([object].Assembly.Location).FileVersion;
            filesystem=$script:drive.DriveFormat; driveType=$script:drive.DriveType.ToString()}
    }
    Emit $event
    $command = [Console]::In.ReadLine()
    if ($command -eq 'cancel') { throw 'CONTROL_CANCEL' }
    if ($command -eq 'fail') { throw 'CONTROL_FAILURE' }
    if ($command -ne 'continue') { throw 'CONTROL_INVALID' }
}
function Private-Security([bool]$directory) {
    if ($directory) { $security = [System.Security.AccessControl.DirectorySecurity]::new() }
    else { $security = [System.Security.AccessControl.FileSecurity]::new() }
    $security.SetOwner($script:sid)
    $security.SetAccessRuleProtection($true, $false)
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $script:sid, [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow)
    $security.AddAccessRule($rule)
    return $security
}
function Check-Private([string]$path, [bool]$directory) {
    $attributes = [System.IO.File]::GetAttributes($path)
    # Broader streams, compressed/encrypted/sparse/offline/reparse objects need
    # separate evidence. This marker profile deliberately admits ordinary files.
    $allowed = if ($directory) { 16 } else { 32 -bor 128 }
    if (([int]$attributes -band (-bnot $allowed)) -ne 0) { throw 'PROPERTY_ATTRIBUTES' }
    $sections = [System.Security.AccessControl.AccessControlSections]::Owner -bor
        [System.Security.AccessControl.AccessControlSections]::Access
    if ($directory) { $security = [System.IO.Directory]::GetAccessControl($path, $sections) }
    else { $security = [System.IO.File]::GetAccessControl($path, $sections) }
    $rules = $security.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])
    if ($security.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $script:sid.Value -or
        -not $security.AreAccessRulesProtected -or $rules.Count -ne 1) { throw 'PROPERTY_ACL' }
    $rule = $rules[0]
    if ($rule.IdentityReference.Value -ne $script:sid.Value -or $rule.IsInherited -or
        $rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
        $rule.FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl -or
        $rule.InheritanceFlags -ne [System.Security.AccessControl.InheritanceFlags]::None -or
        $rule.PropagationFlags -ne [System.Security.AccessControl.PropagationFlags]::None) { throw 'PROPERTY_ACL' }
    if (-not $directory) {
        $streams = @(Get-Item -LiteralPath $path -Stream * -ErrorAction Stop)
        if ($streams.Count -ne 1 -or $streams[0].Stream -ne ':$DATA') { throw 'PROPERTY_STREAMS' }
    }
}
function New-PrivateFile([string]$path, [System.IO.FileShare]$share) {
    $rights = [System.Security.AccessControl.FileSystemRights]::Read -bor
        [System.Security.AccessControl.FileSystemRights]::Write
    # Security is supplied to CreateNew, not applied after sensitive bytes exist.
    return [System.IO.FileStream]::new($path, [System.IO.FileMode]::CreateNew,
        $rights, $share, 4096, [System.IO.FileOptions]::None, (Private-Security $false))
}
function Write-Record([string]$name, [string]$phase) {
    $record = New-PrivateFile (Join-Path $Root $name) ([System.IO.FileShare]::Read)
    try {
        $body = @{purpose='imageinfo-windows-property-research-v1'; phase=$phase;
            observationOnly=$true; namespaceAcknowledged=$false; committed=$false} | ConvertTo-Json -Compress
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $record.Write($bytes, 0, $bytes.Length)
        $record.Flush($true)
        Check-Private (Join-Path $Root $name) $false
    } finally { $record.Dispose() }
}
function Held-Hash {
    $stage.Position = 0
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($stage))).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}
function Installed-Hash([string]$path) {
    # Read the installed object too: hashing only the still-held original stage
    # cannot verify a pathname publication. This is a bounded post-check, not an
    # exclusion mechanism or proof that the checked pathname stays bound.
    $reader = [System.IO.FileStream]::new($path, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [byte[]]::new(65537)
        $count = 0
        while ($count -lt $bytes.Length) {
            $read = $reader.Read($bytes, $count, $bytes.Length-$count)
            if ($read -eq 0) { break }
            $count += $read
        }
        if ($count -ne 65536) { throw 'INSTALLED_CONTENT_DRIFT' }
        return ([BitConverter]::ToString($algorithm.ComputeHash($bytes, 0, $count))).Replace('-', '').ToLowerInvariant()
    } finally { $algorithm.Dispose(); $reader.Dispose() }
}
function Check-Candidate([string]$path, [bool]$installed = $false) {
    Check-Private $Root $true
    Check-Private $path $false
    if ([System.IO.File]::GetLastWriteTimeUtc($path) -ne $script:lastWriteTime -or
        [System.IO.File]::GetCreationTimeUtc($path) -ne $script:creationTime -or
        $stage.Length -ne 65536 -or (Held-Hash) -ne $script:expectedHash) { throw 'PROPERTY_OR_CONTENT_DRIFT' }
    if ($installed -and (Installed-Hash $path) -ne $script:expectedHash) { throw 'INSTALLED_CONTENT_DRIFT' }
}

try {
    if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5) {
        throw 'RUNTIME_UNVERIFIED'
    }
    # Do not normalize untrusted relative/device/stream operands into this profile.
    if ($Root -notmatch '^[A-Za-z]:\\' -or $Root.Length -gt 220 -or
        $Root.Substring(2).Contains(':') -or $Root -match '\\[.]{1,2}(\\|$)') { throw 'PATH_UNVERIFIED' }
    $Root = [System.IO.Path]::GetFullPath($Root)
    if ([System.IO.Directory]::Exists($Root) -or [System.IO.File]::Exists($Root)) { throw 'ROOT_EXISTS' }
    $parent = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetDirectoryName($Root))
    if (-not $parent.Exists) { throw 'PARENT_MISSING' }
    $ancestor = $parent
    while ($null -ne $ancestor) {
        if (([int]$ancestor.Attributes -band 1024) -ne 0) { throw 'REPARSE_ANCESTOR' }
        $ancestor = $ancestor.Parent
    }
    $drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($Root))
    if ($drive.DriveType -ne [System.IO.DriveType]::Fixed -or $drive.DriveFormat -ne 'NTFS') {
        throw 'STORAGE_UNVERIFIED'
    }
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    # Create(DirectorySecurity) applies the ACL at creation, but is not exclusive
    # if another actor wins directory creation. A pathname check is not a guard.
    [System.IO.DirectoryInfo]::new($Root).Create((Private-Security $true))
    Check-Private $Root $true
    Write-Record 'parent-anchor.record' 'guard-anchor'
    Barrier 'private-root-created'
    $share = [System.IO.FileShare]::Read
    if ($Sharing -eq 'delete-share') { $share = $share -bor [System.IO.FileShare]::Delete }
    $candidate = Join-Path $Root 'candidate.bin'
    $output = Join-Path $Root 'output.bin'
    $stage = New-PrivateFile $candidate $share
    $bytes = [byte[]]::new(65536)
    for ($i=0; $i -lt $bytes.Length; $i++) { $bytes[$i] = 48 }
    $stage.Write($bytes, 0, $bytes.Length)
    $stage.Flush($true)
    $creationTime = [System.IO.File]::GetCreationTimeUtc($candidate)
    $lastWriteTime = [System.IO.File]::GetLastWriteTimeUtc($candidate)
    $expectedHash = Held-Hash
    Check-Candidate $candidate
    Barrier 'candidate-flushed'
    Write-Record 'prepared.record' 'prepared'
    Barrier 'prepared-record-flushed'
    Write-Record 'intent.record' 'publication-intent'
    Barrier 'intent-record-flushed'
    Check-Candidate $candidate
    Barrier 'before-publish'
    Check-Candidate $candidate
    Barrier 'validated-before-publish'
    $attempted = $true
    # Strict sharing refuses even our own pathname-based move. Allowing Delete
    # makes this move possible but also permits other namespace actors. This is
    # a counterexample comparison, never a fallback from a failed strict profile.
    [System.IO.File]::Move($candidate, $output)
    $published = $true
    Barrier 'published'
    Check-Candidate $output $true
    $stage.Flush($true)
    Barrier 'output-file-flushed'
    # There is no demonstrated directory/namespace persistence acknowledgement
    # in this managed sequence. Do not fabricate one from Flush(true) on a file.
    Write-Record 'observation.record' 'recovery-required'
    Barrier 'observation-record-flushed'
    Check-Candidate $output $true
    Emit @{outcome='recovery-required'; namespaceAcknowledged=$false; committed=$false;
        publicationAttempted=$attempted; publicationObserved=$published; profileVerified=$false;
        productionPublicationAllowed=$false; events=@($events); diagnostic='NAMESPACE_ACK_UNVERIFIED'}
} catch {
    $base = $_.Exception.GetBaseException()
    $diagnostic = $base.Message
    if ($diagnostic -notmatch '^[A-Z_]{1,64}$') { $diagnostic = 'OS_OR_PROPERTY_FAILURE' }
    if ($diagnostic -eq 'CONTROL_CANCEL' -and -not $attempted) { $exitCode = 130 }
    Emit @{outcome=$(if ($attempted) {'recovery-required'} else {'failed-before-publish'});
        diagnostic=$diagnostic; errorType=$base.GetType().Name; hresultLowWord=($base.HResult -band 65535);
        errorLine=$_.InvocationInfo.ScriptLineNumber;
        publicationAttempted=$attempted; publicationObserved=$published; committed=$false;
        namespaceAcknowledged=$false; profileVerified=$false; productionPublicationAllowed=$false;
        events=@($events)}
} finally {
    if ($null -ne $stage) { $stage.Dispose() }
}
exit $exitCode

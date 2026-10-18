param([string]$AppPath)
# Read-only installation inspection. No auth.json, config.toml, cookies or network.
$ErrorActionPreference = 'Stop'
$candidates = New-Object 'System.Collections.Generic.List[string]'
$packages = @()
$issues = New-Object 'System.Collections.Generic.List[string]'

function Safe-Path([string]$Value) {
    if ($env:USERPROFILE) { return $Value.Replace($env:USERPROFILE, '%USERPROFILE%') }
    return $Value
}
function Add-Executable([string]$Path) {
    if ($Path -and (Test-Path -LiteralPath $Path -PathType Leaf)) {
        if (-not $candidates.Contains($Path)) { $candidates.Add($Path) }
    }
}
function Read-Exact($Stream, [int]$Count) {
    $buffer = New-Object byte[] $Count
    $offset = 0
    while ($offset -lt $Count) {
        $n = $Stream.Read($buffer, $offset, $Count - $offset)
        if ($n -le 0) { throw 'Unexpected end of application archive.' }
        $offset += $n
    }
    return ,$buffer
}
function Inspect-Archive([string]$Path) {
    $stream = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
    try {
        $prefix = Read-Exact $stream 16
        $headerSize = [BitConverter]::ToUInt32($prefix, 4)
        $jsonSize = [BitConverter]::ToUInt32($prefix, 12)
        if ($jsonSize -gt 33554432 -or $jsonSize -lt 2 -or $headerSize -lt ($jsonSize + 8)) {
            throw 'Unsupported application archive header.'
        }
        $header = [Text.Encoding]::UTF8.GetString((Read-Exact $stream $jsonSize)) | ConvertFrom-Json
        $assets = $header.files.webview.files.assets.files
        $markers = @()
        if ($assets) {
            foreach ($item in $assets.PSObject.Properties) {
                if ($item.Name -notmatch '^profile-dropdown.*\.js$') { continue }
                $entry = $item.Value
                if ($entry.unpacked -or $entry.size -gt 4194304 -or $null -eq $entry.offset) { continue }
                $position = 8L + $headerSize + [long]$entry.offset
                if ($position -lt 16 -or ($position + $entry.size) -gt $stream.Length) { throw 'Invalid archive entry.' }
                $stream.Position = $position
                $bytes = Read-Exact $stream ([int]$entry.size)
                $code = [Text.Encoding]::UTF8.GetString($bytes)
                $sha = [Security.Cryptography.SHA256]::Create()
                try { $hash = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
                finally { $sha.Dispose() }
                $markers += [ordered]@{
                    file = $item.Name; sha256 = $hash
                    usageLabel = $code.Contains('profileDropdown.usage')
                    providerNameBranch = $code.Contains('modelProviderName')
                    chatgptAuthBranch = $code.Contains('chatgpt')
                    ambientUsage = $code.Contains('ambientUsage')
                    archiveIntegrityMetadata = ($null -ne $entry.integrity)
                }
            }
        }
        return [ordered]@{
            path = Safe-Path $Path
            sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
            profileBundles = @($markers)
        }
    } finally { $stream.Dispose() }
}

if ($AppPath) { Add-Executable $AppPath }
foreach ($process in @(Get-Process -Name Codex,ChatGPT -ErrorAction SilentlyContinue)) {
    try { Add-Executable $process.Path } catch { $issues.Add('A running app path was not readable.') }
}
if (Get-Command Get-AppxPackage -ErrorAction SilentlyContinue) {
    try {
        foreach ($package in @(Get-AppxPackage | Where-Object { $_.Name -match 'Codex|ChatGPT' })) {
            $packages += [ordered]@{name=$package.Name; version=$package.Version.ToString(); publisher=$package.Publisher; architecture=$package.Architecture.ToString()}
            foreach ($relative in @('app\Codex.exe','app\ChatGPT.exe','Codex.exe','ChatGPT.exe')) {
                Add-Executable (Join-Path $package.InstallLocation $relative)
            }
        }
    } catch { $issues.Add('Store package metadata was not readable.') }
}
foreach ($root in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
    if (-not $root) { continue }
    foreach ($relative in @('Programs\Codex\Codex.exe','Programs\ChatGPT\ChatGPT.exe','Codex\Codex.exe','ChatGPT\ChatGPT.exe','OpenAI\Codex\Codex.exe','OpenAI\ChatGPT\ChatGPT.exe')) {
        Add-Executable (Join-Path $root $relative)
    }
}
$apps = @()
foreach ($candidate in $candidates) {
    try {
        $file = Get-Item -LiteralPath $candidate
        $signature = Get-AuthenticodeSignature -LiteralPath $candidate
        $archive = Join-Path $file.DirectoryName 'resources\app.asar'
        $archiveInfo = $null
        if (Test-Path -LiteralPath $archive -PathType Leaf) {
            try { $archiveInfo = Inspect-Archive $archive }
            catch { $issues.Add('An application archive could not be inspected. No files were changed.') }
        }
        $apps += [ordered]@{
            path = Safe-Path $candidate
            productVersion = $file.VersionInfo.ProductVersion
            fileVersion = $file.VersionInfo.FileVersion
            signatureStatus = $signature.Status.ToString()
            signer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
            archive = $archiveInfo
        }
    } catch { $issues.Add('An executable could not be inspected. No files were changed.') }
}
if ($apps.Count -eq 0) { $issues.Add('No desktop app was found. Open Codex and run this check again, or supply -AppPath with its executable path.') }
$report = [ordered]@{
    schema = 1; inspectedAtUtc = [DateTime]::UtcNow.ToString('o')
    purpose = 'Read-only native usage menu compatibility check; not a patch or a compatibility verdict.'
    powershellVersion = $PSVersionTable.PSVersion.ToString()
    storePackages = @($packages); applications = @($apps); issues = $issues.ToArray()
}
$output = Join-Path $PSScriptRoot 'TokenBots-native-menu-report.json'
[IO.File]::WriteAllText($output, ($report | ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false)))
Write-Host 'Done. No app, account, or configuration was modified.'
Write-Host 'Send TokenBots-native-menu-report.json back to us. It contains installation metadata only.'
Write-Host ('Report: ' + $output)

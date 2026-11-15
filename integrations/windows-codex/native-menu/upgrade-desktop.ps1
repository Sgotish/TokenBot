param([Parameter(Mandatory=$true)][string]$AppDirectory, [Parameter(Mandatory=$true)][string]$Descriptor)
$ErrorActionPreference = 'Stop'
$old = (Resolve-Path -LiteralPath $AppDirectory).Path
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
if (-not $old.StartsWith(([IO.Path]::GetFullPath($base) + '\'),[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path (Join-Path $old '.tokenbots-custom-copy'))) { throw 'Unknown desktop installation.' }
if (@(Get-Process ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $old 'ChatGPT.exe') }).Count) { throw 'Completely exit TokenBots Codex before updating.' }
if ($env:TOKENBOTS_OTA_PROTOCOL -ne '2') { throw 'The updater was upgraded. Restart once more to update the desktop.' }
$release = Get-Content -Raw -LiteralPath $Descriptor | ConvertFrom-Json
if ([string]$release.version -ne $env:TOKENBOTS_OTA_VERSION) { throw 'Desktop release does not match signed update.' }
$architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$arch = if ($architecture -eq 'AMD64') {'x64'} elseif ($architecture -eq 'ARM64') {'arm64'} else {throw 'Unsupported architecture.'}
$entry = $release.architectures.$arch
if (-not $entry) { throw 'No reviewed desktop is available for this architecture.' }
$ini = [IO.File]::ReadAllText((Join-Path $old 'resources\owl-app.ini'))
if ($ini -match ('(?m)^AppVersion=' + [regex]::Escape($entry.applicationVersion) + '\r?$')) { Write-Output $old; return }
$archive = Join-Path $old ('tokenbots-ota\assets\' + $entry.sha256 + '.msix')
if (-not (Test-Path -LiteralPath $archive)) { throw 'Desktop package is downloading. Current application is preserved.' }
if ((Get-Item -LiteralPath $archive).Length -ne $entry.size -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw 'Desktop package hash mismatch.' }
if ((Get-AuthenticodeSignature -LiteralPath $archive).Status -ne 'Valid') { throw 'Desktop package signature is not trusted.' }
$destination = Join-Path $base ('c-' + $entry.applicationVersion + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $destination | Out-Null
try {
    & tar.exe -xf $archive -C $destination
    if ($LASTEXITCODE -ne 0) { throw 'Desktop extraction failed.' }
    [xml]$manifest = Get-Content -Raw -LiteralPath (Join-Path $destination 'AppxManifest.xml')
    $identity = $manifest.Package.Identity
    if ($identity.Name -ne 'OpenAI.Codex' -or $identity.ProcessorArchitecture -ne $arch -or $identity.Version -ne $entry.packageVersion -or $identity.Publisher -ne 'CN=50BDFD77-8903-4850-9FFE-6E8522F64D5B') { throw 'Unexpected desktop package identity.' }
    $app = Join-Path $destination 'app'
    New-Item -ItemType File -Path (Join-Path $app '.tokenbots-custom-copy') | Out-Null
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'patch-copy.ps1') -AppDirectory $app
    if ($LASTEXITCODE -ne 0) { throw 'Reviewed desktop adapter failed.' }
    Copy-Item -LiteralPath (Join-Path $old 'resources\tokenbots-native.json') -Destination (Join-Path $app 'resources\tokenbots-native.json')
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe (Join-Path $app 'resources\tokenbots-native.json') /inheritance:r /grant:r "${user}:(F)" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect connection configuration.' }
    Copy-Item -LiteralPath (Join-Path $old 'launch-tokenbots.ps1') -Destination $app
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'ota-client.cjs') -Destination $app
    # Profiles, project history, external-service authorizations and user skills
    # stay in the existing home. No other profile or credentials are imported.
    Write-Output $app
} catch {
    Remove-Item -LiteralPath $destination -Recurse -Force -ErrorAction SilentlyContinue
    throw
}

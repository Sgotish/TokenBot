param([string]$ArchivePath, [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
if ($architecture -eq 'AMD64') {
    $targetArch = 'x64'
    $releaseHash = 'ace6a186a30c7b8a399c8498ee33238f2e30a54f9e12665ad7998a9f9d20f5b0'
} elseif ($architecture -eq 'ARM64') {
    $targetArch = 'arm64'
    $releaseHash = 'bff7e61e8e7b5cf3b6a85d9cd60933160625162f1c148672bd93bb467fbd0888'
} else { throw 'This build requires Windows x64 or ARM64. No installed app was changed.' }
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
New-Item -ItemType Directory -Force -Path $base | Out-Null
$download = Join-Path $base ('ChatGPT-latest-' + $targetArch + '.msix')
if (-not $ArchivePath) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    # The vendor's latest URL changes independently of the reviewed adapter.
    # Retain the byte-identical signed x64 artifact for repeatable clean installs.
    $url = if ($targetArch -eq 'x64') { 'https://pilot.tokenbots.top/downloads/ChatGPT-x64-ace6a186a30c7b8a.msix' } else { 'https://persistent.oaistatic.com/codex-app-prod/ChatGPT-arm64.msix' }
    if ((Test-Path -LiteralPath $download) -and (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant() -eq $releaseHash) {
        Write-Host 'Using cached official desktop package.'
    } else {
        Write-Host 'Downloading official desktop package (about 1 GB)...'
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            & curl.exe --fail --location --silent --show-error --retry 2 --max-time 900 $url -o $download
            if ($LASTEXITCODE -ne 0) { throw 'Official package download failed.' }
        } else { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $download }
    }
    $ArchivePath = $download
}
if ((Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $releaseHash) {
    throw 'Official release has changed. Stop here for a new adapter; existing apps are unchanged.'
}
$signature = Get-AuthenticodeSignature -LiteralPath $ArchivePath
if ($signature.Status -ne 'Valid') { throw 'Official package signature validation failed. No installed app was changed.' }
$destination = Join-Path $base ('c-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) { throw 'Windows tar.exe is required to extract this release.' }
New-Item -ItemType Directory -Path $destination | Out-Null
& tar.exe -xf (Resolve-Path -LiteralPath $ArchivePath).Path -C $destination
if ($LASTEXITCODE -ne 0) { throw 'Official package extraction failed.' }
Write-Host 'Official package extracted.'
$appDir = Join-Path $destination 'app'
New-Item -ItemType File -Path (Join-Path $appDir '.tokenbots-custom-copy') | Out-Null
& (Join-Path $PSScriptRoot 'patch-copy.ps1') -AppDirectory $appDir
if ($PrepareOnly) { Write-Output $appDir; return }
$access = Join-Path $PSScriptRoot 'native-access.json'
if (-not (Test-Path -LiteralPath $access)) { throw 'Private native-access.json is missing. Original app unchanged.' }
$config = [IO.File]::ReadAllText($access) | ConvertFrom-Json
if ($config.testOnlyLocalOrigin -or $config.origin -notmatch '^https://[^/]+/?$' -or -not $config.key) { throw 'Invalid private access configuration.' }
$configTarget = Join-Path $appDir 'resources\tokenbots-native.json'
Copy-Item -LiteralPath $access -Destination $configTarget
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $configTarget /inheritance:r /grant:r "${identity}:(F)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect local access configuration.' }
# Each private key has its own native home and Electron data directory. Do not
# inherit CODEX_HOME, active profiles, auth, or an existing app's single instance.
$hasher = [Security.Cryptography.SHA256]::Create()
$homeId = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($config.key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
$nativeHome = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $homeId)
New-Item -ItemType Directory -Force -Path $nativeHome | Out-Null
# Protect the directory before creating files, so files inherit a usable ACL.
# Applying directory-only OI/CI grants recursively can leave file ACLs empty.
& icacls.exe $nativeHome /inheritance:r /grant:r "${identity}:(OI)(CI)(F)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect dedicated native configuration.' }
$previousHome = $env:CODEX_HOME
try {
    $env:CODEX_HOME = $nativeHome
    & (Join-Path (Split-Path $PSScriptRoot -Parent) 'setup.ps1')
} finally { $env:CODEX_HOME = $previousHome }
if (-not (Test-Path -LiteralPath (Join-Path $nativeHome 'config.toml'))) { throw 'Dedicated configuration was not created.' }
$null = [IO.File]::ReadAllText((Join-Path $nativeHome 'config.toml'))
$escapedHome = $nativeHome.Replace("'", "''")
$launch = @"
`$ErrorActionPreference = 'Stop'
`$env:CODEX_HOME = '$escapedHome'
Start-Process -FilePath (Join-Path `$PSScriptRoot 'ChatGPT.exe') -WorkingDirectory `$PSScriptRoot -ArgumentList ('--user-data-dir="' + (Join-Path `$env:CODEX_HOME 'desktop-data') + '"')
"@
$launchPath = Join-Path $appDir 'launch-tokenbots.ps1'
[IO.File]::WriteAllText($launchPath, $launch, (New-Object Text.UTF8Encoding($true)))
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'TokenBots Codex.lnk'))
$shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launchPath + '"'
$shortcut.IconLocation = Join-Path $appDir 'ChatGPT.exe'
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = 'TokenBots custom copy with pool usage menu. Official app remains installed.'
$shortcut.Save()
[IO.File]::WriteAllText((Join-Path $base 'current-copy.txt'), $appDir)
Write-Host 'Ready: fully exit the official desktop app, then open TokenBots Codex on your Desktop.'
Write-Host 'Rollback: close TokenBots Codex and open your original official app.'
Write-Host ('Dedicated configuration: ' + $nativeHome)

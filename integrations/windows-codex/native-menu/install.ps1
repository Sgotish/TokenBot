param([string]$ArchivePath, [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
if ($architecture -eq 'AMD64') {
    $targetArch = 'x64'
    $releaseHash = 'e2d892e6c22310e4b1a2928b0d3a29a066e0863d3a333754d6585c77cdafbe7f'
} elseif ($architecture -eq 'ARM64') {
    $targetArch = 'arm64'
    $releaseHash = 'bff7e61e8e7b5cf3b6a85d9cd60933160625162f1c148672bd93bb467fbd0888'
} else { throw 'This build requires Windows x64 or ARM64. No installed app was changed.' }
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
New-Item -ItemType Directory -Force -Path $base | Out-Null
$download = Join-Path $base ('ChatGPT-latest-' + $targetArch + '.msix')
if (-not $ArchivePath) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = 'https://persistent.oaistatic.com/codex-app-prod/ChatGPT-' + $targetArch + '.msix'
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
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'TokenBots Codex.lnk'))
$shortcut.TargetPath = Join-Path $appDir 'ChatGPT.exe'
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = 'TokenBots custom copy with pool usage menu. Official app remains installed.'
$shortcut.Save()
[IO.File]::WriteAllText((Join-Path $base 'current-copy.txt'), $appDir)
Write-Host 'Ready: fully exit the official desktop app, then open TokenBots Codex on your Desktop.'
Write-Host 'Rollback: close TokenBots Codex and open your original official app.'

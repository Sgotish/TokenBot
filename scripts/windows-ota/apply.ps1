param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
# Upgrade transport first, preserving v1 startup on a missing background asset.
$updater = Join-Path $AppDirectory 'ota-client.cjs'
$updaterTemp = $updater + '.new-' + [guid]::NewGuid().ToString('N')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'ota-client.cjs') -Destination $updaterTemp
if (Test-Path -LiteralPath $updater) { [IO.File]::Replace($updaterTemp,$updater,$updater+'.previous') }
else { Move-Item -LiteralPath $updaterTemp -Destination $updater }
$sourceApp = $AppDirectory
$descriptor = Join-Path $PSScriptRoot 'desktop-release.json'
if (Test-Path -LiteralPath $descriptor) {
    & (Join-Path $PSScriptRoot 'enable-ota.ps1') -AppDirectory $AppDirectory
}
$asset = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'browser-asset.json') | ConvertFrom-Json
$cache = Join-Path $AppDirectory ('tokenbots-ota\assets\' + $asset.sha256 + '.zip')
if (-not (Test-Path -LiteralPath $cache)) { throw 'Browser update is downloading in the background. Original client remains usable.' }
if ((Get-Item -LiteralPath $cache).Length -ne $asset.size -or (Get-FileHash -LiteralPath $cache -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.sha256) { throw 'Browser update hash mismatch. No feature configuration changed.' }
$unpacked = Join-Path $PSScriptRoot 'browser-runtime'
Expand-Archive -LiteralPath $cache -DestinationPath $unpacked -Force
$access = [IO.File]::ReadAllText((Join-Path $AppDirectory 'resources\tokenbots-native.json')) | ConvertFrom-Json
$id = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($access.key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
$profile = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $id)
$config = Join-Path $profile 'config.toml'
$backup = Join-Path $profile ('ota-rollback-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup | Out-Null
$paths = @($config, (Join-Path $AppDirectory 'resources\tokenbots-images.cjs'), (Join-Path $profile 'skills\tokenbots-browser-check'), (Join-Path $profile 'skills\tokenbots-project-checkpoints'), (Join-Path $AppDirectory 'launch-tokenbots.ps1'), (Join-Path $AppDirectory 'history-repair.cjs'))
$existed = @()
for ($i=0; $i -lt $paths.Count; $i++) {
    $existed += (Test-Path -LiteralPath $paths[$i])
    if ($existed[$i]) { Copy-Item -LiteralPath $paths[$i] -Destination (Join-Path $backup "$i") -Recurse }
}
try {
    if (Test-Path -LiteralPath $descriptor) {
        $result = @(& (Join-Path $PSScriptRoot 'upgrade-desktop.ps1') -AppDirectory $sourceApp -Descriptor $descriptor)
        $AppDirectory = $result[-1]
    }
    & (Join-Path $unpacked 'enable-browser.ps1') -AppDirectory $AppDirectory
    & (Join-Path $PSScriptRoot 'enable-images.ps1') -AppDirectory $AppDirectory
    & (Join-Path $PSScriptRoot 'enable-history-repair.ps1') -AppDirectory $AppDirectory
    if ($AppDirectory -eq $sourceApp) { & (Join-Path $PSScriptRoot 'update-native.ps1') -AppDirectory $AppDirectory }
    if ($AppDirectory -ne $sourceApp) {
        $release = Get-Content -Raw -LiteralPath $descriptor | ConvertFrom-Json
        $pointer = Join-Path (Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native') 'current-copy.txt'
        $next = Join-Path $sourceApp 'tokenbots-next-app.json'
        [IO.File]::WriteAllText($next,(@{version=$release.version;app=$AppDirectory} | ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)))
        $temp = $pointer + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
        [IO.File]::WriteAllText($temp,$AppDirectory,(New-Object Text.UTF8Encoding($false)))
        [IO.File]::Replace($temp,$pointer,$pointer+'.before-'+$release.version)
    }
} catch {
    for ($i=0; $i -lt $paths.Count; $i++) {
        if (Test-Path -LiteralPath $paths[$i]) { Remove-Item -LiteralPath $paths[$i] -Recurse -Force }
        if ($existed[$i]) { Copy-Item -LiteralPath (Join-Path $backup "$i") -Destination $paths[$i] -Recurse }
    }
    if ($AppDirectory -ne $sourceApp) {
        Remove-Item -LiteralPath (Join-Path $sourceApp 'tokenbots-next-app.json') -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Split-Path $AppDirectory -Parent) -Recurse -Force -ErrorAction SilentlyContinue
    }
    throw
}
# Backup remains in the private profile for deliberate rollback, never uploaded.
# A cold-launch updater is executing the previously loaded launcher text. Run
# recovery now as well, so the first restart after this upgrade is covered.
if ($env:CODEX_HOME -and [IO.Path]::GetFullPath($env:CODEX_HOME).Equals([IO.Path]::GetFullPath($profile),[StringComparison]::OrdinalIgnoreCase)) {
    try {
        $node = Join-Path $AppDirectory 'resources\cua_node\bin\node.exe'
        $repair = Join-Path $AppDirectory 'history-repair.cjs'
        $null = Start-Process -FilePath $node -ArgumentList ('"'+$repair+'" "'+$AppDirectory+'"') -WindowStyle Hidden -Wait -PassThru
    } catch { }
}

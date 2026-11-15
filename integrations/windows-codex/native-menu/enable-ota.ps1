param([string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
if (-not $AppDirectory) { $AppDirectory = [IO.File]::ReadAllText((Join-Path $base 'current-copy.txt')).Trim() }
$app = (Resolve-Path -LiteralPath $AppDirectory).Path
if (-not $app.StartsWith(([IO.Path]::GetFullPath($base) + '\'),[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath (Join-Path $app '.tokenbots-custom-copy'))) { throw 'Unknown TokenBots app copy.' }
$node = Join-Path $app 'resources\cua_node\bin\node.exe'
$launcher = Join-Path $app 'launch-tokenbots.ps1'
$text = [IO.File]::ReadAllText($launcher)
if ($text -notmatch '(?m)^Start-Process -FilePath ') { throw 'Unsupported TokenBots launcher.' }
$updater = Join-Path $app 'ota-client.cjs'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'ota-client.cjs') -Destination $updater -Force
$seed = Join-Path $PSScriptRoot 'ota-seed.json'
if (Test-Path -LiteralPath $seed) {
    & $node $updater stage $app $seed
    if ($LASTEXITCODE -ne 0) { throw 'Bundled update did not pass verification.' }
}
if (-not $text.Contains('# TokenBots OTA v1')) {
    $hook = @'
# TokenBots OTA v1
try {
    $node = Join-Path $PSScriptRoot 'resources\cua_node\bin\node.exe'
    $updater = Join-Path $PSScriptRoot 'ota-client.cjs'
    $lock = $null
    try {
        $lock = [IO.File]::Open((Join-Path $PSScriptRoot 'ota-launch.lock'),'OpenOrCreate','ReadWrite','None')
        $exe = Join-Path $PSScriptRoot 'ChatGPT.exe'
        $running = Get-Process -Name ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }
        if (-not $running) { & $node $updater apply $PSScriptRoot }
        Start-Process -FilePath $node -ArgumentList ('"' + $updater + '" fetch "' + $PSScriptRoot + '"') -WindowStyle Hidden
    } finally { if ($lock) { $lock.Dispose() } }
} catch { }
'@
    $at = [regex]::Match($text,'(?m)^Start-Process -FilePath ').Index
    $text = $text.Insert($at,$hook + "`r`n")
    $temp = $launcher + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temp,$text,(New-Object Text.UTF8Encoding($true)))
    [IO.File]::Replace($temp,$launcher,$launcher+'.before-ota-'+[guid]::NewGuid().ToString('N'))
}
# Resolve the committed side-by-side application after applying an update. The
# profile and desktop-data path remain those already selected by this launcher.
$text = [IO.File]::ReadAllText($launcher)
if (-not $text.Contains('# TokenBots desktop handover v2')) {
    $handover = @'
# TokenBots desktop handover v2
$tbLaunchApp = $PSScriptRoot
$tbInstallBase = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
$tbPointer = Join-Path $tbInstallBase 'current-copy.txt'
if (Test-Path -LiteralPath $tbPointer) {
    $tbCandidate = [IO.Path]::GetFullPath([IO.File]::ReadAllText($tbPointer).Trim())
    if ($tbCandidate.StartsWith(([IO.Path]::GetFullPath($tbInstallBase) + '\'),[StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath (Join-Path $tbCandidate '.tokenbots-custom-copy'))) {
        $tbOriginalAccess = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'resources\tokenbots-native.json') | ConvertFrom-Json
        $tbNextAccess = Get-Content -Raw -LiteralPath (Join-Path $tbCandidate 'resources\tokenbots-native.json') | ConvertFrom-Json
        if ($tbOriginalAccess.key -and $tbOriginalAccess.key -eq $tbNextAccess.key -and $tbOriginalAccess.origin -eq $tbNextAccess.origin) { $tbLaunchApp = $tbCandidate }
    }
}
'@
    $at = [regex]::Match($text,'(?m)^Start-Process -FilePath ').Index
    $text = $text.Insert($at,$handover + "`r`n")
    $text = $text.Replace("(Join-Path `$PSScriptRoot 'ChatGPT.exe') -WorkingDirectory `$PSScriptRoot", "(Join-Path `$tbLaunchApp 'ChatGPT.exe') -WorkingDirectory `$tbLaunchApp")
    # Also support older launchers without an explicit working directory.
    $text = $text.Replace("Start-Process -FilePath (Join-Path `$PSScriptRoot 'ChatGPT.exe')", "Start-Process -FilePath (Join-Path `$tbLaunchApp 'ChatGPT.exe')")
    $temp = $launcher + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temp,$text,(New-Object Text.UTF8Encoding($true)))
    [IO.File]::Replace($temp,$launcher,$launcher+'.before-handover-'+[guid]::NewGuid().ToString('N'))
}
$text = [IO.File]::ReadAllText($launcher)
if (-not $text.Contains('# TokenBots handover entry v2')) {
    # Existing shortcuts may still reference the retained old copy. Redirect
    # before loading its updater or history helper, and only for the same key.
    $entry = @'
# TokenBots handover entry v2
try {
    $tbRoot = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
    $tbCurrent = [IO.Path]::GetFullPath([IO.File]::ReadAllText((Join-Path $tbRoot 'current-copy.txt')).Trim())
    if ($tbCurrent -ne $PSScriptRoot -and $tbCurrent.StartsWith(([IO.Path]::GetFullPath($tbRoot) + '\'),[StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath (Join-Path $tbCurrent '.tokenbots-custom-copy'))) {
        $tbOldAccess = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'resources\tokenbots-native.json') | ConvertFrom-Json
        $tbNewAccess = Get-Content -Raw -LiteralPath (Join-Path $tbCurrent 'resources\tokenbots-native.json') | ConvertFrom-Json
        if ($tbOldAccess.key -and $tbOldAccess.key -eq $tbNewAccess.key -and $tbOldAccess.origin -eq $tbNewAccess.origin) {
            & (Join-Path $tbCurrent 'launch-tokenbots.ps1')
            return
        }
    }
} catch { }
'@
    $temp = $launcher + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temp,($entry + "`r`n" + $text),(New-Object Text.UTF8Encoding($true)))
    [IO.File]::Replace($temp,$launcher,$launcher+'.before-entry-'+[guid]::NewGuid().ToString('N'))
}
Write-Host 'Ready. Open TokenBots Codex using its desktop shortcut.'

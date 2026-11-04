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
Write-Host 'Ready. Open TokenBots Codex using its desktop shortcut.'

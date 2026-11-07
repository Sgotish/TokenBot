param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$app = (Resolve-Path -LiteralPath $AppDirectory).Path
if (-not (Test-Path (Join-Path $app '.tokenbots-custom-copy'))) { throw 'Unknown installation' }
$exe = Join-Path $app 'ChatGPT.exe'
if (@(Get-Process ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }).Count) { throw 'Please completely exit TokenBots Codex before updating.' }
$work = Join-Path $app ('native-update-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $work 'resources') | Out-Null
New-Item -ItemType File -Path (Join-Path $work '.tokenbots-custom-copy') | Out-Null
try {
    # Rebuild from reviewed originals, never from a twice-patched archive.
    Copy-Item -LiteralPath (Join-Path $app 'resources\app.asar.tokenbots-original') -Destination (Join-Path $work 'resources\app.asar')
    Copy-Item -LiteralPath ($exe + '.tokenbots-original') -Destination (Join-Path $work 'ChatGPT.exe')
    $owl = Join-Path $app 'resources\owl-app.ini.tokenbots-original'
    if (Test-Path $owl) { Copy-Item -LiteralPath $owl -Destination (Join-Path $work 'resources\owl-app.ini') }
    # Separate PowerShell avoids duplicate Add-Type declarations in long-lived hosts.
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'patch-copy.ps1') -AppDirectory $work
    if ($LASTEXITCODE -ne 0) { throw 'Reviewed client patch failed. Current client unchanged.' }
    # Both outputs are ready before replacing either. Retain a matched rollback pair.
    $pairs = @(@('resources\app.asar','resources\app.asar'),@('ChatGPT.exe','ChatGPT.exe'))
    $done = @()
    try {
        foreach ($pair in $pairs) {
            $target = Join-Path $app $pair[1]
            $backup = $target + '.ota-previous'
            [IO.File]::Replace((Join-Path $work $pair[0]),$target,$backup)
            $done += $target
        }
    } catch {
        foreach ($target in $done) { Copy-Item -LiteralPath ($target+'.ota-previous') -Destination $target -Force }
        throw
    }
} finally { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }

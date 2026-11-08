param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath (Join-Path $AppDirectory '.tokenbots-custom-copy'))) { throw 'Unknown app copy.' }
$launcher = Join-Path $AppDirectory 'launch-tokenbots.ps1'
$text = [IO.File]::ReadAllText($launcher)
Copy-Item -Force -LiteralPath (Join-Path $PSScriptRoot 'history-repair.cjs') -Destination (Join-Path $AppDirectory 'history-repair.cjs')
if (-not $text.Contains('# TokenBots history repair v1')) {
    $at = [regex]::Match($text,'(?m)^Start-Process -FilePath ')
    if (-not $at.Success) { throw 'Unsupported launcher.' }
    $hook = @'
# TokenBots history repair v1
try {
    $historyLock = $null
    try {
        $historyLock = [IO.File]::Open((Join-Path $PSScriptRoot 'history-repair.lock'),'OpenOrCreate','ReadWrite','None')
        $running = Get-Process -Name ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $PSScriptRoot 'ChatGPT.exe') }
        if (-not $running) {
            & (Join-Path $PSScriptRoot 'resources\cua_node\bin\node.exe') (Join-Path $PSScriptRoot 'history-repair.cjs') $PSScriptRoot
        }
    } finally { if ($historyLock) { $historyLock.Dispose() } }
} catch { }
'@
    $next = $launcher + '.history-next'
    [IO.File]::WriteAllText($next,$text.Insert($at.Index,$hook + "`r`n"),(New-Object Text.UTF8Encoding($true)))
    [IO.File]::Replace($next,$launcher,$launcher+'.before-history-repair')
}

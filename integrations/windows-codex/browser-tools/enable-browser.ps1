param([string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
if (-not $AppDirectory) { $AppDirectory = [IO.File]::ReadAllText((Join-Path $base 'current-copy.txt')).Trim() }
$app = (Resolve-Path -LiteralPath $AppDirectory).Path
if (-not $app.StartsWith(([IO.Path]::GetFullPath($base) + '\'), [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath (Join-Path $app '.tokenbots-custom-copy'))) { throw 'Unknown TokenBots copy. No configuration changed.' }
$node = Join-Path $app 'resources\cua_node\bin\node.exe'
if (-not (Test-Path -LiteralPath $node)) { throw 'Bundled Node runtime missing.' }
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe", "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path -LiteralPath $_ }
if (-not $edge) { throw 'Microsoft Edge not found. Install Edge before enabling browser tools.' }
$cfg = [IO.File]::ReadAllText((Join-Path $app 'resources\tokenbots-native.json')) | ConvertFrom-Json
if ($cfg.origin -ne 'https://pilot.tokenbots.top' -or -not $cfg.key) { throw 'Unknown TokenBots profile.' }
$profileId = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($cfg.key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
$profileDir = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $profileId)
& $node (Join-Path $PSScriptRoot 'install.cjs') $profileDir $node
if ($LASTEXITCODE -ne 0) { throw 'Browser setup stopped. Send the error text without credentials.' }
Write-Host 'Tools registered. Fully restart TokenBots Codex and start a NEW LOCAL chat. Browser click acceptance is still required.'

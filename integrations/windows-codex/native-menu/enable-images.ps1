param([string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
if (-not $AppDirectory) { $AppDirectory = [IO.File]::ReadAllText((Join-Path $base 'current-copy.txt')).Trim() }
$app = (Resolve-Path -LiteralPath $AppDirectory).Path
if (-not $app.StartsWith(([IO.Path]::GetFullPath($base) + '\'), [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath (Join-Path $app '.tokenbots-custom-copy'))) { throw 'Open an installed TokenBots Codex copy first.' }
$resources = Join-Path $app 'resources'
$node = Join-Path $resources 'cua_node\bin\node.exe'
$access = Join-Path $resources 'tokenbots-native.json'
if (-not (Test-Path -LiteralPath $node)) { throw 'Bundled Node runtime missing. Install the current TokenBots Windows package.' }
$cfg = [IO.File]::ReadAllText($access) | ConvertFrom-Json
if ($cfg.origin -ne 'https://pilot.tokenbots.top' -or -not $cfg.key) { throw 'Cannot identify TokenBots profile.' }
$profileId = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($cfg.key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
$profileDir = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $profileId)
$file = Join-Path $profileDir 'config.toml'
$original = [IO.File]::ReadAllText($file)
$script = Join-Path $resources 'tokenbots-images.cjs'
Copy-Item -Force -LiteralPath (Join-Path $PSScriptRoot 'tokenbots-images.cjs') -Destination $script
function QuoteToml([string]$s) { return (ConvertTo-Json -Compress -InputObject $s) }
$block = "[mcp_servers.tokenbots_images]`r`ncommand = $(QuoteToml $node)`r`nargs = [$(QuoteToml $script), $(QuoteToml $access)]`r`ntool_timeout_sec = 240`r`n"
$pattern = '(?ms)^\[mcp_servers\.tokenbots_images\][ \t]*\r?\n(?:(?!^[ \t]*\[).)*'
$matchesFound = [regex]::Matches($original,$pattern)
if ($matchesFound.Count -gt 1) { throw 'Duplicate image server configuration.' }
if ($matchesFound.Count -eq 1) {
    $m = $matchesFound[0]
    $updated = $original.Substring(0,$m.Index) + $block + $original.Substring($m.Index+$m.Length)
} else { $updated = $original.TrimEnd() + "`r`n`r`n" + $block }
if ($updated -ne $original) {
    $id = [guid]::NewGuid().ToString('N')
    $temp = $file + '.images-' + $id
    [IO.File]::WriteAllText($temp,$updated,(New-Object Text.UTF8Encoding($false)))
    [IO.File]::Replace($temp,$file,$file+'.before-images-'+$id)
}
Write-Host 'Ready. Reopen TokenBots Codex and ask it to generate an image in a new chat.'

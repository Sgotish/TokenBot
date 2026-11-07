param([string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
if (-not $AppDirectory) { $AppDirectory = ([IO.File]::ReadAllText((Join-Path $base 'current-copy.txt'))).Trim() }
$app = (Resolve-Path -LiteralPath $AppDirectory).Path
$exe = Join-Path $app 'ChatGPT.exe'
if (@(Get-Process ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }).Count) { throw 'Please save tasks and fully exit TokenBots Codex, then run this update again.' }
& (Join-Path $PSScriptRoot 'enable-ota.ps1') -AppDirectory $app
$node = Join-Path $app 'resources\cua_node\bin\node.exe'
$updater = Join-Path $app 'ota-client.cjs'
$ota = Join-Path $app 'tokenbots-ota'
# A public bundled asset allows installation even on a slow download route.
$asset = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'browser-asset.json')) | ConvertFrom-Json
$cache = Join-Path $ota 'assets'
New-Item -ItemType Directory -Force -Path $cache | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'browser-tools.zip') -Destination (Join-Path $cache ($asset.sha256+'.zip')) -Force
& $node -e 'const fs=require("fs"),path=require("path"),o=require(process.argv[1]);o.exclusive(process.argv[2],()=>o.prepare(process.argv[2],fs.readFileSync(process.argv[3]))).catch(()=>{process.exitCode=1})' $updater $ota (Join-Path $PSScriptRoot 'ota-seed.json')
if ($LASTEXITCODE -ne 0) { throw 'Update verification failed. Existing client has not been replaced.' }
& $node $updater apply $app
if ($LASTEXITCODE -ne 0) { throw 'Update installation failed. Please send us the error text, without your API key.' }
Write-Host 'Update complete. Open TokenBots Codex using the desktop shortcut, then open the profile menu and check updates.'

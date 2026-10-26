$ErrorActionPreference = 'Stop'
# Repair the existing dedicated home for this package's Key. Do not reinstall
# the app, create a new identity, or touch the user's original Codex directory.
$accessPath = Join-Path $PSScriptRoot 'native-access.json'
$access = [IO.File]::ReadAllText($accessPath) | ConvertFrom-Json
if ($access.origin -ne 'https://pilot.tokenbots.top' -or -not $access.key) {
    throw 'This is not a TokenBots production access package. Nothing changed.'
}
$hasher = [Security.Cryptography.SHA256]::Create()
try {
    $homeId = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($access.key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
} finally { $hasher.Dispose() }
$nativeHome = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $homeId)
$configPath = Join-Path $nativeHome 'config.toml'
if (-not (Test-Path -LiteralPath $configPath)) {
    throw 'No existing TokenBots installation for this Key. Use your original Key package or install-native.cmd. Nothing changed.'
}
$old = [IO.File]::ReadAllText($configPath)
if ($old -notmatch '(?m)^\[model_providers\.tokenbots_partner_20261016\]') {
    throw 'Unexpected provider configuration. Nothing changed.'
}
$previousHome = $env:CODEX_HOME
try {
    $env:CODEX_HOME = $nativeHome
    & (Join-Path (Split-Path $PSScriptRoot -Parent) 'setup.ps1')
} finally { $env:CODEX_HOME = $previousHome }
Write-Host 'Long-session compaction enabled. Restart the existing TokenBots Codex shortcut.'
Write-Host 'Your Key, projects and conversation history were not replaced. Configuration backup was saved.'
